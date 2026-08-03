import re
import math
import datetime
import subprocess
import traceback
from PyQt6.QtWidgets import QLayout

class FilterManager:
    """
    Manages the video filter pipeline UI components (Crop, Deinterlace, Resize, Rotate, Deshake),
    grid layout reordering, Auto-Crop detection, CropOverlay interaction, and MPV 'vf' string generation.
    """

    def __init__(self, parent_widget, config, jobs_db, logger, show_msg_box_fn,
                 player_manager, crop_overlay, grid_layout_filters,
                 crop_widgets, deinterlace_widgets, resize_widgets, rotate_widgets, deshake_widgets,
                 global_filter_widgets, layout_refs):

        self.parent = parent_widget
        self.config = config
        self.jobs = jobs_db
        self.log = logger
        self.showMsgBox = show_msg_box_fn
        self.playerManager = player_manager
        self.cropOverlay = crop_overlay
        self.gridLayoutFilters = grid_layout_filters

        # Layout references
        self.layoutFilterCrop = layout_refs['crop']
        self.layoutFilterDeinterlace = layout_refs['deinterlace']
        self.layoutFilterResize = layout_refs['resize']
        self.layoutFilterRotate = layout_refs['rotate']
        self.layoutFilterDeshake = layout_refs['deshake']

        # Crop widgets
        self.btnFilterCrop = crop_widgets['btn']
        self.boxFilterCropT = crop_widgets['top']
        self.boxFilterCropR = crop_widgets['right']
        self.boxFilterCropB = crop_widgets['bottom']
        self.boxFilterCropL = crop_widgets['left']
        self.labelCropT = crop_widgets['label_top']
        self.labelCropR = crop_widgets['label_right']
        self.labelCropB = crop_widgets['label_bottom']
        self.labelCropL = crop_widgets['label_left']
        self.btnAutoCrop = crop_widgets['btn_autocrop']
        self.btnFilterCropUp = crop_widgets['btn_up']
        self.btnFilterCropDown = crop_widgets['btn_down']

        # Deinterlace widgets
        self.btnFilterDeinterlace = deinterlace_widgets['btn']
        self.comboBoxFilterDeinterlaceDeinterlacer = deinterlace_widgets['combo']
        self.btnFilterDeinterlaceUp = deinterlace_widgets['btn_up']
        self.btnFilterDeinterlaceDown = deinterlace_widgets['btn_down']

        # Resize widgets
        self.btnFilterResize = resize_widgets['btn']
        self.boxFilterResizeW = resize_widgets['width']
        self.boxFilterResizeH = resize_widgets['height']
        self.btnFilterResize169 = resize_widgets['btn_169']
        self.btnFilterResize43 = resize_widgets['btn_43']
        self.btnFilterResizeUp = resize_widgets['btn_up']
        self.btnFilterResizeDown = resize_widgets['btn_down']

        # Rotate widgets
        self.btnFilterRotateLeft = rotate_widgets['left']
        self.btnFilterRotateRight = rotate_widgets['right']
        self.btnFilterRotate180 = rotate_widgets['rotate180']
        self.btnFilterRotateUp = rotate_widgets['btn_up']
        self.btnFilterRotateDown = rotate_widgets['btn_down']

        # Deshake widgets
        self.btnFilterDeshake = deshake_widgets['btn']
        self.btnFilterDeshakeUp = deshake_widgets['btn_up']
        self.btnFilterDeshakeDown = deshake_widgets['btn_down']

        # Global filter controls
        self.btnFiltersPreview = global_filter_widgets['preview']
        self.btnFiltersKeep = global_filter_widgets['keep']
        self.btnFiltersReset = global_filter_widgets['reset']

        self.filterAtts = {
            'crop': {
                'layout': self.layoutFilterCrop,
                'btnUp': self.btnFilterCropUp,
                'btnDown': self.btnFilterCropDown
            },
            'deinterlace': {
                'layout': self.layoutFilterDeinterlace,
                'btnUp': self.btnFilterDeinterlaceUp,
                'btnDown': self.btnFilterDeinterlaceDown
            },
            'resize': {
                'layout': self.layoutFilterResize,
                'btnUp': self.btnFilterResizeUp,
                'btnDown': self.btnFilterResizeDown
            },
            'rotate': {
                'layout': self.layoutFilterRotate,
                'btnUp': self.btnFilterRotateUp,
                'btnDown': self.btnFilterRotateDown
            },
            'deshake': {
                'layout': self.layoutFilterDeshake,
                'btnUp': self.btnFilterDeshakeUp,
                'btnDown': self.btnFilterDeshakeDown
            }
        }

    def load_all_filters(self, job, video_props):
        """Loads all filter states and grid positions from a job into UI."""
        self.load_filter_crop(job)
        self.load_filter_deinterlace(job)
        self.load_filter_rotate(job)
        self.load_filter_resize(job)
        self.load_filter_deshake(job)
        self.load_filter_positions(job, video_props)

    def load_filter_crop(self, job):
        try:
            state = job.getFilterCropState()
            if not state:
                self.reset_crop_filter()
            else:
                self.btnFilterCrop.setChecked(True)
                value = job.getFilterCropT()
                self.boxFilterCropT.setValue(value if value else 0)
                value = job.getFilterCropR()
                self.boxFilterCropR.setValue(value if value else 0)
                value = job.getFilterCropB()
                self.boxFilterCropB.setValue(value if value else 0)
                value = job.getFilterCropL()
                self.boxFilterCropL.setValue(value if value else 0)
        except Exception as e:
            msg = 'Error: Cannot load crop filter from job.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            if self.showMsgBox:
                self.showMsgBox(msg, detailText=traceback.format_exc(), icon='warning')

    def load_filter_deinterlace(self, job):
        try:
            state = job.getFilterDeinterlaceState()
            if not state:
                self.reset_deinterlace_filter()
            if state:
                self.btnFilterDeinterlace.setChecked(True)
            deinterlacer = job.getFilterDeinterlaceDeinterlacer()
            if deinterlacer:
                self.comboBoxFilterDeinterlaceDeinterlacer.setCurrentText(deinterlacer)
        except Exception as e:
            msg = 'Error: Cannot load deinterlace filter from job.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            if self.showMsgBox:
                self.showMsgBox(msg, detailText=traceback.format_exc(), icon='warning')

    def load_filter_rotate(self, job, video_props=None):
        try:
            rotation = job.getFilterRotate()
            if not rotation:
                self.reset_rotate_filter()
            elif rotation == 90:
                self.btnFilterRotateRight.setChecked(True)
                self.on_btn_filter_rotate_right(video_props)
            elif rotation == -90:
                self.btnFilterRotateLeft.setChecked(True)
                self.on_btn_filter_rotate_left(video_props)
            elif rotation == 180:
                self.btnFilterRotate180.setChecked(True)
                self.on_btn_filter_rotate_180(video_props)
        except Exception as e:
            msg = 'Error: Cannot load rotate filter from job.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            if self.showMsgBox:
                self.showMsgBox(msg, detailText=traceback.format_exc(), icon='warning')

    def load_filter_resize(self, job):
        try:
            state = job.getFilterResizeState()
            if not state:
                self.reset_resize_filter()
            if state:
                self.btnFilterResize.setChecked(True)
                value = job.getFilterResizeWidth()
                self.boxFilterResizeW.setValue(value if value else 0)
                value = job.getFilterResizeHeight()
                self.boxFilterResizeH.setValue(value if value else 0)
        except Exception as e:
            msg = 'Error: Cannot load resize filter from job.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            if self.showMsgBox:
                self.showMsgBox(msg, detailText=traceback.format_exc(), icon='warning')

    def load_filter_deshake(self, job):
        try:
            state = job.getFilterDeshakeState()
            self.btnFilterDeshake.setChecked(bool(state))
        except Exception as e:
            msg = 'Error: Cannot load deshake filter from job.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            if self.showMsgBox:
                self.showMsgBox(msg, detailText=traceback.format_exc(), icon='warning')

    def move_row_in_filters_grid(self, index, moveDown):
        rowCount = self.gridLayoutFilters.count()
        if moveDown and index == rowCount - 1:
            return False
        elif not moveDown and index == 0:
            return False
        items = self.get_filter_position_items()
        for i in range(len(items)):
            if moveDown:
                if i - 1 == index:
                    self.gridLayoutFilters.addItem(items[i - 1], i, 0)
                elif i == index:
                    self.gridLayoutFilters.addItem(items[i + 1], i, 0)
                else:
                    self.gridLayoutFilters.addItem(items[i], i, 0)
            else:
                if i + 1 == index:
                    self.gridLayoutFilters.addItem(items[i + 1], i, 0)
                elif i == index:
                    self.gridLayoutFilters.addItem(items[i - 1], i, 0)
                else:
                    self.gridLayoutFilters.addItem(items[i], i, 0)
        return True

    def get_index_of_layout_in_filters_grid(self, filterLayout):
        layout = self.gridLayoutFilters.layout()
        if not layout:
            return -1
        return layout.indexOf(filterLayout)

    def set_filter_btn_states(self, video_props=None):
        filterPositions = {}
        rowCount = self.gridLayoutFilters.count()
        for key in self.filterAtts:
            atts = self.filterAtts[key]
            index = self.get_index_of_layout_in_filters_grid(atts['layout'])
            if index > 0:
                atts['btnUp'].setEnabled(True)
            else:
                atts['btnUp'].setEnabled(False)

            if index < rowCount - 1:
                atts['btnDown'].setEnabled(True)
            else:
                atts['btnDown'].setEnabled(False)

            filterPositions.update({index: key})

        job = self.jobs.get_current_job()
        if job:
            job.setFilterPositions(filterPositions)

        self.set_video_filter(video_props)
        self.set_crop_fields_by_rotation()

    def get_filter_position_items(self):
        items = []
        rowCount = self.gridLayoutFilters.count()
        for i in range(rowCount):
            item = self.gridLayoutFilters.takeAt(0)
            item.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
            item.setSpacing(6)
            items.append(item)
        return items

    def load_filter_positions(self, job, video_props=None):
        items = self.get_filter_position_items()
        filterPositions = job.getFilterPositions()
        sorted_positions = sorted(filterPositions.keys(), key=lambda x: int(x))
        for position in sorted_positions:
            filter_name = filterPositions.get(position)
            if not filter_name:
                filter_name = filterPositions.get(str(position))
            for item in items:
                name = item.objectName()
                atts = self.filterAtts.get(filter_name)
                if not atts:
                    msg = 'Filter is not implemented: "%s"' % name
                    self.log(1, msg, 1)
                    if self.showMsgBox:
                        self.showMsgBox(msg, btns="ok", icon="warning")
                    return
                layout = atts.get('layout')
                searchName = layout.objectName()
                if name == searchName:
                    self.gridLayoutFilters.addItem(item, int(position), 0)
        self.set_filter_btn_states(video_props)

    def set_video_filter(self, video_props=None):
        """Compiles active UI filters into an MPV 'vf' string."""
        filters = []
        if self.btnFiltersPreview.isChecked() and video_props:
            job = self.jobs.get_current_job()
            if not job:
                return
            filterPositions = job.getFilterPositions()
            vW = video_props.get('width', 0)
            vH = video_props.get('height', 0)
            sorted_positions = sorted(filterPositions.keys(), key=lambda x: int(x))

            for position in sorted_positions:
                filterName = filterPositions.get(position)
                if not filterName:
                    filterName = filterPositions.get(str(position))

                # Crop
                if filterName == 'crop' and self.btnFilterCrop.isChecked():
                    cropT = self.boxFilterCropT.value()
                    cropR = self.boxFilterCropR.value()
                    cropB = self.boxFilterCropB.value()
                    cropL = self.boxFilterCropL.value()
                    if cropT or cropR or cropB or cropL:
                        vW = vW - cropR - cropL
                        vH = vH - cropT - cropB
                        filters.append('crop=%s:%s:%s:%s' % (vW, vH, cropL, cropT))

                # Resize
                elif filterName == 'resize' and self.btnFilterResize.isChecked():
                    w = self.boxFilterResizeW.value()
                    h = self.boxFilterResizeH.value()
                    if w:
                        vW = w
                    if h:
                        vH = h
                    if w or h:
                        if not w:
                            w = -1
                        if not h:
                            h = -1
                        filters.append('scale=%s:%s,setsar=1:1' % (w, h))

                # Rotate
                elif filterName == 'rotate':
                    if self.btnFilterRotateLeft.isChecked():
                        filters.append('transpose=2')
                    elif self.btnFilterRotateRight.isChecked():
                        filters.append('transpose=1')
                    elif self.btnFilterRotate180.isChecked():
                        filters.append('transpose=2,transpose=2')

                # Deinterlace
                elif filterName == 'deinterlace' and self.btnFilterDeinterlace.isChecked():
                    filters.append('%s' % self.comboBoxFilterDeinterlaceDeinterlacer.currentText())

        if self.playerManager and self.playerManager.playerControl:
            if filters:
                vFilter = ','.join(filters)
                self.log(1, 'Set video filters: %s' % vFilter)
                self.playerManager.playerControl.player['vf'] = vFilter
            else:
                self.playerManager.playerControl.player['vf'] = ''

    def reset_filters(self):
        """Resets all filters to default values."""
        self.reset_crop_filter()
        self.reset_rotate_filter()
        self.reset_resize_filter()
        self.reset_deshake_filter()
        self.reset_deinterlace_filter()

    def reset_crop_filter(self):
        self.btnFilterCrop.setChecked(False)
        self.boxFilterCropT.setValue(0)
        self.boxFilterCropR.setValue(0)
        self.boxFilterCropB.setValue(0)
        self.boxFilterCropL.setValue(0)

    def reset_rotate_filter(self):
        self.btnFilterRotateRight.setChecked(False)
        self.btnFilterRotateLeft.setChecked(False)
        self.btnFilterRotate180.setChecked(False)

    def reset_resize_filter(self):
        self.boxFilterResizeW.setValue(0)
        self.boxFilterResizeH.setValue(0)
        self.btnFilterResize.setChecked(False)

    def reset_deshake_filter(self):
        self.btnFilterDeshake.setChecked(False)

    def reset_deinterlace_filter(self):
        self.btnFilterDeinterlace.setChecked(False)
        self.comboBoxFilterDeinterlaceDeinterlacer.setCurrentText(self.config.getFiltersDeinterlacer())

    def set_btn_filters_preview_icon(self):
        if self.btnFiltersPreview.isChecked():
            self.btnFiltersPreview.setText('')
        else:
            self.btnFiltersPreview.setText('')

    def set_crop_fields_by_rotation(self):
        """Change icon and tooltip of all crop fields based on active rotation."""
        job = self.jobs.get_current_job()
        if not job:
            return
        filterPositions = job.getFilterPositions()
        isCropBeforeRotate = True
        sorted_positions = sorted(filterPositions.keys(), key=lambda x: int(x))

        for position in sorted_positions:
            filter_name = filterPositions.get(position)
            if not filter_name:
                filter_name = filterPositions.get(str(position))
            if filter_name == 'crop':
                break
            elif filter_name == 'rotate':
                isCropBeforeRotate = False
                break

        chars = {
            't': ['Top', ''],
            'r': ['Right', ''],
            'b': ['Bottom', ''],
            'l': ['Left', ''],
        }
        t = chars['t']
        r = chars['r']
        b = chars['b']
        l = chars['l']

        if isCropBeforeRotate:
            if self.btnFilterRotateRight.isChecked():
                t = chars['r']
                r = chars['b']
                b = chars['l']
                l = chars['t']
            elif self.btnFilterRotateLeft.isChecked():
                t = chars['l']
                r = chars['t']
                b = chars['r']
                l = chars['b']
            elif self.btnFilterRotate180.isChecked():
                t = chars['b']
                r = chars['l']
                b = chars['t']
                l = chars['r']

        self.labelCropT.setText(t[1])
        self.boxFilterCropT.setToolTip(t[0])
        self.labelCropR.setText(r[1])
        self.boxFilterCropR.setToolTip(r[0])
        self.labelCropB.setText(b[1])
        self.boxFilterCropB.setToolTip(b[0])
        self.labelCropL.setText(l[1])
        self.boxFilterCropL.setToolTip(l[0])

    def get_autocrop_values(self, current_time_str: str, video_props: dict, limit=24, round_val=2, skip=0, reset=0):
        """Executes FFmpeg cropdetect filter via subprocess and returns detected crop bounds."""
        self.log(1, 'Get autocrop values ...')
        job = self.jobs.get_current_job()
        if not job or not video_props:
            return None

        file_path = job.getSrcFilePathLong()
        time_format = '%H:%M:%S.%f'
        duration_hms = video_props.get('durationHMS', '0:00:00.000')

        try:
            curr_dt = datetime.datetime.strptime(current_time_str, time_format)
            dur_dt = datetime.datetime.strptime(duration_hms, time_format)
            if curr_dt <= dur_dt:
                time_val = current_time_str
            else:
                time_val = (dur_dt - datetime.timedelta(milliseconds=100)).strftime(time_format)
        except Exception:
            time_val = current_time_str

        cmd = 'ffmpeg -ss %s -i "%s" -t 00:00:00.1 -vf cropdetect=%d:%d:%d:%d -f null - 2>&1 | awk \'/crop/ { print $NF }\' | tail -1' % (
            time_val, file_path, limit, round_val, skip, reset
        )
        result = subprocess.run([cmd], stdout=subprocess.PIPE, shell=True)
        crop = re.findall(r'\d+', str(result.stdout))
        self.log(1, crop)
        return crop

    def on_btn_filter_auto_crop_clicked(self, current_time_str: str, video_props: dict):
        crop = self.get_autocrop_values(current_time_str, video_props, limit=24)
        if not crop or len(crop) < 4 or not video_props:
            return

        vw = video_props.get('width', 0)
        vh = video_props.get('height', 0)

        t = int(crop[3])
        r = vw - int(crop[0]) - int(crop[2])
        b = vh - int(crop[1]) - int(crop[3])
        l = int(crop[2])

        # Checks
        if t < 0 or t == vh:
            t = 0
        if r < 0 or r == vw:
            r = 0
        if b < 0 or b == vh:
            b = 0
        if l < 0 or l == vw:
            l = 0

        # Prevent odd values
        if (t + b) % 2 == 1:
            b += 1
        if (l + r) % 2 == 1:
            r += 1

        # Set cropping values
        self.boxFilterCropT.setValue(t)
        self.boxFilterCropR.setValue(r)
        self.boxFilterCropB.setValue(b)
        self.boxFilterCropL.setValue(l)

        if t == 0 and r == 0 and b == 0 and l == 0:
            if self.btnFilterCrop.isChecked():
                self.btnFilterCrop.setChecked(False)
        else:
            if not self.btnFilterCrop.isChecked():
                self.btnFilterCrop.setChecked(True)

    def on_btn_filter_crop_clicked(self, video_props=None):
        job = self.jobs.get_current_job()
        if job:
            job.setFilterCropState(self.btnFilterCrop.isChecked())
        if not self.btnFilterCrop.isChecked() and self.cropOverlay:
            self.log(1, "[DEBUG] Crop button unchecked, stopping interaction.")
            self.cropOverlay.stop_interaction()
        self.set_video_filter(video_props)

    def on_box_filter_crop_changed(self, edge: str, px: int, video_props=None):
        job = self.jobs.get_current_job()
        if not job:
            return
        if edge == 't':
            job.setFilterCropT(px)
        elif edge == 'r':
            job.setFilterCropR(px)
        elif edge == 'b':
            job.setFilterCropB(px)
        elif edge == 'l':
            job.setFilterCropL(px)
        self.set_video_filter(video_props)

    def on_btn_filter_deinterlace_clicked(self, video_props=None):
        job = self.jobs.get_current_job()
        if job:
            job.setFilterDeinterlaceState(self.btnFilterDeinterlace.isChecked())
            job.setFilterDeinterlaceDeinterlacer(self.comboBoxFilterDeinterlaceDeinterlacer.currentText())
        self.set_video_filter(video_props)

    def on_combobox_deinterlacer_changed(self, text: str, video_props=None):
        job = self.jobs.get_current_job()
        if job:
            job.setFilterDeinterlaceDeinterlacer(text)
        self.config.setFiltersDeinterlacer(text)
        self.set_video_filter(video_props)

    def on_btn_filter_resize_clicked(self, video_props=None):
        job = self.jobs.get_current_job()
        if job:
            job.setFilterResizeState(self.btnFilterResize.isChecked())
        if video_props:
            if self.boxFilterResizeW.value() == 0:
                self.boxFilterResizeW.setValue(video_props.get('width', 0))
            if self.boxFilterResizeH.value() == 0:
                self.boxFilterResizeH.setValue(video_props.get('height', 0))
        self.set_video_filter(video_props)

    def on_box_filter_resize_w_changed(self, val: int, video_props=None):
        job = self.jobs.get_current_job()
        if job:
            job.setFilterResizeWidth(val)
        self.set_video_filter(video_props)

    def on_box_filter_resize_h_changed(self, val: int, video_props=None):
        job = self.jobs.get_current_job()
        if job:
            job.setFilterResizeHeight(val)
        self.set_video_filter(video_props)

    def on_btn_filter_resize_169(self):
        self.boxFilterResizeH.setValue(math.ceil((self.boxFilterResizeW.value() / (16 / 9)) / 2.) * 2)

    def on_btn_filter_resize_43(self):
        self.boxFilterResizeH.setValue(math.ceil((self.boxFilterResizeW.value() / (4 / 3)) / 2.) * 2)

    def on_btn_filter_deshake_clicked(self):
        job = self.jobs.get_current_job()
        if job:
            job.setFilterDeshakeState(self.btnFilterDeshake.isChecked())

    def on_btn_filter_rotate_left(self, video_props=None):
        job = self.jobs.get_current_job()
        if job:
            if self.btnFilterRotateLeft.isChecked():
                job.setFilterRotate(-90)
            else:
                job.setFilterRotate(False)
        self.btnFilterRotateRight.setChecked(False)
        self.btnFilterRotate180.setChecked(False)
        self.set_video_filter(video_props)
        self.set_crop_fields_by_rotation()

    def on_btn_filter_rotate_right(self, video_props=None):
        job = self.jobs.get_current_job()
        if job:
            if self.btnFilterRotateRight.isChecked():
                job.setFilterRotate(90)
            else:
                job.setFilterRotate(False)
        self.btnFilterRotateLeft.setChecked(False)
        self.btnFilterRotate180.setChecked(False)
        self.set_video_filter(video_props)
        self.set_crop_fields_by_rotation()

    def on_btn_filter_rotate_180(self, video_props=None):
        job = self.jobs.get_current_job()
        if job:
            if self.btnFilterRotate180.isChecked():
                job.setFilterRotate(180)
            else:
                job.setFilterRotate(False)
        self.btnFilterRotateLeft.setChecked(False)
        self.btnFilterRotateRight.setChecked(False)
        self.set_video_filter(video_props)
        self.set_crop_fields_by_rotation()

    def on_btn_filters_preview(self, video_props=None):
        self.config.setFiltersPreview(self.btnFiltersPreview.isChecked())
        self.set_video_filter(video_props)
        self.set_btn_filters_preview_icon()
