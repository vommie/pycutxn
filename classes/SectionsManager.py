import datetime
import traceback
from PyQt6.QtWidgets import QTableWidgetItem
from classes.Functions import Functions

class SectionsManager:
    """
    Manages video cutting section markers, table controls, auto-creation of default section ranges,
    and visual linear-gradient overlay stops on the custom player timeline slider.
    """

    def __init__(self, parent_widget, config, jobs_db, logger, show_msg_box_fn,
                 player_manager, table_sections, btn_current_start, btn_current_end,
                 btn_add_2, btn_up, btn_down, btn_delete, btn_auto_remove, slider_player):

        self.parent = parent_widget
        self.config = config
        self.jobs = jobs_db
        self.log = logger
        self.showMsgBox = show_msg_box_fn
        self.playerManager = player_manager

        self.tableSections = table_sections
        self.btnCurrentSectionStart = btn_current_start
        self.btnCurrentSectionEnd = btn_current_end
        self.btnSectionAdd2 = btn_add_2
        self.btnSectionUp = btn_up
        self.btnSectionDown = btn_down
        self.btnSectionDelete = btn_delete
        self.btnSectionAutoRemove = btn_auto_remove
        self.sliderPlayer = slider_player

        self.timeFormat = '0:00:00.000'
        self.sectionTimeStart = self.timeFormat
        self.sectionTimeEnd = self.timeFormat

        self.sliderPlayerBgColor = 'rgba(170, 170, 170, 170)'
        self.sliderPlayerstyleTemplate = """
            QSlider::groove:horizontal {
                background: ##BG##;
            }
            QSlider::handle:horizontal {
                height: 10px;
                background: rgba(255, 0, 0, .5);
                margin: 0 -8px;
            }
        """

        self.init_slider_style()

    def init_slider_style(self):
        """Applies the initial custom design and handle stylesheet to the player slider."""
        if self.sliderPlayer:
            self.apply_slider_style(self.sliderPlayerBgColor)

    def apply_slider_style(self, bg_css_value: str):
        """Applies a custom background (color or gradient) to the player slider."""
        if self.sliderPlayer:
            style = self.sliderPlayerstyleTemplate.replace('##BG##', bg_css_value)
            self.sliderPlayer.setStyleSheet(style)

    def load_sections(self, job, video_props: dict = None):
        """Sets the sections from a job into the UI table."""
        self.clear_sections(clearCurrentJob=False, clearCurrentSection=True, video_props=video_props)
        sections = job.getSections() if job else []
        if sections:
            if sections[0]:
                self.set_section_time_start(sections[0][0], video_props)
                self.set_section_time_end(sections[0][1], video_props)
            for section in sections:
                self.section_add_row(section[0], section[1])
        else:
            self.set_current_section_in_slider(video_props)

    def set_current_section_start(self, current_time_str: str, video_props: dict = None):
        self.set_section_time_start(current_time_str, video_props)
        if self.time_string_to_time(self.sectionTimeStart) > self.time_string_to_time(self.sectionTimeEnd):
            self.set_section_time_end(self.sectionTimeStart, video_props)

    def set_current_section_end(self, current_time_str: str, video_props: dict = None):
        self.set_section_time_end(current_time_str, video_props)
        if self.time_string_to_time(self.sectionTimeEnd) < self.time_string_to_time(self.sectionTimeStart):
            self.set_section_time_start(self.sectionTimeEnd, video_props)

    def set_section_time_start(self, value: str, video_props: dict = None):
        """Setter for the current section starting time."""
        self.sectionTimeStart = value
        if self.btnCurrentSectionStart:
            self.btnCurrentSectionStart.setText(value)
        self.set_current_section_in_slider(video_props)
        self.set_btn_section_add_state()

    def set_section_time_end(self, value: str, video_props: dict = None):
        """Setter for the current section ending time."""
        self.sectionTimeEnd = value
        if self.btnCurrentSectionEnd:
            self.btnCurrentSectionEnd.setText(value)
        self.set_current_section_in_slider(video_props)
        self.set_btn_section_add_state()

    def set_btn_section_add_state(self):
        if self.btnSectionAdd2:
            if self.sectionTimeStart and self.sectionTimeEnd and (self.sectionTimeStart != self.sectionTimeEnd):
                self.btnSectionAdd2.setEnabled(True)
            else:
                self.btnSectionAdd2.setEnabled(False)

    def section_add_row(self, fromTime: str, toTime: str):
        rowIndex = self.tableSections.rowCount()
        self.tableSections.insertRow(rowIndex)
        self.tableSections.setItem(rowIndex, 0, QTableWidgetItem(fromTime))
        self.tableSections.setItem(rowIndex, 1, QTableWidgetItem(toTime))

    def section_delete_selected_row(self):
        rowIndex = self.tableSections.currentRow()
        if rowIndex < 0:
            return
        self.tableSections.removeRow(rowIndex)
        job = self.jobs.get_current_job()
        if job:
            job.removeSection(rowIndex)
        if rowIndex > 0:
            self.tableSections.setCurrentCell(rowIndex - 1, 0)
        self.set_section_btn_states()

    def clear_sections(self, clearCurrentJob: bool = True, clearCurrentSection: bool = True, video_props: dict = None):
        """
        Clears sections from table and optionally current job/markers.

        :param clearCurrentJob: If True, removes all sections from current job.
        :param clearCurrentSection: If True, resets start/end section markers.
        """
        for i in range(self.tableSections.rowCount()):
            self.tableSections.removeRow(0)
        if clearCurrentJob:
            job = self.jobs.get_current_job()
            if job:
                job.clearSections()
        if clearCurrentSection:
            self.set_section_time_start(self.timeFormat, video_props)
            self.set_section_time_end(self.timeFormat, video_props)

    def set_section_btn_states(self):
        rowCount = self.tableSections.rowCount()
        iRow = self.tableSections.currentRow()
        if rowCount == 0:
            self.btnSectionUp.setEnabled(False)
            self.btnSectionDown.setEnabled(False)
            self.btnSectionDelete.setEnabled(False)
        else:
            self.btnSectionDelete.setEnabled(True)
            if iRow == 0:
                self.btnSectionUp.setEnabled(False)
            else:
                self.btnSectionUp.setEnabled(True)
            if iRow < rowCount - 1:
                self.btnSectionDown.setEnabled(True)
            else:
                self.btnSectionDown.setEnabled(False)

    def set_current_section_in_slider(self, video_props: dict = None):
        """Sets current section range visually as a linear-gradient overlay in the custom player slider."""
        if video_props is None:
            video_props = getattr(self.parent, 'videoProps', {})

        duration_ms = video_props.get('durationMs') if video_props else 0
        if not self.sliderPlayer or not duration_ms or duration_ms <= 0:
            self.apply_slider_style(self.sliderPlayerBgColor)
            return

        gradient = 'qlineargradient(spread:pad, x1:0, y1:1, x2:1, y2:1, stop:0 BGCOLOR, stop:START1 BGCOLOR, stop:START2 MARKERCOLOR, stop:START3 MARKERCOLOR, stop:START4 CONNCOLOR, stop:END1 CONNCOLOR, stop:END2 MARKERCOLOR, stop:END3 MARKERCOLOR, stop:END4 BGCOLOR, stop:1 BGCOLOR)'

        startPos = (Functions.HMSToTimestamp(self.sectionTimeStart, True) / duration_ms)
        endPos = (Functions.HMSToTimestamp(self.sectionTimeEnd, True) / duration_ms)

        markerWidth = 0.002
        markerColor = 'rgba(225, 225, 225, 225)'
        borderSize = 0.00001

        gradient = gradient.replace('BGCOLOR', self.sliderPlayerBgColor)
        gradient = gradient.replace('MARKERCOLOR', markerColor)
        gradient = gradient.replace('START1', self.sanitize_gradient_pos(startPos - (markerWidth / 2) - borderSize))
        gradient = gradient.replace('START2', self.sanitize_gradient_pos(startPos - (markerWidth / 2)))
        gradient = gradient.replace('START3', self.sanitize_gradient_pos(startPos + (markerWidth / 2)))
        gradient = gradient.replace('START4', self.sanitize_gradient_pos(startPos + (markerWidth / 2) + borderSize))
        gradient = gradient.replace('END1', self.sanitize_gradient_pos(endPos - (markerWidth / 2) - borderSize))
        gradient = gradient.replace('END2', self.sanitize_gradient_pos(endPos - (markerWidth / 2)))
        gradient = gradient.replace('END3', self.sanitize_gradient_pos(endPos + (markerWidth / 2)))
        gradient = gradient.replace('END4', self.sanitize_gradient_pos(endPos + (markerWidth / 2) + borderSize))

        if endPos > startPos:
            gradient = gradient.replace('CONNCOLOR', markerColor)
        else:
            gradient = gradient.replace('CONNCOLOR', self.sliderPlayerBgColor)

        self.apply_slider_style(gradient)

    def sanitize_gradient_pos(self, pos: float) -> str:
        """Sanitizes position float to [0, 1] range as string for gradient stops."""
        if pos <= 0:
            pos = 0.0
        if pos >= 1:
            pos = 1.0
        return str(pos)

    def time_string_to_time(self, timeStr: str) -> datetime.datetime:
        try:
            return datetime.datetime.strptime(timeStr, '%H:%M:%S.%f')
        except Exception:
            return datetime.datetime.strptime('0:00:00.000', '%H:%M:%S.%f')

    def auto_create_section_for_job(self, job, video_props: dict) -> bool:
        """Creates a section for a job if no sections were explicitly added by user."""
        try:
            if self.sectionTimeStart == self.timeFormat and self.sectionTimeEnd == self.timeFormat:
                self.log(1, 'No section were added. Auto create whole video duration as section.')
                job.addSection(self.timeFormat, video_props.get('durationHMS', self.timeFormat))
                return True
            elif self.sectionTimeStart == self.sectionTimeEnd:
                msg = 'Error: No sections were added and section markers have same time position.'
                self.log(1, msg, 1)
                if self.showMsgBox:
                    self.showMsgBox(
                        msg,
                        infoText='Please set a valid section range.',
                        detailText='Current section start: %s\nCurrent section End: %s' % (self.sectionTimeStart, self.sectionTimeEnd),
                        icon='critical'
                    )
                return False
            else:
                self.log(1, 'No section were added. Auto create section from %s to %s.' % (self.sectionTimeStart, self.sectionTimeEnd))
                job.addSection(self.sectionTimeStart, self.sectionTimeEnd)
                return True
        except Exception:
            raise Exception(traceback.format_exc())

    def on_btn_section_add_clicked(self):
        if self.sectionTimeStart == self.sectionTimeEnd:
            if self.showMsgBox:
                self.showMsgBox(
                    'Cannot add a 0-second section.',
                    infoText='Please set a valid section range by seeking forward before setting Section End.',
                    icon='warning'
                )
            return

        self.section_add_row(self.sectionTimeStart, self.sectionTimeEnd)
        job = self.jobs.get_current_job()
        if job:
            job.addSection(self.sectionTimeStart, self.sectionTimeEnd)

    def on_btn_section_delete_clicked(self):
        self.section_delete_selected_row()

    def on_btn_section_up_clicked(self):
        move = Functions.moveTableRow(self.tableSections, -1)
        job = self.jobs.get_current_job()
        if job:
            job.moveSection(move.get('from'), move.get('to'))

    def on_btn_section_down_clicked(self):
        move = Functions.moveTableRow(self.tableSections, 1)
        job = self.jobs.get_current_job()
        if job:
            job.moveSection(move.get('from'), move.get('to'))

    def on_btn_current_section_start_clicked(self, current_player_time: str):
        if self.sectionTimeStart != current_player_time and self.playerManager and self.playerManager.playerControl:
            self.playerManager.playerControl.seek(self.sectionTimeStart, 'absolute')

    def on_btn_current_section_end_clicked(self, current_player_time: str):
        if self.sectionTimeEnd != current_player_time and self.playerManager and self.playerManager.playerControl:
            self.playerManager.playerControl.seek(self.sectionTimeEnd, 'absolute')

    def on_btn_section_auto_remove_clicked(self):
        if self.btnSectionAutoRemove:
            self.config.setSectionsAutoRemove(self.btnSectionAutoRemove.isChecked())

    def on_table_section_curr_cell_changed(self):
        self.set_section_btn_states()

    def on_table_section_item_dbl_clicked(self, item):
        if item and self.playerManager and self.playerManager.playerControl:
            timeStr = item.text()
            self.playerManager.playerControl.seek(timeStr, 'absolute')
