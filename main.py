#!/usr/bin/env python3

import sys
import os
if "QT_QPA_PLATFORM" not in os.environ:
    os.environ["QT_QPA_PLATFORM"] = "xcb;wayland"

import datetime
import subprocess
import re
import shutil
import hashlib
import locale
import math
import traceback
import gc
import ctypes

from PyQt6 import uic, QtGui, QtWidgets, QtCore
from PyQt6.QtWidgets import QListWidgetItem, QLayout, QMessageBox, QTableWidgetItem, QMainWindow, QDialog
from PyQt6.QtCore import Qt, pyqtSlot, QCoreApplication, QTimer, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QFontDatabase, QKeySequence, QPalette, QColor, QAction, QShortcut

import res  # pyrcc5 -o res.py res/res.qrc

# Dialogs & Core Classes
from classes.DirsUI import DirsUI
from classes.HashUI import HashUI
from classes.TagsFilterUI import TagsFilterUI
from classes.SettingsUI import SettingsUI
from classes.LogUi import LogUi
from classes.RatingUI import RatingUI
from classes.KnownUI import KnownUI
from classes.EditDBUI import EditDBUI
from classes.TimerMessageBox import TimerMessageBox
from classes.CropOverlay import CropOverlay
from classes.PlayerSlider import PlayerSlider
from classes.Config import Config
from classes.JobsDB import JobsDB
from classes.DB import DB
from classes.Functions import Functions

# Manager & Helper Classes
from classes.CodecSpecs import CODEC_SPECS, CodecSpecs
from classes.TargetDirScannerThread import TargetDirScannerThread
from classes.AppLogger import AppLogger
from classes.PowerManager import PowerManager
from classes.FileHashService import FileHashService
from classes.PlayerManager import MPVSignalBridge, PlayerManager
from classes.FilterManager import FilterManager
from classes.SectionsManager import SectionsManager
from classes.TaggerManager import TaggerManager
from classes.QueueManager import QueueManager


class MainUi(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        self.rootDir = os.path.dirname(os.path.realpath(__file__))
        QtGui.QFontDatabase.addApplicationFont('%s/res/font_droid_sans_mono_nerd.otf' % self.rootDir)
        super(MainUi, self).__init__()
        uic.loadUi('%s/gui/main.ui' % self.rootDir, self)

        self.initMembers()
        self.initManagers()
        self.initGui()
        self.initShortcuts()
        self.initGuiEvents()

        self.playerManager.init_player()
        self.show()
        self.preventDragging()

    @property
    def tagsTree(self):
        """Delegates tagsTree access to TaggerManager for EditDBUI dialog compatibility."""
        return self.taggerManager.tagsTree if hasattr(self, 'taggerManager') else []

    def tagOrParentTagsHaveFilter(self, currTag, setFilter=False):
        """Delegates tag filtering check to TaggerManager for EditDBUI dialog compatibility."""
        if hasattr(self, 'taggerManager'):
            return self.taggerManager.tag_or_parent_tags_have_filter(currTag, setFilter)
        return False

    def preventDragging(self):
        """Prevents almost all GUI elements from being dragged except those in nonDraggable."""
        self.nonDraggable = [self.renderFrame, self.groupBoxSections, self.centralwidget]
        for obj in self.findChildren(QtWidgets.QWidget):
            if obj in self.nonDraggable:
                obj.installEventFilter(self)

    def eventFilter(self, source, event):
        if event.type() == QtCore.QEvent.Type.MouseMove:
            leftMouseButtonPressed = (event.buttons() == QtCore.Qt.MouseButton.LeftButton)
            cursorShape = self.cursor().shape()
            resizing = cursorShape in {
                QtCore.Qt.CursorShape.SizeHorCursor,
                QtCore.Qt.CursorShape.SizeVerCursor,
                QtCore.Qt.CursorShape.SizeBDiagCursor,
                QtCore.Qt.CursorShape.SizeFDiagCursor,
                QtCore.Qt.CursorShape.SizeAllCursor,
                QtCore.Qt.CursorShape.SplitHCursor,
                QtCore.Qt.CursorShape.SplitVCursor,
                QtCore.Qt.CursorShape.OpenHandCursor,
                QtCore.Qt.CursorShape.ClosedHandCursor
            }
            if leftMouseButtonPressed and not resizing and source in self.nonDraggable:
                return True
        return super(MainUi, self).eventFilter(source, event)

    def initMembers(self):
        self.is_first_show = True
        self.config = Config()
        self.iconFontName = 'DroidSansMono Nerd Font Mono'
        self.jobsFilePath = self.config.getJobsFilePath()
        self.jobs = None

        try:
            self.jobs = JobsDB(self.jobsFilePath)
            self.jobs.create_empty_current_job()
        except Exception as e:
            msg = 'Error: Cannot initialize jobs database.'
            if hasattr(self, 'log'):
                self.log(1, msg, 1)
            self.showMsgBox(msg, detailText=str(e), icon='critical')

        # Dynamically created QActions
        self.actionEditDBEntry = QAction('Edit DB entry', self)
        self.actionStateCancel = QAction('Cancel Job', self)

        # Dialogs
        self.dirsUI = DirsUI(self)
        self.knownUI = KnownUI(self)
        self.hashUI = HashUI(self)
        self.ratingUI = RatingUI(self)
        self.tagsFilterUI = TagsFilterUI(self)
        self.settingsUI = SettingsUI(self)
        self.logUi = LogUi(self)

        # Database
        self.db = DB(self.config.getTaggerDBPath(), lambda *args, **kwargs: self.log(*args, **kwargs))
        self.labelTaggerError.setHidden(True)

        # Custom Slider
        self.sliderPlayer = PlayerSlider(Qt.Orientation.Horizontal)
        self.framePlayerProgress.insertWidget(0, self.sliderPlayer)
        self.sliderPlayer.factor = self.config.getPlayerSliderFactor()
        self.sliderPlayer.setMinimum(0)
        self.sliderPlayer.setMaximum(99 * self.sliderPlayer.factor)
        self.sliderPlayer.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Video State Variables
        self.videoProps = {}
        self.overwriteFile = False
        self.jobsToReplace = False
        self.dirScannerThread = None

    def initManagers(self):
        """Instantiates and wires all domain manager classes."""
        self.logger = AppLogger(self.logApp, self.logFFmpeg, self.logDB)
        self.log = self.logger.log

        self.powerManager = PowerManager(self, self.btnQueueSleep, self.btnQueueShutdown)

        self.fileHashService = FileHashService(
            db=self.db,
            hash_ui=self.hashUI,
            logger=self.log,
            show_msg_box_fn=self.showMsgBox,
            hash_file_ext='md5'
        )

        self.playerManager = PlayerManager(
            parent_widget=self,
            config=self.config,
            logger=self.log,
            show_msg_box_fn=self.showMsgBox,
            render_frame=self.renderFrame,
            btn_pause=self.btnPause,
            btn_mute=self.btnMute,
            slider_volume=self.sliderVolume,
            slider_player=self.sliderPlayer,
            label_time_curr=self.labelPlayerTimeCurr,
            label_time_total=self.labelPlayerTimeTotal,
            frame_player_btns=self.framePlayerBtns,
            frame_player_progress=self.framePlayerProgress
        )

        self.cropOverlay = CropOverlay(self.renderFrame, self)

        crop_widgets = {
            'btn': self.btnFilterCrop, 'top': self.boxFilterCropT, 'right': self.boxFilterCropR,
            'bottom': self.boxFilterCropB, 'left': self.boxFilterCropL, 'label_top': self.labelCropT,
            'label_right': self.labelCropR, 'label_bottom': self.labelCropB, 'label_left': self.labelCropL,
            'btn_autocrop': self.btnAutoCrop, 'btn_up': self.btnFilterCropUp, 'btn_down': self.btnFilterCropDown
        }
        deinterlace_widgets = {
            'btn': self.btnFilterDeinterlace, 'combo': self.comboBoxFilterDeinterlaceDeinterlacer,
            'btn_up': self.btnFilterDeinterlaceUp, 'btn_down': self.btnFilterDeinterlaceDown
        }
        resize_widgets = {
            'btn': self.btnFilterResize, 'width': self.boxFilterResizeW, 'height': self.boxFilterResizeH,
            'btn_169': self.btnFilterResize169, 'btn_43': self.btnFilterResize43,
            'btn_up': self.btnFilterResizeUp, 'btn_down': self.btnFilterResizeDown
        }
        rotate_widgets = {
            'left': self.btnFilterRotateLeft, 'right': self.btnFilterRotateRight,
            'rotate180': self.btnFilterRotate180, 'btn_up': self.btnFilterRotateUp, 'btn_down': self.btnFilterRotateDown
        }
        deshake_widgets = {
            'btn': self.btnFilterDeshake, 'btn_up': self.btnFilterDeshakeUp, 'btn_down': self.btnFilterDeshakeDown
        }
        global_filter_widgets = {
            'preview': self.btnFiltersPreview, 'keep': self.btnFiltersKeep, 'reset': self.btnFiltersReset
        }
        layout_refs = {
            'crop': self.layoutFilterCrop, 'deinterlace': self.layoutFilterDeinterlace,
            'resize': self.layoutFilterResize, 'rotate': self.layoutFilterRotate, 'deshake': self.layoutFilterDeshake
        }

        self.filterManager = FilterManager(
            parent_widget=self, config=self.config, jobs_db=self.jobs, logger=self.log,
            show_msg_box_fn=self.showMsgBox, player_manager=self.playerManager, crop_overlay=self.cropOverlay,
            grid_layout_filters=self.gridLayoutFilters, crop_widgets=crop_widgets, deinterlace_widgets=deinterlace_widgets,
            resize_widgets=resize_widgets, rotate_widgets=rotate_widgets, deshake_widgets=deshake_widgets,
            global_filter_widgets=global_filter_widgets, layout_refs=layout_refs
        )

        self.sectionsManager = SectionsManager(
            parent_widget=self, config=self.config, jobs_db=self.jobs, logger=self.log,
            show_msg_box_fn=self.showMsgBox, player_manager=self.playerManager, table_sections=self.tableSections,
            btn_current_start=self.btnCurrentSectionStart, btn_current_end=self.btnCurrentSectionEnd,
            btn_add_2=self.btnSectionAdd2, btn_up=self.btnSectionUp, btn_down=self.btnSectionDown,
            btn_delete=self.btnSectionDelete, btn_auto_remove=self.btnSectionAutoRemove, slider_player=self.sliderPlayer
        )

        rate_radio_btns = {
            0: self.radioButton_rate0, 1: self.radioButton_rate1, 2: self.radioButton_rate2,
            3: self.radioButton_rate3, 4: self.radioButton_rate4, 5: self.radioButton_rate5
        }

        self.taggerManager = TaggerManager(
            parent_widget=self, config=self.config, db=self.db, jobs_db=self.jobs, rating_ui=self.ratingUI,
            logger=self.log, show_msg_box_fn=self.showMsgBox, dock_tagger=self.dockTagger,
            label_tagger_error=self.labelTaggerError, list_widget_tags_tree=self.listWidgetTagsTree,
            list_widget_last_tags=self.listWidgetLastTags, btn_last_rating=self.btnLastRating,
            btn_tagger_active=self.btnTaggerActive, btn_tagger_warning=self.btnTaggerWarning,
            btn_tagger_filter=self.btnTaggerFilter, rate_radio_btns=rate_radio_btns,
            widget_history_ctrl=self.widgetTagRateHistoryCtrl, widget_edit_ctrl=self.widgetTagRateEditCtrl,
            btn_export_save=self.btnExportSave
        )

        actions = {
            'play': self.actionPlayFile, 'open_folder': self.actionOpenFolder, 'show_log': self.actionShowLog,
            'postpone': self.actionStatePostpone, 'resume': self.actionStateResume, 'reset': self.actionStateReset,
            'cancel': self.actionStateCancel, 'move_top': self.actionMoveTop, 'move_bottom': self.actionMoveBottom,
            'edit_db': self.actionEditDBEntry
        }

        self.queueManager = QueueManager(
            parent_widget=self, config=self.config, jobs_db=self.jobs, logger=self.log,
            file_hash_service=self.fileHashService, power_manager=self.powerManager, log_ui=self.logUi,
            show_msg_box_fn=self.showMsgBox, table_queue=self.tableQueue, btn_queue_up=self.btnQueueUp,
            btn_queue_down=self.btnQueueDown, btn_queue_pause=self.btnQueuePause, btn_queue_kill=self.btnQueueKill,
            btn_queue_load=self.btnQueueLoad, btn_queue_delete=self.btnQueueDelete,
            btn_queue_delete_all=self.btnQueueDeleteAll, progress_bar_render=self.progressBarRender,
            widget_render_details=self.widgetRenderDetails, label_fps=self.labelRenderFPS,
            label_speed=self.labelRenderSpeed, label_size=self.labelRenderSize, label_time=self.labelRenderTime,
            actions=actions, is_same_render_fn=self.isSameRenderSrcTgt,
            is_sections_missing_fn=self.isSectionsMissing, edit_db_entry_cb=self.onQueueCtxActionEditDBEntry
        )

    def initGui(self):
        self.toolTipBtnExportSave = self.btnExportSave.toolTip()
        self.queueManager.reset_render_details()

        # GUI elements options
        header = self.tableSections.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setMaximumSectionSize(10)

        header = self.tableQueue.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

        # Set GUI from config
        self.updateDirs(self.config.getTargetDirs())
        self.cmbTgtDirs.setCurrentText(self.config.getAppTgtDirName())
        self.btnTgtFileAutoIncrement.setChecked(self.config.getAppIncrementFilename())
        self.btnSectionAutoRemove.setChecked(self.config.getSectionsAutoRemove())
        self.btnFiltersPreview.setChecked(self.config.getFiltersPreview())
        self.filterManager.set_btn_filters_preview_icon()

        current_v_codec = self.config.getRenderVideoCodec()
        if current_v_codec not in CODEC_SPECS:
            current_v_codec = 'libsvtav1'

        self.spinBoxCRF.setValue(self.config.getRenderCRF())
        self.comboBoxContainer.setCurrentText(self.config.getRenderContainer())
        self.comboBoxAudioCodec.setCurrentText(self.config.getRenderAudioCodec())
        self.spinBoxAudioBitrate.setValue(self.config.getRenderAudioBitrate())
        self.comboBoxVideoCodec.setCurrentText(current_v_codec)
        self.onVideoCodecChanged(current_v_codec)

        # Tagger / Database Init
        self.taggerManager.init_tagger()
        self.taggerManager.check_db_connectivity()

        # Queue Jobs Initialization
        waitingJobs = False
        if self.jobs.jobs:
            for job in self.jobs.get_sorted_jobs():
                state = job.getState()
                if state == 0:
                    waitingJobs = True
                elif state == 4:
                    job.setLog('Job had state "Rendering" when the program started.')
                    job.setState(3)
                    state = 3
                elif state == 5:
                    job.setLog('Job had state "Paused" when the program started.')
                    job.setState(3)
                    state = 3
                self.queueManager.queue_add_row(job.getID(), job.getTgtFileNameLong(), self.queueManager.get_job_state_string(state))
        else:
            self.deleteDeshakeDir()

        self.queueManager.set_btn_queue_delete_all_state()

        if self.config.getQueueIsPaused() or (waitingJobs and self.config.getAppPauseQueueOnStartWhenWaitingJobs()):
            self.btnQueuePause.setChecked(True)
            self.queueManager.toggle_queue_pause()
        elif waitingJobs and not self.btnQueuePause.isChecked():
            self.queueManager.run_next_wait_job()

        self.tableQueue.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tableQueue.customContextMenuRequested.connect(self.queueManager.on_queue_context_menu)

        self.sectionsManager.set_btn_section_add_state()

    def initShortcuts(self):
        self.scPause = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.scFrameStep = QShortcut(QKeySequence(Qt.Key.Key_PageDown), self)
        self.scFrameStepBack = QShortcut(QKeySequence(Qt.Key.Key_PageUp), self)
        self.scMute = QShortcut(QKeySequence(Qt.Key.Key_M), self)
        self.scSeekSmall = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        self.scSeekMedium = QShortcut(QKeySequence(Qt.Key.Key_Right | Qt.KeyboardModifier.ShiftModifier), self)
        self.scSeekSmallBack = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        self.scSeekMediumBack = QShortcut(QKeySequence(Qt.Key.Key_Left | Qt.KeyboardModifier.ShiftModifier), self)
        self.scSectionStart = QShortcut(QKeySequence(Qt.Key.Key_Home), self)
        self.scSectionEnd = QShortcut(QKeySequence(Qt.Key.Key_End), self)
        self.scSectionAdd1 = QShortcut(QKeySequence(Qt.Key.Key_Plus), self)
        self.scSectionAdd2 = QShortcut(QKeySequence(Qt.Key.Key_ScrollLock), self)
        self.scExportSave = QShortcut(QKeySequence("Ctrl+S"), self)
        self.scExportSave2 = QShortcut(QKeySequence(Qt.Key.Key_F9), self)

        all_shortcuts = [
            self.scPause, self.scFrameStep, self.scFrameStepBack, self.scMute,
            self.scSeekSmall, self.scSeekMedium, self.scSeekSmallBack, self.scSeekMediumBack,
            self.scSectionStart, self.scSectionEnd, self.scSectionAdd1, self.scSectionAdd2,
            self.scExportSave, self.scExportSave2
        ]
        for sc in all_shortcuts:
            sc.setContext(Qt.ShortcutContext.ApplicationShortcut)

    def initGuiEvents(self):
        try:
            # Connect Dynamic Actions
            self.actionEditDBEntry.triggered.connect(self.onQueueCtxActionEditDBEntry)
            self.actionStateCancel.triggered.connect(self.queueManager.on_queue_ctx_action_cancel_job)

            # Player Control
            self.btnPause.clicked.connect(self.playerManager.toggle_pause)
            self.scPause.activated.connect(self.playerManager.toggle_pause)
            self.btnFrameStep.clicked.connect(self.playerManager.frame_step_forward)
            self.scFrameStep.activated.connect(self.playerManager.frame_step_forward)
            self.btnFrameStepBack.clicked.connect(self.playerManager.frame_step_backward)
            self.scFrameStepBack.activated.connect(self.playerManager.frame_step_backward)

            self.btnSectionStart.clicked.connect(lambda: self.sectionsManager.set_current_section_start(self.playerManager.playerTimeCurrent, self.videoProps))
            self.scSectionStart.activated.connect(lambda: self.sectionsManager.set_current_section_start(self.playerManager.playerTimeCurrent, self.videoProps))
            self.btnSectionEnd.clicked.connect(lambda: self.sectionsManager.set_current_section_end(self.playerManager.playerTimeCurrent, self.videoProps))
            self.scSectionEnd.activated.connect(lambda: self.sectionsManager.set_current_section_end(self.playerManager.playerTimeCurrent, self.videoProps))

            self.btnSectionAdd1.clicked.connect(self.sectionsManager.on_btn_section_add_clicked)
            self.scSectionAdd1.activated.connect(self.sectionsManager.on_btn_section_add_clicked)
            self.scSectionAdd2.activated.connect(self.sectionsManager.on_btn_section_add_clicked)

            self.btnMute.clicked.connect(self.onBtnMuteClicked)
            self.scMute.activated.connect(self.onBtnMuteClicked)
            self.sliderVolume.valueChanged.connect(self.onSliderVolumeChange)

            self.scSeekSmall.activated.connect(lambda: self.playerManager.sanitize_seek(2.0, self.videoProps))
            self.scSeekMedium.activated.connect(lambda: self.playerManager.sanitize_seek(10.0, self.videoProps))
            self.scSeekSmallBack.activated.connect(lambda: self.playerManager.sanitize_seek(-2.0, self.videoProps))
            self.scSeekMediumBack.activated.connect(lambda: self.playerManager.sanitize_seek(-10.0, self.videoProps))

            self.renderFrame.wheelEvent = self.renderFrameWheelEvent
            self.sliderPlayer.valueChanged.connect(self.onSliderPlayerValueChanged)

            # Sections
            self.tableSections.currentCellChanged.connect(self.sectionsManager.on_table_section_curr_cell_changed)
            self.tableSections.itemDoubleClicked.connect(self.sectionsManager.on_table_section_item_dbl_clicked)
            self.btnSectionAdd2.clicked.connect(self.sectionsManager.on_btn_section_add_clicked)
            self.btnSectionDelete.clicked.connect(self.sectionsManager.on_btn_section_delete_clicked)
            self.btnSectionUp.clicked.connect(self.sectionsManager.on_btn_section_up_clicked)
            self.btnSectionDown.clicked.connect(self.sectionsManager.on_btn_section_down_clicked)
            self.btnCurrentSectionStart.clicked.connect(lambda: self.sectionsManager.on_btn_current_section_start_clicked(self.playerManager.playerTimeCurrent))
            self.btnCurrentSectionEnd.clicked.connect(lambda: self.sectionsManager.on_btn_current_section_end_clicked(self.playerManager.playerTimeCurrent))
            self.btnSectionAutoRemove.clicked.connect(self.sectionsManager.on_btn_section_auto_remove_clicked)

            # Job Finalization
            self.lineEditTgtFileName.textChanged.connect(self.onLineEditTgtFileNameChanged)
            self.boxTgtFileCount.valueChanged.connect(self.onBoxFileCountChanged)
            self.btnExportSave.clicked.connect(self.onBtnExportSave)
            self.scExportSave.activated.connect(self.onBtnExportSave)
            self.scExportSave2.activated.connect(self.onBtnExportSave)
            self.btnTgtFileAutoIncrement.clicked.connect(self.onBtnTgtFileAutoIncrement)
            self.btnExportDirs.clicked.connect(self.onBtnExportDirsClicked)
            self.cmbTgtDirs.currentTextChanged.connect(self.onCmbTgtDirsCurrTextChanged)

            # Filters
            self.btnFilterCrop.clicked.connect(lambda: self.filterManager.on_btn_filter_crop_clicked(self.videoProps))
            self.btnFilterCrop.toggled.connect(lambda: self.filterManager.on_btn_filter_crop_clicked(self.videoProps))
            self.boxFilterCropT.valueChanged.connect(lambda val: self.filterManager.on_box_filter_crop_changed('t', val, self.videoProps))
            self.boxFilterCropR.valueChanged.connect(lambda val: self.filterManager.on_box_filter_crop_changed('r', val, self.videoProps))
            self.boxFilterCropB.valueChanged.connect(lambda val: self.filterManager.on_box_filter_crop_changed('b', val, self.videoProps))
            self.boxFilterCropL.valueChanged.connect(lambda val: self.filterManager.on_box_filter_crop_changed('l', val, self.videoProps))
            self.btnAutoCrop.clicked.connect(lambda: self.filterManager.on_btn_filter_auto_crop_clicked(self.playerManager.playerTimeCurrent, self.videoProps))

            self.btnFilterDeinterlace.toggled.connect(lambda: self.filterManager.on_btn_filter_deinterlace_clicked(self.videoProps))
            self.comboBoxFilterDeinterlaceDeinterlacer.currentTextChanged.connect(lambda text: self.filterManager.on_combobox_deinterlacer_changed(text, self.videoProps))

            self.btnFilterResize.clicked.connect(lambda: self.filterManager.on_btn_filter_resize_clicked(self.videoProps))
            self.btnFilterResize.toggled.connect(lambda: self.filterManager.on_btn_filter_resize_clicked(self.videoProps))
            self.boxFilterResizeW.valueChanged.connect(lambda val: self.filterManager.on_box_filter_resize_w_changed(val, self.videoProps))
            self.boxFilterResizeH.valueChanged.connect(lambda val: self.filterManager.on_box_filter_resize_h_changed(val, self.videoProps))
            self.btnFilterResize169.clicked.connect(self.filterManager.on_btn_filter_resize_169)
            self.btnFilterResize43.clicked.connect(self.filterManager.on_btn_filter_resize_43)

            self.btnFilterDeshake.clicked.connect(self.filterManager.on_btn_filter_deshake_clicked)
            self.btnFilterDeshake.toggled.connect(self.filterManager.on_btn_filter_deshake_clicked)

            self.btnFilterRotateLeft.clicked.connect(lambda: self.filterManager.on_btn_filter_rotate_left(self.videoProps))
            self.btnFilterRotateRight.clicked.connect(lambda: self.filterManager.on_btn_filter_rotate_right(self.videoProps))
            self.btnFilterRotate180.clicked.connect(lambda: self.filterManager.on_btn_filter_rotate_180(self.videoProps))

            self.btnFiltersPreview.clicked.connect(lambda: self.filterManager.on_btn_filters_preview(self.videoProps))
            self.btnFiltersKeep.clicked.connect(lambda: None)
            self.btnFiltersReset.clicked.connect(self.filterManager.reset_filters)

            # Filter Up/Down Grid Reordering
            self.btnFilterCropDown.clicked.connect(lambda: self.onFilterGridRowMove('crop', True))
            self.btnFilterCropUp.clicked.connect(lambda: self.onFilterGridRowMove('crop', False))
            self.btnFilterDeinterlaceDown.clicked.connect(lambda: self.onFilterGridRowMove('deinterlace', True))
            self.btnFilterDeinterlaceUp.clicked.connect(lambda: self.onFilterGridRowMove('deinterlace', False))
            self.btnFilterResizeDown.clicked.connect(lambda: self.onFilterGridRowMove('resize', True))
            self.btnFilterResizeUp.clicked.connect(lambda: self.onFilterGridRowMove('resize', False))
            self.btnFilterRotateDown.clicked.connect(lambda: self.onFilterGridRowMove('rotate', True))
            self.btnFilterRotateUp.clicked.connect(lambda: self.onFilterGridRowMove('rotate', False))
            self.btnFilterDeshakeDown.clicked.connect(lambda: self.onFilterGridRowMove('deshake', True))
            self.btnFilterDeshakeUp.clicked.connect(lambda: self.onFilterGridRowMove('deshake', False))

            # Queue Events
            self.tableQueue.selectionModel().selectionChanged.connect(self.queueManager.set_queue_btn_states)
            self.tableQueue.cellDoubleClicked.connect(self.onTableQueueCellDblClicked)
            self.tableQueue.cellChanged.connect(lambda iRow, iCol: self.queueManager.set_btn_queue_delete_all_state() if iCol == 2 else None)

            self.btnQueueDelete.clicked.connect(self.queueManager.queue_delete_selected_rows)
            self.btnQueueUp.clicked.connect(lambda: self.queueManager.move_selected_jobs(-1))
            self.btnQueueDown.clicked.connect(lambda: self.queueManager.move_selected_jobs(1))
            self.btnQueuePause.clicked.connect(self.queueManager.toggle_queue_pause)
            self.btnQueueKill.clicked.connect(self.queueManager.cancel_current_job)
            self.btnQueueLoad.clicked.connect(lambda: self.newFile(False))
            self.btnQueueDeleteAll.clicked.connect(self.queueManager.queue_remove_finished_rows)
            self.btnQueueSleep.clicked.connect(lambda state: self.powerManager.toggle_power_mode('sleep', state))
            self.btnQueueShutdown.clicked.connect(lambda state: self.powerManager.toggle_power_mode('shutdown', state))

            # Actions / Menu
            self.actionSettings.triggered.connect(self.onActionSettings)
            self.actionQuit.triggered.connect(self.onActionQuit)
            self.actionOpenAppDir.triggered.connect(self.onActionOpenAppDir)
            self.actionOpenAppData.triggered.connect(self.onActionOpenAppData)
            self.actionRestorePanels.triggered.connect(self.onActionRestorePanels)
            self.actionPlayFile.triggered.connect(self.queueManager.on_queue_ctx_action_play_file)
            self.actionOpenFolder.triggered.connect(self.queueManager.on_queue_ctx_action_open_folder)
            self.actionMoveTop.triggered.connect(self.queueManager.on_queue_ctx_action_move_top_multi)
            self.actionMoveBottom.triggered.connect(self.queueManager.on_queue_ctx_action_move_bottom_multi)
            self.actionStatePostpone.triggered.connect(self.queueManager.on_queue_ctx_action_state_postpone)
            self.actionStateResume.triggered.connect(self.queueManager.on_queue_ctx_action_state_resume)
            self.actionStateReset.triggered.connect(self.queueManager.on_queue_ctx_action_state_reset)
            self.actionShowLog.triggered.connect(self.queueManager.on_queue_ctx_action_show_log)

            # Tagger Events
            self.btnTagRateHistorySave.clicked.connect(lambda: self.taggerManager.on_btn_tag_rate_history_save_clicked(self.videoProps, self.setBtnExportSaveState))
            self.listWidgetLastTags.itemClicked.connect(self.taggerManager.on_list_widget_last_tags_item_clicked)
            self.btnTagsLast.clicked.connect(self.taggerManager.on_btn_tags_last_clicked)
            self.btnTagsClear.clicked.connect(self.taggerManager.on_btn_tags_clear_clicked)
            self.btnTaggerActive.clicked.connect(self.taggerManager.on_btn_tagger_active_clicked)
            self.btnTaggerWarning.clicked.connect(self.taggerManager.on_btn_tagger_warning_clicked)
            self.btnTaggerFilter.clicked.connect(self.onBtnTaggerFilterClicked)
            self.btnLastRating.clicked.connect(self.taggerManager.on_btn_last_rating_clicked)

            # Render Controls Events
            self.comboBoxVideoCodec.currentTextChanged.connect(self.onVideoCodecChanged)
            self.spinBoxCRF.valueChanged.connect(lambda val: self.config.setRenderCRF(val))
            self.comboBoxContainer.currentTextChanged.connect(lambda text: self.config.setRenderContainer(text))
            self.comboBoxPreset.currentIndexChanged.connect(self.onPresetChanged)
            self.comboBoxAudioCodec.currentTextChanged.connect(lambda text: self.config.setRenderAudioCodec(text))
            self.spinBoxAudioBitrate.valueChanged.connect(lambda val: self.config.setRenderAudioBitrate(val))

        except Exception as e:
            msg = 'Error: Cannot set all GUI events.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            self.showMsgBox(msg, infoText='Exit application', detailText=traceback.format_exc(), icon='critical')
            sys.exit(1)

    def onFilterGridRowMove(self, filter_name: str, move_down: bool):
        atts = self.filterManager.filterAtts.get(filter_name)
        if atts:
            idx = self.filterManager.get_index_of_layout_in_filters_grid(atts['layout'])
            self.filterManager.move_row_in_filters_grid(idx, move_down)
            self.filterManager.set_filter_btn_states(self.videoProps)

    def onVideoCodecChanged(self, codec_name: str):
        spec = CodecSpecs.get_spec(codec_name)
        if not spec:
            return

        self.comboBoxVideoCodec.blockSignals(True)
        self.spinBoxCRF.blockSignals(True)
        self.comboBoxPreset.blockSignals(True)

        self.spinBoxCRF.setRange(spec['min_crf'], spec['max_crf'])
        current_crf = self.spinBoxCRF.value()
        if current_crf < spec['min_crf'] or current_crf > spec['max_crf']:
            self.spinBoxCRF.setValue(spec['default_crf'])

        self.comboBoxPreset.clear()
        for val, label in spec['presets']:
            self.comboBoxPreset.addItem(label, userData=val)

        saved_preset = str(self.config.getRenderPreset())
        preset_idx = self.comboBoxPreset.findData(saved_preset)
        if preset_idx != -1:
            self.comboBoxPreset.setCurrentIndex(preset_idx)
        else:
            default_idx = self.comboBoxPreset.findData(spec['default_preset'])
            if default_idx != -1:
                self.comboBoxPreset.setCurrentIndex(default_idx)

        self.config.setRenderVideoCodec(codec_name)
        self.config.setRenderCRF(self.spinBoxCRF.value())
        selected_preset = self.comboBoxPreset.currentData()
        if selected_preset:
            self.config.setRenderPreset(selected_preset)

        self.comboBoxVideoCodec.blockSignals(False)
        self.spinBoxCRF.blockSignals(False)
        self.comboBoxPreset.blockSignals(False)

    def onPresetChanged(self, index: int):
        preset_data = self.comboBoxPreset.currentData()
        if preset_data:
            self.config.setRenderPreset(str(preset_data))

    def showEvent(self, event):
        super(MainUi, self).showEvent(event)
        if self.is_first_show:
            self.restore_layout_state()
            self.is_first_show = False

    def restore_layout_state(self):
        try:
            geometry = self.config.getAppGeometry()
            if geometry:
                self.restoreGeometry(geometry)
            state = self.config.getAppState()
            if state:
                self.restoreState(state)
        except Exception as e:
            self.log(1, "Could not restore layout state.", 1, traceback=traceback.format_exc())

    def newFile(self, videoFilePath=False):
        """Loads a video file as new current job into PyCutXn."""
        try:
            self.log(1, '---New File-----------------------------------')
            self.log(3, '---New File -----------------------------------')
            self.cropOverlay.stop_interaction()

            if self.playerManager:
                self.playerManager.reset_canvas()

            self.taggerManager.check_db_connectivity()

            if not videoFilePath:
                self.log(1, 'Loading job from queue ...')
                job_id, _ = self.queueManager.queue_get_job_id_from_row()
                self.jobs.new_current_job(False, self.jobs.get_job(job_id))
                job = self.jobs.get_current_job()
                videoFilePath = job.getSrcFilePathLong()
                self.taggerManager.set_tags_and_rating_to_tree(False)
                self.loadTargetDirName(job)
                self.taggerManager.set_history_mode(True, self.setBtnExportSaveState)
            else:
                self.log(1, 'Init new job from file ...')
                self.jobs.new_current_job(videoFilePath)
                job = self.jobs.get_current_job()
                self.setCurrTgtDir()

            prevFilters = self.jobs.get_current_job().getFilters()
            self.setWindowTitle('%s (%s) - pyCutXn' % (job.getSrcFileNameLong(), job.getSrcDirName()))
            self.log(1, 'Source path: "%s".' % videoFilePath)

            # Probing video properties
            self.videoProps, codecInfo = Functions.getVideoPropertiesAndCodecInfo(videoFilePath)
            self.videoProps['durationMs'] = Functions.HMSToTimestamp(self.videoProps.get('durationHMS'), True)
            self.plainTextEditCodecInfo.setPlainText(codecInfo)
            self.showWarningForOddVideoSourceSize(self.videoProps)
            self.log(1, 'Video properties: %s' % self.videoProps)

            # Set properties & filters
            if self.btnFiltersKeep.isChecked() and prevFilters:
                job.setFilters(prevFilters)

            self.filterManager.load_all_filters(job, self.videoProps)
            self.loadTargetFileName(job)
            self.loadTargetFileCount(job)

            self.sectionsManager.load_sections(job, self.videoProps)

            if self.videoProps:
                self.playerManager.load_video_file(
                    videoFilePath,
                    self.sectionsManager.sectionTimeStart,
                    self.videoProps
                )

            self.handleKnownWarnings(job)
        except Exception as e:
            msg = 'Error: Cannot load new file.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            self.showMsgBox(msg, detailText=traceback.format_exc(), icon='critical')

    def saveSession(self):
        """Saves current job session as new job and into DB."""
        try:
            if self.taggerManager.historyMode:
                return False
            self.log(1, 'Saving current session ...')
            if not self.taggerManager.warn_when_no_tags_or_rating():
                self.log(1, 'Saving aborted by user.')
                return False

            currentJob = self.jobs.get_current_job()
            currentJob.setTgtFileExt('.%s' % self.config.getRenderContainer())
            currentJob.setRenderSettingVideoCodec(self.config.getRenderVideoCodec())
            currentJob.setRenderSettingCRF(self.config.getRenderCRF())
            currentJob.setRenderSettingPreset(self.config.getRenderPreset())
            currentJob.setRenderSettingAudioCodec(self.config.getRenderAudioCodec())
            currentJob.setRenderSettingAudioBitrate(self.config.getRenderAudioBitrate())
            currentJob.setRenderSettingContainer(self.config.getRenderContainer())

            if self.isSameRenderSrcTgt(currentJob, False):
                return False

            if self.isTgtFileExistsInTgtDirWarningActive():
                if not self.overwriteTgtFileIfExists(currentJob):
                    return False

            if self.isTgtFileExistsInJobsWarningActive():
                if not self.overwriteTgtFileIfExistsInQueue(currentJob):
                    return False

            job = self.addCurrentJobToQueue()
            if not job:
                return False

            if not self.taggerManager.save_current_tags_and_rating(self.videoProps):
                return False

            if self.btnTgtFileAutoIncrement.isChecked():
                self.changeTargetFileCount(1)

            if self.btnSectionAutoRemove.isChecked():
                self.sectionsManager.clear_sections(clearCurrentJob=True, clearCurrentSection=False, video_props=self.videoProps)

            self.log(1, 'Session saved as new job in queue.')
        except Exception as e:
            msg = 'Error: Cannot save current session as new job in queue.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            self.showMsgBox(msg, detailText=traceback.format_exc(), icon='critical')
            return False

    def addCurrentJobToQueue(self):
        """Adds current session as new job to queue."""
        try:
            job = False
            try:
                job = self.jobs.save_current_job()
                if not job:
                    raise Exception("Failed to save job to database.")

                if not job.getSections() and self.config.getSectionsAutoCreate():
                    if not self.sectionsManager.auto_create_section_for_job(job, self.videoProps):
                        return False

                state = job.getState()
                self.queueManager.queue_add_row(
                    job.getID(), job.getTgtFileNameLong(), self.queueManager.get_job_state_string(state)
                )
                self.queueManager.run_next_wait_job()
            except Exception as e:
                msg = 'Error: Cannot add session to job queue.'
                self.log(1, msg, 1)
                self.showMsgBox(msg, detailText=str(e), icon='critical')
            return job
        except Exception as e:
            raise Exception(traceback.format_exc())

    def isSameRenderSrcTgt(self, job, isTask=False) -> bool:
        try:
            if Functions.isSameString(job.getSrcFilePathLong(), job.getTgtFilePathLong()):
                msg = 'Error: Input and Output Path are the same.'
                self.log(1, msg, 1)
                self.queueManager.on_ffmpeg_exit([job, -100, msg, False, False])
                if not isTask:
                    self.showMsgBox(msg, btns="ok", icon="critical")
                return True
            return False
        except Exception as e:
            raise Exception(e)

    def isSectionsMissing(self, job, isTask=False) -> bool:
        try:
            if len(job.getSections()) == 0:
                msg = 'Error: No sections to render.'
                self.log(1, msg, 1)
                self.queueManager.on_ffmpeg_exit([job, -101, msg, False, False])
                if not isTask:
                    self.showMsgBox(msg, btns="ok", icon="critical")
                return True
            return False
        except Exception as e:
            raise Exception(e)

    def handleKnownWarnings(self, job):
        hashID = False
        detailText = ''
        if self.isFileIsKnownWarningIsActive() and self.taggerManager.is_tagger_enabled():
            hashID, dateTime = self.fileHashService.is_job_file_known(job)
            detailText = f'Hash ID: {hashID}, Date: {dateTime}'

        if hashID:
            self.log(1, 'Current source file was already opened in the past. (HashID: "%s", Date: %s)' % (hashID, dateTime))

        if self.isBaseFileExistsInTgtDirWarningActive():
            self.startAsyncTargetDirScan(job, hashID, dateTime, detailText)
        elif hashID:
            self.showWarningForKnownFile(detailText=detailText)

    def startAsyncTargetDirScan(self, job, hashID=False, dateTime=None, detailText=''):
        if self.dirScannerThread and self.dirScannerThread.isRunning():
            self.dirScannerThread.wait(100)

        self.dirScannerThread = TargetDirScannerThread(job, hashID, dateTime, detailText)
        self.dirScannerThread.scanFinished.connect(self.onTargetDirScanFinished)
        self.dirScannerThread.start()

    @pyqtSlot(str, list, object, object, str)
    def onTargetDirScanFinished(self, job_id, matches, hashID, dateTime, detailText):
        current_job = self.jobs.get_current_job()
        if not current_job or current_job.getID() != job_id:
            return

        targetMatches = matches if matches else False

        if hashID and targetMatches:
            self.showWarningForExistingTargetAndKnownFile(detailText=detailText, matches=targetMatches)
        elif hashID:
            self.showWarningForKnownFile(detailText=detailText)
        elif targetMatches:
            self.showWarningForExistingTargetFile(targetMatches)

    def showWarningForKnownFile(self, detailText=''):
        job = self.jobs.get_current_job()
        knownFiles = self.fileHashService.get_file_list_from_job(job)
        w, h = 440, 110
        if knownFiles:
            self.knownUI.setFilesListToKnown(knownFiles)
            self.knownUI.setLabel('The source file is already known and were edited to following the files:')
            w, h = 540, 280
        else:
            self.knownUI.setLabel('The source file is already known but no edits are protocolized.')

        self.knownUI.setIcon('', color='#00FF00')
        self.knownUI.setTitle('Known File')
        if self.playerManager.playerControl:
            self.playerManager.playerControl.pause(True)
        self.knownUI.resize(w, h)
        self.knownUI.exec()

    def showWarningForExistingTargetFile(self, matches):
        self.knownUI.setFilesListToFound(matches)
        self.knownUI.setLabel('The current file\'s basename already exists in the target directory:')
        self.knownUI.setIcon(text='')
        self.knownUI.setTitle('Current file found in target dir')
        if self.playerManager.playerControl:
            self.playerManager.playerControl.pause(True)
        self.knownUI.exec()

    def showWarningForExistingTargetAndKnownFile(self, detailText, matches):
        job = self.jobs.get_current_job()
        knownFiles = self.fileHashService.get_file_list_from_job(job)
        if knownFiles:
            self.knownUI.setFilesListToKnown(knownFiles)
            self.knownUI.setLabel(f"Source file is already known and it's filename exists in target dir.\nDetails: {detailText}")
        else:
            self.knownUI.setLabel('The source file is already known and it\'s filename exists in target dir:')

        if matches:
            self.knownUI.setFilesListToFound(matches)
        self.knownUI.setIcon('', color='#00FF00')
        self.knownUI.setTitle('Known File and Filename exists in target')
        self.knownUI.resize(700, 340)
        if self.playerManager.playerControl:
            self.playerManager.playerControl.pause(True)
        self.knownUI.exec()

    def showWarningForOddVideoSourceSize(self, videoProps):
        heightIsOdd = (videoProps.get('height', 0) % 2 == 1)
        widthIsOdd = (videoProps.get('width', 0) % 2 == 1)
        msg = ''
        if heightIsOdd and widthIsOdd:
            msg = 'Width and height of video source file are odd.'
        elif heightIsOdd:
            msg = 'Height of video source file is odd.'
        elif widthIsOdd:
            msg = 'Width of video source file is odd.'

        if msg != '':
            self.showMsgBox(
                msg,
                infoText='This can lead to encoding errors. Please crop or resize video to even dimensions.\n\nVideo size: %s x %s' % (
                    videoProps.get('width'), videoProps.get('height')
                ),
                icon='warning'
            )

    def overwriteTgtFileIfExists(self, currentJob) -> bool:
        overwrite = True
        tgtFile = currentJob.getTgtFilePathLong()
        if os.path.exists(tgtFile):
            self.log(1, 'Target file already exists.')
            self.overwriteFile = tgtFile
            if not self.showMsgBox(
                'The target file already exists. Overwrite it?',
                btns='yesno', infoText=tgtFile, icon='question',
                extraBtns=(
                    {'text': 'Open target', 'callback': self.onMsgBoxExtraBtnOverwriteFile},
                    {'text': 'Auto-Rename', 'callback': self.onMsgBoxExtraBtnRenameTarget}
                )
            ):
                overwrite = False
                self.log(1, 'User does not want to overwrite target file.')
            else:
                self.log(1, 'User wants to overwrite target file.')
            self.overwriteFile = False
        return overwrite

    def overwriteTgtFileIfExistsInQueue(self, currentJob) -> bool:
        if not self.settingsUI.checkBoxWarnJobQueue.isChecked():
            return True
        overwrite = True
        currTgtFile = currentJob.getTgtFilePathLong()
        jobs = []
        detailText = 'Jobs in queue with target file "%s":' % currTgtFile

        for i in range(self.tableQueue.rowCount()):
            item = self.tableQueue.item(i, 0)
            if not item:
                continue
            try:
                jobID = int(item.text())
            except Exception:
                msg = 'Error: Cannot convert JobID from job queue to integer.'
                self.log(1, msg, 1, traceback=traceback.format_exc())
                return False

            job = self.jobs.get_job(jobID)
            if job and job.getTgtFilePathLong() == currTgtFile:
                jobs.append(job)
                detailText = '%s\nID: %s' % (detailText, jobID)

        if jobs:
            self.jobsToReplace = jobs
            self.log(1, 'Target file already exists in %s previous job(s).' % len(jobs))
            if not self.showMsgBox(
                'The target file already exists in the jobs queue. Save anyways?',
                btns='yesno', infoText=currTgtFile, detailText=detailText, icon='question',
                extraBtns=({'text': 'Delete existing Jobs', 'callback': self.onMsgBoxExtraBtnDeleteJobsWithTgtFile},)
            ):
                overwrite = False
                self.log(1, 'User does not want to overwrite target file.')
            else:
                self.log(1, 'User wants to overwrite target file.')
            self.jobsToReplace = False
        return overwrite

    def autoRenameTargetFilename(self):
        try:
            job = self.jobs.get_current_job()
            originalName = job.getTgtFileName()
            for i in range(1, 1000):
                if os.path.isfile(job.getTgtFilePathLong()):
                    job.setTgtFileName('{f} ({i})'.format(f=originalName, i=i))
                else:
                    self.lineEditTgtFileName.setText(job.getTgtFileName())
                    return
        except Exception as e:
            msg = 'Error: Cannot auto rename target filename.'
            self.log(1, msg, 1, traceback=traceback.format_exc())

    def showMsgBox(self, msg, btns="ok", icon="info", infoText='', detailText='', title='PyCutXn Message', extraBtns=()):
        msgBox = QMessageBox()
        self.lastMsgBox = msgBox
        if icon == "info":
            msgBox.setIcon(QMessageBox.Icon.Information)
        elif icon == "question":
            msgBox.setIcon(QMessageBox.Icon.Question)
        elif icon == "warning":
            msgBox.setIcon(QMessageBox.Icon.Warning)
        elif icon == "critical":
            msgBox.setIcon(QMessageBox.Icon.Critical)

        msgBox.setText(msg)
        if infoText != '':
            msgBox.setInformativeText(infoText)
        msgBox.setWindowTitle(title)
        if detailText != '':
            msgBox.setDetailedText(detailText)

        if btns == 'okcancel':
            msgBox.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        elif btns == 'save':
            msgBox.setStandardButtons(QMessageBox.StandardButton.Save)
        elif btns == 'savecancel':
            msgBox.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel)
        elif btns == 'yesno':
            msgBox.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        elif btns == 'retry':
            msgBox.setStandardButtons(QMessageBox.StandardButton.Retry)
        elif btns == 'retryabort':
            msgBox.setStandardButtons(QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Abort)
        elif btns == 'close':
            msgBox.setStandardButtons(QMessageBox.StandardButton.Close)
        else:
            msgBox.setStandardButtons(QMessageBox.StandardButton.Ok)

        for extraBtn in extraBtns:
            if 'text' in extraBtn:
                btn = msgBox.addButton(extraBtn['text'], QMessageBox.ButtonRole.ActionRole)
                btn.disconnect()
                if 'callback' in extraBtn and extraBtn['callback']:
                    btn.clicked.connect(extraBtn['callback'])

        result = msgBox.exec()
        if result in (QMessageBox.StandardButton.Ok, QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.Save, QMessageBox.StandardButton.Retry):
            return True
        return False

    def loadTargetDirName(self, job):
        if job.getTgtDirName():
            self.setTgtDirByData(job.getTgtDirName())

    def loadTargetFileName(self, job):
        if job.getTgtFileName():
            self.lineEditTgtFileName.setText(job.getTgtFileName())
            self.lineEditTagRateHistoryFile.setText(job.getTgtFileNameLong())

    def loadTargetFileCount(self, job):
        if job.getTgtFileCount():
            self.boxTgtFileCount.setValue(job.getTgtFileCount())
        else:
            self.setTargetFileCount(0)
            if self.btnTgtFileAutoIncrement.isChecked():
                self.setTargetFileCount(1)

    def changeTargetFileCount(self, value: int):
        self.boxTgtFileCount.setValue(self.boxTgtFileCount.value() + value)

    def setTargetFileCount(self, value: int):
        self.boxTgtFileCount.setValue(value)

    def setCurrTgtDir(self):
        path = self.cmbTgtDirs.currentData()
        self.jobs.get_current_job().setTgtDirName(path)

    def setTgtDirByData(self, path):
        if self.cmbTgtDirs.currentData() == path:
            return True
        index = self.cmbTgtDirs.findData(path)
        if index != -1:
            self.cmbTgtDirs.setCurrentIndex(index)
            return True
        msg = 'Error: Cannot set target path to "%s"' % path
        self.log(1, msg, 1)
        self.showMsgBox(msg, btns="ok", icon="warning")
        return False

    def updateDirs(self, dirs: list):
        self.dirs = dirs
        self.config.setAppDirs(dirs)
        currentText = self.cmbTgtDirs.currentText()
        self.cmbTgtDirs.clear()
        for i in range(len(self.dirs)):
            self.cmbTgtDirs.insertItem(i, self.dirs[i][1], userData=self.dirs[i][0])
            if self.dirs[i][1] == currentText:
                self.cmbTgtDirs.setCurrentText(currentText)

    def setBtnExportSaveState(self):
        if len(self.cmbTgtDirs.currentText()) > 0 and len(self.lineEditTgtFileName.text()) > 0 and not self.taggerManager.historyMode:
            if not self.btnExportSave.isEnabled():
                self.btnExportSave.setEnabled(True)
        else:
            if self.btnExportSave.isEnabled():
                self.btnExportSave.setEnabled(False)

    def isTgtFileExistsInTgtDirWarningActive(self):
        return self.config.getAppWarnTgtFileExistsInTgtDir()

    def isTgtFileExistsInJobsWarningActive(self):
        return self.config.getAppWarnFileExistsInJobs()

    def isBaseFileExistsInTgtDirWarningActive(self):
        return self.config.getAppWarnBaseFileExistsInTgtDir()

    def isFileIsKnownWarningIsActive(self):
        return self.config.getAppWarnFileHashExistsInDB()

    def deleteDeshakeDir(self):
        path = self.config.getConfigDeshakePath()
        if path and os.path.isdir(path):
            shutil.rmtree(path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.cropOverlay and self.cropOverlay.isVisible():
            self.cropOverlay.update_geometry()

    def keyPressEvent(self, event):
        if self.isActiveWindow():
            if event.key() in (Qt.Key.Key_ScrollLock, Qt.Key.Key_Plus):
                self.sectionsManager.on_btn_section_add_clicked()
                event.accept()
                return

            if event.key() == Qt.Key.Key_Control and not event.isAutoRepeat():
                if self.btnFilterCrop.isChecked() and self.videoProps:
                    self.cropOverlay.start_interaction()

        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Control and not event.isAutoRepeat():
            if self.cropOverlay.is_cropping_active:
                self.cropOverlay.stop_interaction()
        super().keyReleaseEvent(event)

    def closeEvent(self, event):
        if self.queueManager.ffmpegProcess and self.config.getAppWarnCloseWhileRender():
            if not self.showMsgBox('A job is currently rendering.', infoText='Really quit?', btns='yesno', icon='question'):
                event.ignore()
                return

        if self.queueManager.FFmpegThread and self.queueManager.FFmpegThread.isRunning():
            self.queueManager.cancel_current_job()
            self.queueManager.FFmpegThread.wait(2000)

        self.playerManager.terminate_player()

        self.config.setAppGeometry(self.saveGeometry())
        self.config.setAppState(self.saveState())

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.activateWindow()
        self.raise_()
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            links = [str(url.toLocalFile()) for url in event.mimeData().urls()]
            if links:
                self.newFile(links[0])
        else:
            event.ignore()

    def onBtnMuteClicked(self):
        self.config.setPlayerIsMuted(not self.config.getPlayerIsMuted())
        self.playerManager.set_mute_state(self.config.getPlayerIsMuted())

    def onSliderVolumeChange(self):
        volume = self.sliderVolume.value()
        self.playerManager.playerControl.volume(volume)

    def renderFrameWheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.playerManager.set_volume_slider(+5)
        elif event.angleDelta().y() < 0:
            self.playerManager.set_volume_slider(-5)

    def onSliderPlayerValueChanged(self, value):
        if self.playerManager.is_slider_player_pressed():
            self.playerManager.seek_from_slider(value, self.videoProps)

    def onLineEditTgtFileNameChanged(self, text):
        job = self.jobs.get_current_job()
        if job:
            job.setTgtFileName(text)
        self.setBtnExportSaveState()

    def onBoxFileCountChanged(self, val):
        try:
            job = self.jobs.get_current_job()
            if job:
                job.setTgtFileCount(val)
        except Exception as e:
            msg = 'Error: increase file count.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            self.showMsgBox(msg, detailText=traceback.format_exc(), icon='warning')

    def onBtnExportSave(self):
        self.saveSession()

    def onBtnTgtFileAutoIncrement(self):
        self.config.setAppIncrementFilename(self.btnTgtFileAutoIncrement.isChecked())
        if self.boxTgtFileCount.value() == 0:
            self.changeTargetFileCount(1)

    def onBtnExportDirsClicked(self):
        self.dirsUI.show()

    def onBtnTaggerFilterClicked(self):
        self.tagsFilterUI.show()

    def onCmbTgtDirsCurrTextChanged(self, text):
        self.setCurrTgtDir()
        self.config.setAppTgtDirName(text)
        self.setBtnExportSaveState()
        if self.isBaseFileExistsInTgtDirWarningActive():
            job = self.jobs.get_current_job()
            if job and job.getTgtDirName():
                self.startAsyncTargetDirScan(job)

    def onTableQueueCellDblClicked(self, row, col):
        state = self.queueManager.queue_get_current_state(row)
        if state == 4:
            return
        elif state == 1:
            self.queueManager.on_queue_ctx_action_play_file()
        elif state in (3, 6):
            self.queueManager.on_queue_ctx_action_show_log()

    def onQueueCtxActionEditDBEntry(self):
        if not self.taggerManager.is_tagger_enabled():
            self.showMsgBox('Tagger/DB function is not available.', icon='warning')
            return

        jobID, _ = self.queueManager.queue_get_job_id_from_row()
        job = self.jobs.get_job(jobID)
        if not job:
            return

        dialog = EditDBUI(self, job)
        result = dialog.exec()

        if result == QtWidgets.QDialog.DialogCode.Accepted and self.taggerManager.historyMode:
            currentJob = self.jobs.get_current_job()
            if currentJob and currentJob.getTgtFilePathLong() == job.getTgtFilePathLong():
                self.log(1, "Refreshing Tag & Rate panel to reflect DB changes.")
                self.taggerManager.set_tags_and_rating_to_tree(forSource=False)

    def onActionSettings(self):
        self.settingsUI.show()

    def onActionQuit(self):
        QCoreApplication.quit()

    def onActionOpenAppDir(self):
        opener = Functions.getCurrentSysOpener()
        subprocess.call([opener, self.rootDir])

    def onActionOpenAppData(self):
        opener = Functions.getCurrentSysOpener()
        subprocess.call([opener, self.config.getConfigPath()])

    def onActionRestorePanels(self):
        self.dockExport.show()
        self.dockTagger.show()
        self.dockQueue.show()
        self.dockLogs.show()
        self.dockCodecs.show()

    def onMsgBoxExtraBtnOverwriteFile(self):
        if self.overwriteFile and os.path.isfile(self.overwriteFile):
            opener = Functions.getCurrentSysOpener()
            subprocess.call([opener, self.overwriteFile])

    def onMsgBoxExtraBtnRenameTarget(self):
        self.autoRenameTargetFilename()
        try:
            if hasattr(self, 'lastMsgBox') and self.lastMsgBox:
                self.lastMsgBox.done(1)
            self.saveSession()
        except Exception:
            pass

    def onMsgBoxExtraBtnDeleteJobsWithTgtFile(self):
        if self.jobsToReplace:
            for job in self.jobsToReplace:
                self.queueManager.queue_remove_row_by_job(job)

    def updateTagsFilter(self, tagIDs: list):
        self.taggerManager.update_tags_filter(tagIDs)


app = QtWidgets.QApplication(sys.argv)
window = MainUi()
app.exec()
