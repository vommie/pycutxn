#!/usr/bin/env python3

import sys
import datetime
import json
import subprocess
import os
import signal
import re
import copy
import shutil
import hashlib
import locale

from libs.mpv import *
from libs.mpv import *

from classes.PlayerControl import PlayerControl
from classes.DirsUI import DirsUI
from classes.TagsFilterUI import TagsFilterUI
from classes.SettingsUI import SettingsUI
from classes.LogUi import LogUi
from classes.KnownUI import KnownUI
from classes.Functions import Functions
from classes.Config import Config
from classes.Jobs import Jobs
from classes.FFmpegThread import FFmpegThread
from classes.DB import DB
from classes.PlayerSlider import PlayerSlider

from PyQt5 import uic, QtGui, QtWidgets
from PyQt5.QtWidgets import QListWidgetItem, QShortcut, QLayout, QMessageBox, QTableWidgetItem
from PyQt5.QtCore import Qt, pyqtSlot, QCoreApplication
from PyQt5.QtGui import QFont, QFontDatabase, QKeySequence, QPalette, QColor
import res  # pyrcc5 -o res.py res/res.qrc

import ffmpeg

class MainUi(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        self.rootDir = os.path.dirname(os.path.realpath(__file__))
        _id = QtGui.QFontDatabase.addApplicationFont('%s/res/font_droid_sans_mono_nerd.otf' % self.rootDir) # Init Nerd Fronts Font for Icons
        super(MainUi, self).__init__()
        uic.loadUi('%s/gui/main.ui' % self.rootDir, self)
        self.initMembers()
        self.initGui()
        self.initShortcuts()
        self.initGuiEvents()
        self.initPlayer()
        self.show()

    def initMembers(self):
        self.config = Config()
        self.iconFontName = 'DroidSansMono Nerd Font Mono'
        self.jobsFilePath = self.config.getJobsFilePath()
        try:
            self.jobs = Jobs(self.jobsFilePath)
        except Exception as e:
            msg = 'Error: Cannot initialize jobs.'
            self.log(1, msg, 1)
            self.showMsgBox(msg, detailText=str(e), icon='critical')
        self.jobStates = {
            0: 'Waiting',
            1: 'Finished',
            2: 'Pending',
            3: 'Error',
            4: 'Rendering',
            5: 'Paused'
        }
        self.ffmpegProcess = False
        self.ffmpegKilled = False
        # Init member variables
        self.dirsUI = DirsUI(self)
        self.knownUI = KnownUI(self)
        self.tagsFilterUI = TagsFilterUI(self)
        self.settingsUI = SettingsUI(self)
        self.db = DB(self.config.getTaggerDBPath(), self.log)
        self.labelTaggerError.setHidden(True)
        self.tagsTree = []
        self.lastTagIDs = []
        self.lastRating = 0
        self.logUi = LogUi(self)
        self.timeFormat = '0:00:0.000'
        self.playerTimeCurrent = self.timeFormat
        self.playerTimeCurrentMs = 0
        self.frameStep = False
        self.jobsSwapping = False # Prevents crash when printing progress while jobs in queue getting switched
        self.resetVideoProps()
        self.overwriteFile = False # File path to a target file the current session would overwrite on save
        self.sectionTimeStart = self.timeFormat
        self.sectionTimeEnd = self.timeFormat
        # Filters
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

    def initGui(self):
        geometry = self.config.getAppGeometry()
        if geometry: self.restoreGeometry(geometry)
        state = self.config.getAppState()
        if state: self.restoreState(state)
        # Other
        self.toolTipBtnExportSave = self.btnExportSave.toolTip()
        self.resetRenderDetails()
        # GUI elements options
        header = self.tableSections.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header.setMaximumSectionSize(10)
        header = self.tableQueue.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        # Set GUI from config
        self.updateDirs(self.config.getTargetDirs())
        self.cmbTgtDirs.setCurrentText(self.config.getAppTgtDirName())
        self.btnTgtFileAutoIncrement.setChecked(self.config.getAppIncrementFilename())
        waitingJobs = False
        # Queue Jobs
        if len(self.jobs.jobs.items()) > 1:
            for id, job in self.jobs.jobs.items():
                try:
                    int(id) # Skip 'default' job
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
                    self.queueAddRow(id, job.getTgtFileNameLong(), self.getJobStateString(state))
                except: pass
        else:
            self.deleteDeshakeDir()
        # Handle queue pause
        if self.config.getQueueIsPaused() or (waitingJobs and self.config.getAppPauseQueueOnStartWhenWaitingJobs()):
            self.btnQueuePause.setChecked(True)
            self.toggleQueuePause()
        elif waitingJobs and not self.btnQueuePause.isChecked():
            self.runNextWaitJob()
        self.tableQueue.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tableQueue.customContextMenuRequested.connect(self.onQueueContextMenu)
        self.renderFrame.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.renderFrame.setAttribute(Qt.WA_NativeWindow)
        # Add custom slider to control the player time position
        self.sliderPlayer = PlayerSlider(Qt.Horizontal)
        self.framePlayerProgress.insertWidget(0, self.sliderPlayer)
        self.sliderPlayer.factor = self.config.getPlayerSliderFactor()
        self.sliderPlayer.setMinimum(0)
        self.sliderPlayer.setMaximum(99 * self.sliderPlayer.factor)
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
        self.sliderPlayer.setStyleSheet(self.sliderPlayerstyleTemplate.replace('##BG##', self.sliderPlayerBgColor))
        # Init categories tree
        self.tagsTreeItemPrefix =  ''
        self.tagsTreeSpaceChar = ' '
        self.setTagsTreeStyle()
        # Tagger
        self.setHistoryMode(False)
        self.btnTaggerActive.setChecked(self.config.getTaggerIsActive())
        self.btnTaggerWarning.setChecked(self.config.getTaggerIsWarningActive())

    def initShortcuts(self):
        self.scPause = QShortcut(QKeySequence(Qt.Key_Space), self)
        self.scFrameStep = QShortcut(QKeySequence(Qt.Key_PageDown), self)
        self.scFrameStepBack = QShortcut(QKeySequence(Qt.Key_PageUp), self)
        self.scMute = QShortcut(QKeySequence(Qt.Key_M), self)
        self.scSeekSmall = QShortcut(QKeySequence(Qt.Key_Right), self)
        self.scSeekMedium = QShortcut(QKeySequence(Qt.SHIFT + Qt.Key_Right), self)
        self.scSeekSmallBack = QShortcut(QKeySequence(Qt.Key_Left), self)
        self.scSeekMediumBack = QShortcut(QKeySequence(Qt.SHIFT + Qt.Key_Left), self)
        self.scSectionStart = QShortcut(QKeySequence(Qt.Key_Home), self)
        self.scSectionEnd = QShortcut(QKeySequence(Qt.Key_End), self)
        self.scSectionAdd1 = QShortcut(QKeySequence(Qt.Key_Plus), self)
        self.scSectionAdd2 = QShortcut(QKeySequence(Qt.Key_ScrollLock), self)
        self.scExportSave = QShortcut(QKeySequence(Qt.CTRL + Qt.Key_S), self)
        self.scExportSave2 = QShortcut(QKeySequence(Qt.Key_F9), self)

    def initGuiEvents(self):
        try:
            # Player control
            self.btnPause.clicked.connect(self.onBtnPauseClicked)
            self.scPause.activated.connect(self.onBtnPauseClicked)
            self.btnFrameStep.clicked.connect(self.onBtnFrameStepClicked)
            self.scFrameStep.activated.connect(self.onBtnFrameStepClicked)
            self.btnFrameStepBack.clicked.connect(self.onBtnFrameStepBackClicked)
            self.scFrameStepBack.activated.connect(self.onBtnFrameStepBackClicked)
            self.btnSectionStart.clicked.connect(self.onBtnSectionStartClicked)
            self.scSectionStart.activated.connect(self.onScSectionStart)
            self.btnSectionEnd.clicked.connect(self.onBtnSectionEndClicked)
            self.scSectionEnd.activated.connect(self.onScSectionEnd)
            self.btnSectionAdd1.clicked.connect(self.onBtnSectionAddClicked)
            self.scSectionAdd1.activated.connect(self.onBtnSectionAddClicked)
            self.scSectionAdd2.activated.connect(self.onBtnSectionAddClicked)
            self.btnMute.clicked.connect(self.onBtnMuteClicked)
            self.scMute.activated.connect(self.onBtnMuteClicked)
            self.sliderVolume.valueChanged.connect(self.onSliderVolumeChange)
            self.scSeekSmall.activated.connect(self.onPlayerSeekSmall)
            self.scSeekMedium.activated.connect(self.onPlayerSeekMedium)
            self.scSeekSmallBack.activated.connect(self.onPlayerSeekSmallBack)
            self.scSeekMediumBack.activated.connect(self.onPlayerSeekMediumBack)
            self.renderFrame.wheelEvent = self.renderFrameWheelEvent
            self.sliderPlayer.valueChanged.connect(self.onSliderPlayerValueChanged)
            # Sections
            self.tableSections.currentCellChanged.connect(self.onTableSectionCurrCellChanged)
            self.tableSections.itemDoubleClicked.connect(self.onTableSectionItemDblClicked)
            self.btnSectionAdd2.clicked.connect(self.onBtnSectionAddClicked)
            self.btnSectionDelete.clicked.connect(self.onBtnSectionDeleteClicked)
            self.btnSectionUp.clicked.connect(self.onBtnSectionUpClicked)
            self.btnSectionDown.clicked.connect(self.onBtnSectionDownClicked)
            self.btnCurrentSectionStart.clicked.connect(self.onBtnCurrentSectionStart)
            self.btnCurrentSectionEnd.clicked.connect(self.onBtnCurrentSectionEnd)
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
            self.btnFilterCrop.clicked.connect(self.onBtnFilterCropClicked)
            self.btnFilterCrop.toggled.connect(self.onBtnFilterCropClicked)
            self.boxFilterCropT.valueChanged.connect(self.onBoxFilterCropTChanged)
            self.boxFilterCropR.valueChanged.connect(self.onBoxFilterCropRChanged)
            self.boxFilterCropB.valueChanged.connect(self.onBoxFilterCropBChanged)
            self.boxFilterCropL.valueChanged.connect(self.onBoxFilterCropLChanged)
            self.btnFilterDeinterlace.clicked.connect(self.onBtnFilterDeinterlaceClicked)
            self.btnFilterDeinterlace.toggled.connect(self.onBtnFilterDeinterlaceClicked)
            self.comboBoxFilterDeinterlaceDeinterlacer.currentTextChanged.connect(self.onComboBoxFilterDeinterlaceDeinterlacerChanged)
            self.btnFilterResize.clicked.connect(self.onBtnFilterResizeClicked)
            self.btnFilterResize.toggled.connect(self.onBtnFilterResizeClicked)
            self.boxFilterResizeW.valueChanged.connect(self.onBoxFilterResizeWChanged)
            self.boxFilterResizeH.valueChanged.connect(self.onBoxFilterResizeHChanged)
            self.btnFilterDeshake.clicked.connect(self.onBtnFilterDeshake)
            self.btnFilterDeshake.toggled.connect(self.onBtnFilterDeshake)
            self.btnFilterRotateLeft.clicked.connect(self.onBtnFilterRotateLeft)
            self.btnFilterRotateRight.clicked.connect(self.onBtnFilterRotateRight)
            self.btnFilterRotate180.clicked.connect(self.onBtnFilterRotate180)
            # Filters Up/Down Buttons
            self.btnFilterCropDown.clicked.connect(self.onBtnFilterCropDownClicked)
            self.btnFilterCropUp.clicked.connect(self.onBtnFilterCropUpClicked)
            self.btnFilterDeinterlaceDown.clicked.connect(self.onBtnFilterDeinterlaceDownClicked)
            self.btnFilterDeinterlaceUp.clicked.connect(self.onBtnFilterDeinterlaceUpClicked)
            self.btnFilterResizeDown.clicked.connect(self.onBtnFilterResizeDownClicked)
            self.btnFilterResizeUp.clicked.connect(self.onBtnFilterResizeUpClicked)
            self.btnFilterRotateDown.clicked.connect(self.onBtnFilterRotateDownClicked)
            self.btnFilterRotateUp.clicked.connect(self.onBtnFilterRotateUpClicked)
            self.btnFilterDeshakeDown.clicked.connect(self.onBtnFilterDeshakeDownClicked)
            self.btnFilterDeshakeUp.clicked.connect(self.onBtnFilterDeshakeUpClicked)
            # Queue
            self.tableQueue.currentCellChanged.connect(self.onTableQueueCurrCellChanged)
            self.tableQueue.cellDoubleClicked.connect(self.onTableQueueCellDblClicked)
            self.btnQueueDelete.clicked.connect(self.onBtnQueueDeleteClicked)
            self.btnQueueUp.clicked.connect(self.onBtnQueueUpClicked)
            self.btnQueueDown.clicked.connect(self.onBtnQueueDownClicked)
            self.btnQueuePause.clicked.connect(self.onBtnQueuePauseClicked)
            self.btnQueueKill.clicked.connect(self.onBtnQueueKillClicked)
            self.btnQueueLoad.clicked.connect(self.onBtnQueueLoadClicked)
            # Actions
            self.actionSettings.triggered.connect(self.onActionSettings)
            self.actionQuit.triggered.connect(self.onActionQuit)
            self.actionPlayFile.triggered.connect(self.onQueueCtxActionPlayFile)
            self.actionOpenFolder.triggered.connect(self.onQueueCtxActionOpenFolder)
            self.actionStatePostpone.triggered.connect(self.onQueueCtxActionStatePostpone)
            self.actionStateResume.triggered.connect(self.onQueueCtxActioStateResume)
            self.actionStateReset.triggered.connect(self.onQueueCtxActioStateReset)
            self.actionShowLog.triggered.connect(self.onQueueCtxActionShowLog)
            # Tagger
            self.btnTagRateHistorySave.clicked.connect(self.onBtnTagRateHistorySaveClicked)
            self.listWidgetLastTags.itemClicked.connect(self.onListWidgetLastTagsItemClicked)
            self.btnTagsLast.clicked.connect(self.onBtnTagsLastClicked)
            self.btnTagsLast.clicked.connect(self.onBtnTagsLastClicked)
            self.btnTagsClear.clicked.connect(self.onBtnTagsClearClicked)
            self.btnTaggerActive.clicked.connect(self.onBtnTaggerActiveClicked)
            self.btnTaggerWarning.clicked.connect(self.onBtnTaggerWarningClicked)
            self.btnTaggerFilter.clicked.connect(self.onBtnTaggerFilterClicked)
        except Exception as e:
            msg = 'Error: Cannot set all GUI events.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            self.showMsgBox(msg, infoText='Exit application', detailText=traceback.format_exc(), icon='critical')
            exit(1)

    def initPlayer(self):
        try:
            self.renderFrame.setAttribute(Qt.WA_DontCreateNativeAncestors)
            self.renderFrame.setAttribute(Qt.WA_NativeWindow)
            locale.setlocale(locale.LC_NUMERIC, 'C')
            player = MPV(wid=str(int(self.renderFrame.winId())), vo='x11', log_handler=print, loglevel='fatal', keep_open='yes')
            self.playerControl = PlayerControl(player, self.config)
            self.playerControl.volume(self.config.getPlayerVolume())
            self.setMuteState(self.config.getPlayerIsMuted())
            # Register observers
            self.playerControl.player.observe_property('pause', self.onPlayerPause)
            self.playerControl.player.observe_property('time-pos', self.onPlayerTimePos)
            self.playerControl.player.observe_property('volume', self.onPlayerVolume)
        except Exception as e:
            msg = 'Error: Cannot initialize the video player.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            self.showMsgBox(msg, detailText=traceback.format_exc(), icon='critical')
            exit(1)

    def newFile(self, videoFilePath = False):
        '''
        Loads a file as new curent job into PyCut. (Re)sets the GUI.

        :param videoFilePath: The path to the video file to open. If not set, the currently selected job in the queue gets loaded.
        '''
        try:
            self.log(1, '---New File-----------------------------------')
            self.log(3, '---New File -----------------------------------')
            self.playerControl.pause(True)
            self.checkDBConnectivity()
            if not videoFilePath:
                self.log(1, 'Loading job from queue ...')
                self.jobs.newCurrentJob(False, self.jobs.getJob(self.queueGetJobIDFromRow()[0]))
                job = self.jobs.getCurrentJob()
                self.setTagsAndRatingToTree(False)
                self.loadTargetDirName(job)
                self.setHistoryMode(True)
            else:
                self.log(1, 'Init new job from file ...')
                self.jobs.newCurrentJob(videoFilePath)
                job = self.jobs.getCurrentJob()
                self.setCurrTgtDir()
                self.showWarningForKnownFile()
            if not videoFilePath: videoFilePath = job.getSrcFilePathLong()
            self.setWindowTitle('%s (%s) - pyCut' % (job.getSrcFileNameLong(), job.getSrcDirName()))
            self.log(1, 'Source path: "%s".' % videoFilePath)
            # Get Video Props
            self.videoProps = Functions.getVideoProperties(videoFilePath)
            self.videoProps['durationMs'] = Functions.HMSToTimestamp(self.videoProps.get('durationHMS'), True)
            self.showWarningForOddVideoSourceSize(self.videoProps)
            self.log(1, 'Video properties: %s' % self.videoProps)
            # Set properties
            self.loadFilterCrop(job)
            self.loadFilterDeinterlace(job)
            self.loadFilterRotate(job)
            self.loadFilterResize(job)
            self.loadFilterDeshake(job)
            self.loadFilterPositions(job)
            self.loadTargetFileName(job)
            self.loadTargetFileCount(job)
            self.playerTimeCurrent = self.timeFormat
            self.setSliderPlayerPosFromTimestamp(0)
            self.setLabelPlayerTimeCurr(self.timeFormat)
            self.setFilterBtnStates()
            self.loadSections(job)
            # Load video file
            if self.videoProps:
                audioFilter='lavfi=[dynaudnorm=s=30]'
                audioFilter = ''
                audioFilter='lavfi=[loudnorm=I=-16:TP=-3:LRA=4]'
                audioFilter='lavfi=[dynaudnorm=g=5:f=250:r=0.9:p=0.5]'
                audioFilter='lavfi=[loudnorm=I=-22:TP=-1.5:LRA=2]' # Works
                self.playerControl.player.loadfile(videoFilePath, 'replace', start=self.sectionTimeStart, af=audioFilter)
                if not self.config.getPlayerAutoPlay(): self.playerControl.pause(True)
                else:  self.playerControl.pause(False)
                self.setPlayerControlsState(True)
        except Exception as e:
            msg = 'Error: Cannot load new file.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            self.showMsgBox(msg, detailText=traceback.format_exc(), icon='critical')
            # TODO: Reset GUI / reset to defaultjob

    def loadFilterCrop(self, job):
        try:
            state = job.getFilterCropState()
            if not state:
                self.resetCropFilter()
            else:
                self.btnFilterCrop.setChecked(True)
                value = job.getFilterCropT()
                if value: self.boxFilterCropT.setValue(value)
                else: self.boxFilterCropT.setValue(0)
                value = job.getFilterCropR()
                if value: self.boxFilterCropR.setValue(value)
                else: self.boxFilterCropR.setValue(0)
                value = job.getFilterCropB()
                if value: self.boxFilterCropB.setValue(value)
                else: self.boxFilterCropB.setValue(0)
                value = job.getFilterCropL()
                if value: self.boxFilterCropL.setValue(value)
                else: self.boxFilterCropL.setValue(0)
        except Exception as e:
            msg = 'Error: Cannot load crop filter from job.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            self.showMsgBox(msg, detailText=traceback.format_exc(), icon='warning')

    def loadFilterDeinterlace(self, job):
        try:
            state = job.getFilterDeinterlaceState()
            if not state: self.resetDeinterlaceFilter()
            if state:
                self.btnFilterDeinterlace.setChecked(True)
            deinterlacer = job.getFilterDeinterlaceDeinterlacer()
            self.comboBoxFilterDeinterlaceDeinterlacer.setCurrentText(deinterlacer)
        except Exception as e:
            msg = 'Error: Cannot load deinterlace filter from job.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            self.showMsgBox(msg, detailText=traceback.format_exc(), icon='warning')

    def loadFilterRotate(self, job):
        try:
            rotation = job.getFilterRotate()
            if not rotation:
                self.resetRotateFilter()
            elif rotation == 90:
                self.btnFilterRotateRight.setChecked(True)
                self.onBtnFilterRotateRight()
            elif rotation == -90:
                self.btnFilterRotateLeft.setChecked(True)
                self.onBtnFilterRotateLeft()
            elif rotation == 180:
                self.btnFilterRotate180.setChecked(True)
                self.onBtnFilterRotate180()
        except Exception as e:
            msg = 'Error: Cannot load rotate filter from job.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            self.showMsgBox(msg, detailText=traceback.format_exc(), icon='warning')

    def loadFilterResize(self, job):
        try:
            state = job.getFilterResizeState()
            if not state: self.resetResizeFilter()
            if state:
                self.btnFilterResize.setChecked(True)
                value = job.getFilterResizeWidth()
                if value: self.boxFilterResizeW.setValue(value)
                else: self.boxFilterResizeW.setValue(0)
                value = job.getFilterResizeHeight()
                if value: self.boxFilterResizeH.setValue(value)
                else: self.boxFilterResizeH.setValue(0)
        except Exception as e:
            msg = 'Error: Cannot load resize filter from job.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            self.showMsgBox(msg, detailText=traceback.format_exc(), icon='warning')

    def loadFilterDeshake(self, job):
        try:
            state = job.getFilterDeshakeState()
            if state: self.btnFilterDeshake.setChecked(True)
            else: self.btnFilterDeshake.setChecked(False)
        except Exception as e:
            msg = 'Error: Cannot load deshake filter from job.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            self.showMsgBox(msg, detailText=traceback.format_exc(), icon='warning')

    def saveSession(self):
        '''
        Saves the current job session as new job and into the database
        '''
        try:
            if(self.historyMode): return False
            self.log(1, 'Saving current session ...')
            if not self.warnWhenNoTagsOrRating():
                self.log(1, 'Saving aborted by user.')
                return False
            currentJob = self.jobs.getCurrentJob()
            currentJob.setTgtFileExt('.%s' % self.config.getRenderContainer())
            currentJob.setRenderSettingVideoCodec(self.config.getRenderVideoCodec())
            currentJob.setRenderSettingCRF(self.config.getRenderCRF())
            currentJob.setRenderSettingPreset(self.config.getRenderPreset())
            currentJob.setRenderSettingAudioCodec(self.config.getRenderAudioCodec())
            currentJob.setRenderSettingAudioBitrate(self.config.getRenderAudioBitrate())
            currentJob.setRenderSettingContainer(self.config.getRenderContainer())
            if self.isSameRenderSrcTgt(currentJob, False): return False
            if not self.overwriteTgtFileIfExists(currentJob): return False
            job = self.addCurrentJobToQueue()
            if not job: return False
            if not self.saveCurrentTagsAndRating(): return False
            if self.btnTgtFileAutoIncrement.isChecked(): self.changeTargetFileCount(1)
            self.log(1, 'Session saved as new job in queue.')
        except Exception as e:
            msg = 'Error: Cannot save current session as new job in queue.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            self.showMsgBox(msg, detailText=traceback.format_exc(), icon='critical')
            return False

    def addCurrentJobToQueue(self):
        '''Adds the current job session as new job to the jobs queue'''
        try:
            job = False
            try:
                id, job = self.jobs.saveCurrentJob()
                if not job.getSections() and self.config.getAppSetAutoSection():
                    if not self.autoCreateSectionForJob(job): return False
                state = job.getState()
                iRow = self.queueAddRow(id, job.getTgtFileNameLong(), self.getJobStateString(state))
                job.setPosition(iRow)
                self.runNextWaitJob()
            except Exception as e:
                msg = 'Error: Cannot add session to job queue.'
                self.log(1, msg, 1)
                self.showMsgBox(msg, detailText=str(e), icon='critical')
            return job
        except Exception as e:
            raise Exception(traceback.format_exc())

    def autoCreateSectionForJob(self, job):
        '''Creates a section for a job if none section is added but a range is selected'''
        try:
            if self.sectionTimeStart == self.timeFormat and self.sectionTimeEnd == self.timeFormat:
                self.log(1, 'No section were added. Auto create whole video duration as section.')
                job.addSection(self.timeFormat, self.videoProps.get('durationHMS'))
                return True
            elif self.sectionTimeStart == self.sectionTimeEnd:
                msg = 'Error: No sections were added and section markers have same time position.'
                self.log(1, msg, 1)
                self.showMsgBox(msg, infoText='Please set a valid section range.', detailText='Current section start: %s\nCurrent section End: %s' % (self.sectionTimeStart, self.sectionTimeEnd), icon='critical')
                return False
            else:
                self.log(1, 'No section were added. Auto create section from %s to %s.' % (self.sectionTimeStart, self.sectionTimeEnd))
                job.addSection(self.sectionTimeStart, self.sectionTimeEnd)
                return True
        except Exception as e:
            raise Exception(traceback.format_exc())

    def runNextWaitJob(self):
        try:
            if self.ffmpegProcess or self.btnQueuePause.isChecked():
                return False
            self.log(1, 'Running next job ...')
            job = self.getNextWaitingJob()
            if job:
                if self.isSameRenderSrcTgt(job, True) or self.isSectionsMissing(job, True): return False
                self.FFmpegThread = FFmpegThread(job, self.config.getConfigDeshakePath())
                self.FFmpegThread.finished.connect(self.onFFmpegThreadFinished)
                self.FFmpegThread.ffmpegStart.connect(self.onFFmpegStart)
                self.FFmpegThread.ffmpegProcess.connect(self.onFFmpegProgress)
                self.FFmpegThread.ffmpegExit.connect(self.onFFmpegExit)
                self.FFmpegThread.start()
                self.log(1, 'FFmpeg thread started.')
            return True
        except Exception as e:
            msg = 'Error: Cannot run next waiting job in queue.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            self.showMsgBox(msg, detailText=traceback.format_exc(), icon='critical')
            return False

    def isSameRenderSrcTgt(self, job, isTask=False):
        '''
        Checks if the source and target file are not the same.

        :param job: The job to check
        :param isTask: If True, there will be no message box in the frontend (use it for the queue)
        '''
        try:
            if Functions.isSameString(job.getSrcFilePathLong(), job.getTgtFilePathLong()):
                msg = 'Error: Input and Output Path are the same.'
                self.log(1, msg, 1)
                self.onFFmpegExit([job, -100, msg, False, False])
                if not isTask: self.showMsgBox(msg, btns="ok", icon="critical")
                return True
            return False
        except Exception as e:
            raise Exception(e)

    def isSectionsMissing(self, job, isTask=False):
        '''
        Checks if the job have sections

        :param job: The job to check
        :param isTask: If True, there will be no message box in the frontend (use it for the queue)
        :return: True if sections are missing, else False
        '''
        try:
            if len(job.getSections()) == 0:
                msg = 'Error: No sections to render.'
                self.log(1, msg, 1)
                self.onFFmpegExit([job, -101, msg, False, False])
                if not isTask: self.showMsgBox(msg, btns="ok", icon="critical")
                return True
            return False
        except Exception as e:
            raise Exception(e)

    def getNextWaitingJob(self):
        return self.getNextJobByStateID(0)

    def getNextPausedJob(self):
        return self.getNextJobByStateID(5)

    def getNextRenderingJob(self):
        return self.getNextJobByStateID(4)

    def getNextJobByStateID(self, stateID):
        try:
            job = False
            jobItems = self.tableQueue.findItems(self.getJobStateString(stateID), Qt.MatchExactly)
            if(jobItems):
                iRow = self.tableQueue.row(jobItems[0])
                jobItem = self.tableQueue.item(iRow, 0)
                jobIndex = jobItem.text()
                job = self.jobs.getJob(jobIndex)
            return job
        except Exception as e:
            msg = 'Error: Cannot get the next job by ID.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            self.showMsgBox(msg, detailText=traceback.format_exc(), icon='critical')
            return False

    def setPlayerControlsState(self, state):
        self.framePlayerBtns.setEnabled(state)
        self.framePlayerProgress.setEnabled(state)

    # Convert time string (0:00:0.0) to datetime object
    def timeStringToTime(self, timeStr):
        date_time_obj = datetime.datetime.strptime(timeStr, '%H:%M:%S.%f')
        return date_time_obj

    def getJobStateString(self, state):
        return self.jobStates.get(state)

    def setMuteState(self, mute):
        self.playerControl.mute(mute)
        if mute:
            self.btnMute.setText('婢')
        else:
            self.btnMute.setText('墳')

    # Player observer event handlers

    def onPlayerPause(self, action, state):
        if not self.frameStep:
            if state:
                self.btnPause.setText('契')
            else:
                self.btnPause.setText('')
        self.frameStep = False

    def onPlayerTimePos(self, action, timestamp):
        '''
        Callback function when the player time position changes. Only processes every 2nd call as mpv fires this callback two times per jump.
        '''
        if not timestamp: return
        try:
            self.playerTimeCurrentMs = timestamp
            time = Functions.timestampToHMS(timestamp)
            self.playerTimeCurrent = time
            self.setLabelPlayerTimeCurr(time)
            if not self.isSliderPlayerPressed(): self.setSliderPlayerPosFromTimestamp(timestamp)
        except Exception as e:
            self.log(1, 'Error: Cannot set player time to time label. %s' % e, 1)

    def onPlayerVolume(self, action, volume):
        self.setVolumeSlider(int(volume), False)

    # GUI control event handlers

    def closeEvent(self, event):
        '''Qt close event. Gets called when application closing is triggered'''
        # Todo: Check if job rendering
        if self.ffmpegProcess and self.config.getAppWarnCloseWhileRender():
            if not self.showMsgBox('A job is currently rendering.', infoText='Really quit?', btns='yesno', icon='question'):
                event.ignore()
                return
        self.config.setAppGeometry(self.saveGeometry())
        self.config.setAppState(self.saveState())

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls:
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls:
            event.setDropAction(Qt.CopyAction)
            event.accept()
            links = []
            for url in event.mimeData().urls():
                links.append(str(url.toLocalFile()))
            # self.emit(SIGNAL("dropped"), links[0])
            self.newFile(links[0])
        else:
            event.ignore()

    def onBtnPauseClicked(self):
        self.playerControl.togglePause()

    def onPlayerSeekSmall(self):
        self.sanitizeSeek(2.0)

    def onPlayerSeekMedium(self):
        self.sanitizeSeek(10.0)

    def onPlayerSeekSmallBack(self):
        self.sanitizeSeek(-2.0)

    def onPlayerSeekMediumBack(self):
        self.sanitizeSeek(-10.0)

    def onBtnFrameStepClicked(self):
        self.frameStep = True
        self.playerControl.frameStep()
        self.btnPause.setText('契')

    def onBtnFrameStepBackClicked(self):
        self.playerControl.frameBackStep()
        self.btnPause.setText('契')

    def onBtnSectionStartClicked(self):
        self.setCurrentSectionStart()

    def onScSectionStart(self):
        self.setCurrentSectionStart()

    def onBtnSectionEndClicked(self):
        self.setCurrentSectionEnd()

    def onScSectionEnd(self):
        self.setCurrentSectionEnd()

    def onBtnSectionAddClicked(self):
        self.sectionAddRow(self.sectionTimeStart, self.sectionTimeEnd)
        self.jobs.getCurrentJob().addSection(self.sectionTimeStart, self.sectionTimeEnd)

    def onBtnSectionDeleteClicked(self):
        self.sectionDeleteSelectedRow()

    def onBtnSectionUpClicked(self):
        move = Functions.moveTableRow(self.tableSections, -1)
        self.jobs.getCurrentJob().moveSection(move.get('from'), move.get('to'))

    def onBtnSectionDownClicked(self):
        move = Functions.moveTableRow(self.tableSections, 1)
        self.jobs.getCurrentJob().moveSection(move.get('from'), move.get('to'))

    def onBtnCurrentSectionStart(self):
        if self.sectionTimeStart != self.playerTimeCurrent: self.playerControl.seek(self.sectionTimeStart, 'absolute')

    def onBtnCurrentSectionEnd(self):
        if self.sectionTimeEnd != self.playerTimeCurrent: self.playerControl.seek(self.sectionTimeEnd, 'absolute')

    def onTableSectionCurrCellChanged(self):
        self.setSectionBtnStates()

    def onTableSectionItemDblClicked(self, item):
        timeStr = item.text()
        self.playerControl.seek(timeStr, 'absolute')

    def onLineEditTgtFileNameChanged(self, text):
        self.jobs.getCurrentJob().setTgtFileName(text)
        self.setBtnExportSaveState()

    def onBoxFileCountChanged(self, text):
        try:
            self.jobs.getCurrentJob().setTgtFileCount(text)
        except Exception as e:
            msg = 'Error: increase file count.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            self.showMsgBox(msg, detailText=traceback.format_exc(), icon='warning')

    def onBtnExportSave(self):
        self.saveSession()

    def onBtnTgtFileAutoIncrement(self):
        self.config.setAppIncrementFilename(self.btnTgtFileAutoIncrement.isChecked())
        if self.boxTgtFileCount.value() == 0: self.changeTargetFileCount(1)

    def onBtnExportDirsClicked(self):
        self.dirsUI.show()

    def onBtnTaggerFilterClicked(self):
        self.tagsFilterUI.show()

    def onCmbTgtDirsCurrTextChanged(self, text):
        self.setCurrTgtDir()
        self.config.setAppTgtDirName(text)
        self.setBtnExportSaveState()

    def onBtnFilterCropClicked(self):
        job = self.jobs.getCurrentJob()
        job.setFilterCropState(self.btnFilterCrop.isChecked())

    def onBoxFilterCropTChanged(self, px):
        job = self.jobs.getCurrentJob()
        job.setFilterCropT(px)

    def onBoxFilterCropRChanged(self, px):
        job = self.jobs.getCurrentJob()
        job.setFilterCropR(px)

    def onBoxFilterCropBChanged(self, px):
        job = self.jobs.getCurrentJob()
        job.setFilterCropB(px)

    def onBoxFilterCropLChanged(self, px):
        job = self.jobs.getCurrentJob()
        job.setFilterCropL(px)

    def onBtnFilterDeinterlaceClicked(self):
        job = self.jobs.getCurrentJob()
        job.setFilterDeinterlaceState(self.btnFilterDeinterlace.isChecked())

    def onComboBoxFilterDeinterlaceDeinterlacerChanged(self, text):
        job = self.jobs.getCurrentJob()
        job.setFilterDeinterlaceDeinterlacer(text)
        self.config.setFiltersDeinterlacer(text)

    def onBtnFilterResizeClicked(self):
        job = self.jobs.getCurrentJob()
        job.setFilterResizeState(self.btnFilterResize.isChecked())

    def onBoxFilterResizeWChanged(self, text):
        job = self.jobs.getCurrentJob()
        job.setFilterResizeWidth(text)

    def onBoxFilterResizeHChanged(self, text):
        job = self.jobs.getCurrentJob()
        job.setFilterResizeHeight(text)

    def onBtnFilterDeshake(self):
        job = self.jobs.getCurrentJob()
        job.setFilterDeshakeState(self.btnFilterDeshake.isChecked())

    def onBtnFilterRotateLeft(self):
        job = self.jobs.getCurrentJob()
        if self.btnFilterRotateLeft.isChecked():
            job.setFilterRotate(-90)
        else:
            job.setFilterRotate(False)
        self.btnFilterRotateRight.setChecked(False)
        self.btnFilterRotate180.setChecked(False)

    def onBtnFilterRotateRight(self):
        job = self.jobs.getCurrentJob()
        if self.btnFilterRotateRight.isChecked():
            job.setFilterRotate(90)
        else:
            job.setFilterRotate(False)
        self.btnFilterRotateLeft.setChecked(False)
        self.btnFilterRotate180.setChecked(False)

    def onBtnFilterRotate180(self):
        job = self.jobs.getCurrentJob()
        if self.btnFilterRotate180.isChecked():
            job.setFilterRotate(180)
        else:
            job.setFilterRotate(False)
        self.btnFilterRotateLeft.setChecked(False)
        self.btnFilterRotateRight.setChecked(False)

    def onBtnMuteClicked(self):
        self.config.setPlayerIsMuted(not self.config.getPlayerIsMuted())
        self.setMuteState(self.config.getPlayerIsMuted())

    def onSliderVolumeChange(self):
        volume = self.sliderVolume.value()
        self.playerControl.volume(volume)

    def renderFrameWheelEvent(self, event):
        volume = self.sliderVolume.value()
        if event.angleDelta().y() > 0:
            self.setVolumeSlider(+5)
        elif event.angleDelta().y() < 0:
            self.setVolumeSlider(-5)

    def onSliderPlayerValueChanged(self, value):
        if self.isSliderPlayerPressed(): self.seekFromPlayerSlider(value)

    def onTableQueueCurrCellChanged(self, row, col):
        self.setQueueBtnStates()

    def onTableQueueCellDblClicked(self, row, col):
        state = self.queueGetCurrentState(row)
        if state == 4:
            return
        elif state == 1:
            self.queuePlayFile()
        elif state == 3:
            self.queueShowLog()

    def onBtnQueueDeleteClicked(self):
        self.queueDeleteSelectedRow()

    def onBtnQueueUpClicked(self):
        self.swapJobs(Functions.moveTableRow(self.tableQueue, -1))

    def onBtnQueueDownClicked(self):
        self.swapJobs(Functions.moveTableRow(self.tableQueue, 1))

    def onBtnQueuePauseClicked(self):
        self.toggleQueuePause()

    def onBtnQueueKillClicked(self):
        self.killFFmpegProcess()

    def onBtnQueueLoadClicked(self):
        self.newFile(False)

    def onQueueContextMenu(self, point):
        menu = QtWidgets.QMenu(self)
        if self.tableQueue.itemAt(point):
            state = self.queueGetCurrentState()
            if state == 4:
                return
            if state == 1:
                menu.addAction(self.actionPlayFile)
            menu.addAction(self.actionOpenFolder)
            menu.addSeparator()
            if state == 0:
                menu.addAction(self.actionStatePostpone)
            if state == 2:
                menu.addAction(self.actionStateResume)
            if state == 3 or state == 1:
                menu.addAction(self.actionStateReset)
            menu.addSeparator()
            if state != 0:
                menu.addAction(self.actionShowLog)
        point = self.tableQueue.mapToGlobal(point)
        menu.popup(point)

    def onQueueCtxActionPlayFile(self):
        self.queuePlayFile()

    def onQueueCtxActionOpenFolder(self):
        self.queueOpenFolder()

    def onQueueCtxActionStatePostpone(self):
        self.queueSetState(2)

    def onQueueCtxActioStateResume(self):
        self.queueSetState(0)

    def onQueueCtxActioStateReset(self):
        self.queueSetState(0)

    def onQueueCtxActionShowLog(self):
        self.queueShowLog()

    def onBtnFilterCropDownClicked(self):
        index = self.getIndexOfLayoutInFiltersGrid(self.layoutFilterCrop)
        self.moveRowInFiltersGrid(index, True)
        self.setFilterBtnStates()

    def onBtnFilterCropUpClicked(self):
        index = self.getIndexOfLayoutInFiltersGrid(self.layoutFilterCrop)
        self.moveRowInFiltersGrid(index, False)
        self.setFilterBtnStates()

    def onBtnFilterDeinterlaceDownClicked(self):
        index = self.getIndexOfLayoutInFiltersGrid(self.layoutFilterDeinterlace)
        self.moveRowInFiltersGrid(index, True)
        self.setFilterBtnStates()

    def onBtnFilterDeinterlaceUpClicked(self):
        index = self.getIndexOfLayoutInFiltersGrid(self.layoutFilterDeinterlace)
        self.moveRowInFiltersGrid(index, False)
        self.setFilterBtnStates()

    def onBtnFilterResizeDownClicked(self):
        index = self.getIndexOfLayoutInFiltersGrid(self.layoutFilterResize)
        self.moveRowInFiltersGrid(index, True)
        self.setFilterBtnStates()

    def onBtnFilterResizeUpClicked(self):
        index = self.getIndexOfLayoutInFiltersGrid(self.layoutFilterResize)
        self.moveRowInFiltersGrid(index, False)
        self.setFilterBtnStates()

    def onBtnFilterRotateDownClicked(self):
        index = self.getIndexOfLayoutInFiltersGrid(self.layoutFilterRotate)
        self.moveRowInFiltersGrid(index, True)
        self.setFilterBtnStates()

    def onBtnFilterRotateUpClicked(self):
        index = self.getIndexOfLayoutInFiltersGrid(self.layoutFilterRotate)
        self.moveRowInFiltersGrid(index, False)
        self.setFilterBtnStates()

    def onBtnFilterDeshakeDownClicked(self):
        index = self.getIndexOfLayoutInFiltersGrid(self.layoutFilterDeshake)
        self.moveRowInFiltersGrid(index, True)
        self.setFilterBtnStates()

    def onBtnFilterDeshakeUpClicked(self):
        index = self.getIndexOfLayoutInFiltersGrid(self.layoutFilterDeshake)
        self.moveRowInFiltersGrid(index, False)
        self.setFilterBtnStates()

    def onBtnTagRateHistorySaveClicked(self):
        if self.saveCurrentTagsAndRating(): self.setHistoryMode(False)

    def onListWidgetLastTagsItemClicked(self, item):
        tagID = item.data(100)
        self.selectTagsInTagsTree([tagID], False)
        item.setSelected(False)

    def onBtnTagsLastClicked(self):
        self.selectTagsInTagsTree(self.lastTagIDs, False)

    def onBtnTagsClearClicked(self):
        self.clearTagsTree()

    def onBtnLastRatingClicked(self):
        self.setBtnRating(self.lastRating)

    def onBtnTaggerActiveClicked(self):
        self.config.setTaggerIsActive(not self.config.getTaggerIsActive())

    def onBtnTaggerWarningClicked(self):
        self.config.setTaggerIsWarningActive(not self.config.getTaggerIsWarningActive())

    def onActionSettings(self):
        self.settingsUI.show()

    def onActionQuit(self):
        QCoreApplication.quit()

    def onMsgBoxExtraBtnOverwriteFile(self):
        '''Opens a file saved in variable self.overwriteFile'''
        if self.overwriteFile:
            if os.path.isfile(self.overwriteFile):
                opener = Functions.getCurrentSysOpener()
                subprocess.call([opener, self.overwriteFile])

    # Other Event handlers

    # Event handler while ffmpeg is rendering
    @pyqtSlot('PyQt_PyObject')
    def onFFmpegProgress(self, atts):
        line, job, totalSeconds = atts
        # Line can be an array with this values:
        # ['frame', '260']
        # ['fps', '67.89']
        # ['stream_0_0_q', '-1.0']
        # ['bitrate', '1550.2kbits/s']
        # ['total_size', '1679097']
        # ['out_time_us', '8665000']
        # ['out_time_ms', '8665000']
        # ['out_time', '00:00:08.665000']
        # ['dup_frames', '0']
        # ['drop_frames', '0']
        # ['speed', '2.26x']
        # ['progress', 'end']
        if self.jobsSwapping:
            return
        if not isinstance(line, list):
            return
        if not len(line) == 2:
            return
        if line[0] == 'speed':
            try: self.labelRenderSpeed.setText('%.2fx' % float(line[1][:-1]))
            except: pass
        elif line[0] == 'fps':
            try: self.labelRenderFPS.setText('%.2f %s' % (float(line[1]), line[0]))
            except: pass
        elif line[0] == 'total_size':
            try: self.labelRenderSize.setText('%.2f MiB' % float(int(line[1])/1000000))
            except: pass
        elif line[0] == 'out_time':
            try: self.labelRenderTime.setText(line[1][:-3])
            except: pass
        elif line[0] == 'out_time_ms':
            currentSecond = int(int(line[1])/10000)
            totalSeconds = int(totalSeconds * 100)
            if currentSecond > totalSeconds:
                currentSecond = totalSeconds
            if currentSecond == 0:
                self.progressBarRender.setMaximum(0)
            else:
                self.progressBarRender.setMaximum(totalSeconds)
                self.progressBarRender.setValue(currentSecond)

    # Event handler when ffmpeg exits rendering
    @pyqtSlot('PyQt_PyObject')
    def onFFmpegExit(self, atts):
        self.log(1, 'FFmpeg exited.')
        self.ffmpegProcess = False
        job, code, output, error, deshakeFile = atts
        errorMsg = ''
        if error: errorMsg = '%sFFmpeg Output:\n%s' % (errorMsg, str(error))
        if error and output: errorMsg = '%s\n\n' % errorMsg
        if output: errorMsg = '%sFFmpeg Output:\n%s' % (errorMsg, str(output))
        job.setFilterDeshakeFile(deshakeFile)
        if self.progressBarRender.isEnabled():
            self.progressBarRender.setValue(0)
            self.progressBarRender.setEnabled(False)
        if self.widgetRenderDetails.isEnabled():
            self.resetRenderDetails()
        state = job.getState()
        if code == 0:
            state = 1
        else:
            if self.ffmpegKilled:
                self.ffmpegKilled = False
                errorMsg = 'ffmpeg killed while rendering by the user.\n\n%s' % errorMsg
            state = 3
        if errorMsg != '':
            job.setLog(errorMsg)
        job.setState(state)
        if self.btnQueueKill.isEnabled(): self.btnQueueKill.setEnabled(False)
        # Update queue table with job state
        id = job.getID()
        self.updateQueueJobState(id, state)
        self.runNextWaitJob()

    # Event handler when ffmpeg starts to render
    @pyqtSlot('PyQt_PyObject')
    def onFFmpegStart(self, atts):
        job = atts[0]
        totalSeconds = atts[1]
        job.setState(4)
        self.ffmpegProcess = atts[2]
        self.updateQueueJobState(job.getID(), 4)
        if not self.progressBarRender.isEnabled(): self.progressBarRender.setEnabled(True)
        self.progressBarRender.setMinimum(0) # When min and max are same value, progress bar gets an "idle" animation in some system themes
        self.progressBarRender.setMaximum(0)
        self.progressBarRender.setValue(0)
        if not self.widgetRenderDetails.isEnabled(): self.widgetRenderDetails.setEnabled(True)
        if not self.btnQueueKill.isEnabled():
            self.btnQueueKill.setEnabled(True)

    def onFFmpegThreadFinished(self):
        self.ffmpegProcess = False

    # GUI Control

    def showMsgBox(self, msg, btns="ok", icon="info", infoText='', detailText='', title='PyCut Message', extraBtnText='', extraBtnCallback=False):
        '''
        Shows a QMessageBox dialog.

        :param msg: The message to display
        :param btns: Choices. Default = "ok". Options: "okcancel", "save", "savecancel", "yesno", "retry", "retryabort", "close"
        :param icon: Icon. Default "info". Options: "info", "question", "warning", "critical". Set to False for no icon.
        :param infoText: Info text which gets displayed below the main message
        :param detailText: Detail text which gets displayed if the user clicks on a "details" button
        :param title: Title of the message box.
        :param extraBtnText: If not a empty string, a extra button gets added with this text. This button will not be able to give a return value.
        :param extraBtnCallback: If a function gets set, it will be called if the extra btn is clicked.
        '''
        msgBox = QMessageBox()
        if icon == "info":  msgBox.setIcon(QMessageBox.Information)
        elif icon == "question":  msgBox.setIcon(QMessageBox.Question)
        elif icon == "warning":  msgBox.setIcon(QMessageBox.Warning)
        elif icon == "critical":  msgBox.setIcon(QMessageBox.Critical)
        msgBox.setText(msg)
        if infoText != '': msgBox.setInformativeText(infoText)
        msgBox.setWindowTitle(title)
        if detailText != '': msgBox.setDetailedText(detailText)
        if btns == 'okcancel': msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        elif btns == 'save': msgBox.setStandardButtons(QMessageBox.Save)
        elif btns == 'savecancel': msgBox.setStandardButtons(QMessageBox.Save | QMessageBox.Cancel)
        elif btns == 'yesno': msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        elif btns == 'retry': msgBox.setStandardButtons(QMessageBox.Retry)
        elif btns == 'retryabort': msgBox.setStandardButtons(QMessageBox.Retry | QMessageBox.Abort)
        elif btns == 'close': msgBox.setStandardButtons(QMessageBox.Close)
        else: msgBox.setStandardButtons(QMessageBox.Ok)
        if extraBtnText != '':
            extraBtn = msgBox.addButton(extraBtnText, msgBox.ActionRole)
            extraBtn.disconnect()
            if extraBtnCallback : extraBtn.clicked.connect(extraBtnCallback)
        result = msgBox.exec_()
        if(result == QMessageBox.Ok): return True
        elif(result == QMessageBox.Cancel): return False
        elif(result == QMessageBox.Yes): return True
        elif(result == QMessageBox.No): return False
        elif(result == QMessageBox.Save): return True
        elif(result == QMessageBox.Retry): return True
        elif(result == QMessageBox.Abort): return False
        elif(result == QMessageBox.Close): return False
        return False

    def buildTagsTree(self, currTagID):
        '''
        Fills the TagsTree widget with tags of the member variable "tagsTree".
        This is a recursive function. Call it with currTagID parameter = -1
        to start the process.

        :param currTagID: Set it to -1 to start the loop.
        '''
        if currTagID != -1:
            self.tagsTreeItemPrefix = '%s%s' % (self.tagsTreeSpaceChar, self.tagsTreeItemPrefix)
        for i, tag in enumerate(self.tagsTree):
            if tag['parentID'] == currTagID:
                item = QListWidgetItem('%s%s' % (self.tagsTreeItemPrefix, tag['label']))
                item.setToolTip('TagID: %s' % tag['tagID'])
                fontWeight = -1
                if tag['parentID'] == -1: fontWeight = QFont.Bold
                item.setFont(QFont('Noto Sans', 8, weight=fontWeight))
                self.listWidgetTagsTree.addItem(item)
                if 'filter' in tag and tag['filter']: item.setHidden(True)
                self.buildTagsTree(tag['tagID'])
                self.tagsTree[i]['item'] = item
        self.tagsTreeItemPrefix = self.tagsTreeItemPrefix[0:-1]

    def setTagsAndRatingToTree(self, forSource:bool = True):
        '''
        Gets the tags and rating for the source or target file of the current
        job session and sets it into the tags tree and rating panel.

        :param forSource: Get the tags and ratings for the source filename if True, else get them from the target filename.
        '''
        if not self.isTaggerEnabled: return False
        job = self.jobs.getCurrentJob()
        try:
            if forSource: folderID = self.db.getFolderID(job.getSrcDirName())
            else: folderID = self.db.getFolderID(job.getTgtDirName())
            if not folderID: return False
            if forSource: imageID = self.db.getImageID(folderID, job.getSrcFileNameLong())
            else: imageID = self.db.getImageID(folderID, job.getTgtFileNameLong())
            if not imageID:
                if forSource: return False
                imageID = self.db.insertImage(folderID, job.getTgtFileNameLong(), job.getHashID())
                if not imageID:
                    msg = 'Error: Cannot create ImageID for file.'
                    self.log(1, msg, 1)
                    self.showMsgBox(msg, btns="ok", icon="critical")
                    return False
            rating = self.db.getRating(imageID)
            if rating: self.setBtnRating(rating)
            else: self.setBtnRating(0)
            tagIDs = self.db.getTagIDs(imageID)
            self.selectTagsInTagsTree(tagIDs)
        except Exception as e:
            self.disableTaggerPanel()
            msg = 'Error on setting Tags and Rating to the Tagger Panel.'
            self.log(1, msg, 1)
            self.showMsgBox(msg, btns="ok", icon="warning", detailText=str(e))
            return False
        return True

    def warnWhenNoTagsOrRating(self):
        '''
        Displays a warning if no tags or no rating is set.

        :return: True if both are set or if user wants to proceed, false if not
        '''
        if self.isTaggerWarningActive():
            tagIDs = self.getSelectedTagIDsFromTagsTree()
            rating = self.getRatingFromBtns()
            if not tagIDs and not rating:
                if not self.showMsgBox('No rating and no tags are set.', btns='yesno', icon='question', infoText='Save anyways?'): return False
            elif not tagIDs:
                if not self.showMsgBox('No tags are set.', btns='yesno', icon='question', infoText='Save anyways?'): return False
            elif not rating:
                if not self.showMsgBox('No rating is set.', btns='yesno', icon='question', infoText='Save anyways?'): return False
        return True

    def saveCurrentTagsAndRating(self):
        '''
        Saves the current tags and rating for the target file to the database.
        Call this function when 'warnWhenNoTagsOrRating' returns true.

        :param return: False if something went wrong. True if successfully saved.
        '''
        if not self.isTaggerEnabled(): return False
        self.log(1, 'Save Tags and Rating to DB ...')
        job = self.jobs.getCurrentJob()
        try:
            folderID = self.db.getFolderID(job.getTgtDirName())
            if not folderID: folderID = self.db.insertPath(job.getTgtDirName())
            if not folderID:
                msg = 'Error: Got no folderID. Cannot save tags and rating.'
                self.log(1, msg, 1)
                self.showMsgBox(msg, btns='ok', icon='warning')
                return False
            imageID = self.db.getImageID(folderID, job.getTgtFileNameLong())
            if not imageID: imageID = self.db.insertImage(folderID, job.getTgtFileNameLong())
            if not imageID:
                msg = 'Error: Got no imageID. Cannot save tags and rating.'
                self.log(1, msg, 1)
                self.showMsgBox(msg, btns='ok', icon='warning')
                return False
        except Exception as e:
            msg = 'Error when saving Tags and Rating to database'
            self.log(1, '%s: %s' % (msg, e), 1)
            self.showMsgBox('%s.' % msg, btns='ok', icon='warning', detailText=str(e))
            self.disableTaggerPanel()
            return False

        hashID = job.getHashID()
        rating = self.getRatingFromBtns()
        tagIDs = self.getSelectedTagIDsFromTagsTree()
        try:
            self.log(1, 'Save hashID to database ...')
            self.db.setHashID(imageID, folderID, hashID)
            self.log(1, 'HashID saved: %s' % hashID)
            self.log(1, 'Save rating to database ...')
            self.db.setRating(imageID, folderID, rating)
            self.log(1, 'Rating saved: %s' % rating)
            self.log(1, 'Save tags to database ...')
            self.db.setTags(imageID, tagIDs)
            self.log(1, 'Tags saved: %s' % tagIDs)
        except:
            msg = 'Error: No database connection possible'
            self.log(1, msg, 1)
            self.showMsgBox(msg, btns='ok', icon="warning")
            self.disableTaggerPanel()
            return False
        self.insertTagsInLastTagsList(tagIDs)
        self.setLastRating(rating)
        self.clearRating()
        self.clearTagsTree()
        return True

    def getSelectedTagIDsFromTagsTree(self):
        '''
        Gets all selected tags from the tags tree widget.

        :return: Array with tag IDs of selected tag tree items
        '''
        tagIDs = []
        for i, tag in enumerate(self.tagsTree):
            tag = self.tagsTree[i]
            try:
                item = tag['item']
                if item.isSelected():
                    tagIDs.append(tag['tagID'])
            except Exception as e:
                msg = 'Error: Cannot get the selection state for a tags tree item.'
                self.log(1, msg, 1)
                self.showMsgBox(msg, infoText='This could mean this Tag will not be set to the database', detailText=str(e), icon="warning")
                continue
        return tagIDs

    def getRatingFromBtns(self):
        '''
        Gets the currently selected rating from the rating radio buttons

        :return: The current rating (int)
        '''
        rating = 0
        if self.radioButton_rate0.isChecked(): return 0
        if self.radioButton_rate1.isChecked(): return 1
        if self.radioButton_rate2.isChecked(): return 2
        if self.radioButton_rate3.isChecked(): return 3
        if self.radioButton_rate4.isChecked(): return 4
        if self.radioButton_rate5.isChecked(): return 5
        return rating

    def selectTagsInTagsTree(self, tagIDs, clearSelection=True):
        '''
        Selects a list of tag IDs on the tags tree. Clears all tags which are not in the list.

        :param tagIDs: Array of tag IDs. Empty array clears all tags.
        :param clearTags: If True, all tags get deselected before the new tags get selected.
        '''
        if clearSelection or not tagIDs:
            self.log(1, 'Clear tags ...')
            for i in range(self.listWidgetTagsTree.count()):
                self.listWidgetTagsTree.item(i).setSelected(False)
        selected = []
        hiddenTags = []
        for tagID in tagIDs:
            for tag in self.tagsTree:
                if tag['tagID'] == tagID:
                    tag['item'].setSelected(True)
                    if tag['filter']: hiddenTags.append('"%s" (TagID "%s")' % (tag['label'], tag['tagID']))
                    selected.append(tag['item'].text().replace(self.tagsTreeSpaceChar, ''))
        if tagIDs: self.log(1, 'Selecting tags: %s' % ', '.join(selected))
        if hiddenTags:
            msg = 'Warning: Tags were loaded from job which are hidden in the Tags Tree.'
            self.log(1, msg, 1)
            self.showMsgBox(msg, detailText='%s' % '\n'.join(hiddenTags))

    def insertTagsInLastTagsList(self, tagIDs, clearTags=True):
        '''
        Insert tags into the last tags listview

        :param tagIDs: Array of tag IDs. Empty array clears all tags.
        :param clearTags: If True, all tags get cleared before the new tags inserted.
        '''
        if clearTags: self.listWidgetLastTags.clear()

        self.lastTagIDs = tagIDs
        for tagID in tagIDs:
            for tag in self.tagsTree:
                if tag['tagID'] == tagID:
                    item = QListWidgetItem(tag['label'])
                    item.setData(100, tag['tagID'])
                    self.listWidgetLastTags.addItem(item)

    def updateTagsFilter(self, tagIDs):
        '''
        Update the filtered tags in the tags tree
        '''
        for tag in self.tagsTree:
            if tag['tagID'] in tagIDs:
                tag['filter'] = True
                tag['item'].setHidden(True)
                tag['item'].setSelected(False)
            else:
                tag['filter'] = False
                tag['item'].setHidden(False)

    def setLastRating(self, rating):
        self.lastRating = rating
        self.btnLastRating.setText(str(rating))

    def setBtnRating(self, rating):
        self.log(1, 'Selecting rating: %s' % rating)
        if rating == 0: self.radioButton_rate0.setChecked(True)
        if rating == 1: self.radioButton_rate1.setChecked(True)
        if rating == 2: self.radioButton_rate2.setChecked(True)
        if rating == 3: self.radioButton_rate3.setChecked(True)
        if rating == 4: self.radioButton_rate4.setChecked(True)
        if rating == 5: self.radioButton_rate5.setChecked(True)

    def disableTaggerPanel(self):
        '''Disables the Tagger panel. For use when no database connection is possible.'''
        if not self.isTaggerEnabled(): return
        self.showMsgBox('Tagger got disabled as there was no succesful database connection possible.', btns="ok", icon="warning")
        self.dockTagger.setEnabled(False)
        self.emptyTagsTree()
        self.clearRating()
        self.labelTaggerError.setHidden(False)
        self.setHistoryMode(False)

    def enableTaggerPanel(self):
        '''Enables the Tagger panel. For use when database connection is possible.'''
        if self.isTaggerEnabled(): return
        if not self.tagsTree:
            try: tagsTree = self.db.getTagsTree()
            except: return False
            self.tagsTree = self.setFilterStateForTagsTree(tagsTree)
            self.buildTagsTree(-1)
        self.labelTaggerError.setHidden(True)
        self.dockTagger.setEnabled(True)

    def setFilterStateForTagsTree(self, tagsTree):
        '''
        Loops the tags tree array and sets "filter"=True if the for the TagID a filter entry is set

        :param tagsTree: The tagsTree array with tags as objects
        :return: TagsTree array with objects having "filter"=True if they should get filtered
        '''
        filterTagIDs = self.config.getTaggerFilterTagIDs()
        for i in range(len(tagsTree)):
            tag = tagsTree[i]
            if tag['tagID'] in filterTagIDs:
                tagsTree[i]['filter'] = True
            else: tagsTree[i]['filter'] = False
        return tagsTree

    def checkDBConnectivity(self):
        '''Checks if the database is available and sets Tagger panel status based on the result'''
        if self.db.testConnection():
            if not self.dockTagger.isEnabled(): self.db.createHashTable()
            self.enableTaggerPanel()
        else: self.disableTaggerPanel()

    def isTaggerEnabled(self):
        '''
        Checks if tagging and rating is enabled.

        :return: True if tagging and rating is enabled, False if not.
        '''
        return self.dockTagger.isEnabled()

    def isTaggerWarningActive(self):
        '''
        Checks if the Tagger warning button is checked which warns if no rating or no tags are selected
        '''
        return self.btnTaggerWarning.isChecked()

    def isTgtFileExistsInTgtDirWarningActive(self):
        '''
        Checks if the option to warn if the target file already exists in the target directory is active
        '''
        return self.config.getAppWarnFileExistsInTgtDir()

    def isTgtFileExistsInJobsWarningActive(self):
        '''
        Checks if the option to warn if the target path and file already exists in the jobs queue is active
        '''
        return self.config.getAppWarnFileExistsInJobs()

    def isFileIsKnownWarningIsActive(self):
        '''
        Checks if the option to warn if the file hash of the currently opened file is known in the database is active
        '''
        return self.config.getAppWarnFileHashExistsInDB()

    def overwriteTgtFileIfExists(self, currentJob) -> bool:
        '''
        If the target file for the jobs exists, the user gets prompted to ask if it should get overwritten.

        :param currentJob: The current job.
        :return: True if the file should get overwritten when it exists, else False
        '''
        overwrite = True
        tgtFile = currentJob.getTgtFilePathLong()
        if os.path.exists(tgtFile):
            self.log(1, 'Target file already exists.')
            self.overwriteFile = tgtFile
            if not self.showMsgBox('The target file already exists. Overwrite it?', btns='yesno', infoText=tgtFile, icon='question', extraBtnText='Open target', extraBtnCallback=self.onMsgBoxExtraBtnOverwriteFile):
                overwrite = False
                self.log(1, 'User does not want to overwrite target file.')
            else:
                self.log(1, 'User wants to overwrite target file.')
            self.overWriteFile = False
        return overwrite

    def setBtnSectionAddState(self):
        if self.sectionTimeStart and self.sectionTimeEnd:
            self.btnSectionAdd2.setEnabled(True)
        else:
            self.btnSectionAdd2.setEnabled(False)

    def sectionAddRow(self, fromTime, toTime):
        rowIndex = self.tableSections.rowCount()
        self.tableSections.insertRow(rowIndex)
        self.tableSections.setItem(rowIndex, 0, QTableWidgetItem(fromTime))
        self.tableSections.setItem(rowIndex, 1, QTableWidgetItem(toTime))

    def sectionDeleteSelectedRow(self):
        rowIndex = self.tableSections.currentRow()
        self.tableSections.removeRow(rowIndex)
        self.jobs.getCurrentJob().removeSection(rowIndex)
        if(rowIndex > 0):
            self.tableSections.setCurrentCell(rowIndex-1, 0)
        self.setSectionBtnStates()

    def clearSections(self):
        '''Clears the sections table (without resetting the current section timestamps)'''
        self.setSectionTimeStart(self.timeFormat)
        self.setSectionTimeEnd(self.timeFormat)
        for i in range(self.tableSections.rowCount()):
            self.tableSections.removeRow(0)

    def emptyTagsTree(self):
        '''Deletes all items from the tagsTree'''
        self.tagsTree = []
        self.listWidgetTagsTree.clear()

    def clearTagsTree(self):
        '''Resets the tag tree'''
        self.selectTagsInTagsTree([])

    def clearLastTagsList(self):
        '''Resets the last tags list view'''
        self.insertTagsInLastTagsList([])

    def clearRating(self):
        '''Sets the rating back to zero'''
        self.setBtnRating(0)

    def queueAddRow(self, id, filename, state):
        iRow = self.tableQueue.rowCount()
        self.tableQueue.insertRow(iRow)
        itemID = QTableWidgetItem(id)
        itemFilename = QTableWidgetItem(filename)
        itemFilename.setToolTip(filename)
        itemState = QTableWidgetItem(state)
        self.tableQueue.setItem(iRow, 0, itemID)
        self.tableQueue.setItem(iRow, 1, itemFilename)
        self.tableQueue.setItem(iRow, 2, itemState)
        self.tableQueue.scrollToBottom()
        return iRow

    def resetCropFilter(self):
        self.btnFilterCrop.setChecked(False)
        self.boxFilterCropT.setValue(0)
        self.boxFilterCropR.setValue(0)
        self.boxFilterCropB.setValue(0)
        self.boxFilterCropL.setValue(0)

    def resetRotateFilter(self):
        self.btnFilterRotateRight.setChecked(False)
        self.btnFilterRotateLeft.setChecked(False)
        self.btnFilterRotate180.setChecked(False)

    def resetResizeFilter(self):
        self.boxFilterResizeW.setValue(0)
        self.boxFilterResizeH.setValue(0)
        self.btnFilterResize.setChecked(False)

    def resetDeshakeFilter(self):
        self.btnFilterDeshake.setChecked(False)

    def resetDeinterlaceFilter(self):
        self.btnFilterDeinterlace.setChecked(False)
        self.comboBoxFilterDeinterlaceDeinterlacer.setCurrentText(self.config.getFiltersDeinterlacer())

    def resetRenderDetails(self):
        '''Resets the render details to 0 and disables the layout'''
        self.widgetRenderDetails.setEnabled(False)
        self.labelRenderFPS.setText('0 fps')
        self.labelRenderSpeed.setText('0x')
        self.labelRenderSize.setText('0 MiB')
        self.labelRenderTime.setText(self.timeFormat)

    def setVolumeSlider(self, value : int, relative=True):
        '''
        Set the volume slider value.

        :param value: The value the slider gets changed to
        :param relative: If True, the value gets added or subscracted from current volume. Else, the volume gets set to the value.
        '''
        volume = self.sliderVolume.value()
        if relative: volume = volume + value
        else: volume = value
        if volume > 100: volume = 100
        elif volume < 0: volume = 0
        self.sliderVolume.setValue(volume)

    def setHistoryMode(self, state):
        '''
        Enables or disables the Tag & Rate history mode by setting the member variable to the state
        and controlling which elements in the GUI are visible or not.

        :param state: True or False
        '''
        if state and self.isTaggerEnabled():
            self.log(1, 'Activate Tags and Rating History Mode.')
            self.historyMode = True
            self.widgetTagRateHistoryCtrl.setVisible(True)
            self.widgetTagRateEditCtrl.setVisible(False)
            self.btnExportSave.setToolTip('Cannot save while Tags & Rating is in History Mode. Save current Tags & Rating first.')
        elif not state and self.isTaggerEnabled():
            self.log(1, 'Disable Tags and Rating History Mode.')
            self.historyMode = False
            self.widgetTagRateHistoryCtrl.setVisible(False)
            self.widgetTagRateEditCtrl.setVisible(True)
            self.btnExportSave.setToolTip(self.toolTipBtnExportSave)
        else:
            self.widgetTagRateHistoryCtrl.setVisible(False)
            self.widgetTagRateEditCtrl.setVisible(True)
            self.historyMode = False
        self.setBtnExportSaveState()

    # Set the states of the section buttons
    def setSectionBtnStates(self):
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
            if iRow < rowCount-1:
                self.btnSectionDown.setEnabled(True)
            else:
                self.btnSectionDown.setEnabled(False)

    def setQueueBtnStates(self):
        rowCount = self.tableQueue.rowCount()
        iRow = self.tableQueue.currentRow()
        if rowCount == 0:
            self.btnQueueUp.setEnabled(False)
            self.btnQueueDown.setEnabled(False)
            self.btnQueueDelete.setEnabled(False)
            self.btnQueueLoad.setEnabled(False)
        else:
            self.btnQueueDelete.setEnabled(True)
            self.btnQueueLoad.setEnabled(True)
            if iRow == 0:
                self.btnQueueUp.setEnabled(False)
            else:
                self.btnQueueUp.setEnabled(True)
            if iRow < rowCount-1:
                self.btnQueueDown.setEnabled(True)
            else:
                self.btnQueueDown.setEnabled(False)

    def setBtnExportSaveState(self):
        if len(self.cmbTgtDirs.currentText()) > 0 and len(self.lineEditTgtFileName.text()) > 0 and not self.historyMode:
            if not self.btnExportSave.isEnabled(): self.btnExportSave.setEnabled(True)
        else:
            if self.btnExportSave.isEnabled(): self.btnExportSave.setEnabled(False)

    def queueDeleteSelectedRow(self):
        jobID, iRow = self.queueGetJobIDFromRow()
        try:
            job = self.jobs.getJob(jobID)
            if job.getState() == 4:
                self.showMsgBox('Cannot delete job while it is rendering.', infoText='Abort the job first, then delete it.', icon='warning')
                return
            self.log(1, 'Remove Job with ID %s' % jobID)
            self.jobs.removeJob(jobID)
        except Exception as e:
            msg = 'Error: Cannot remove Job.'
            self.log(1, msg, 1)
            self.showMsgBox(msg, btns="ok", icon="warning", detailText=str(e))
            return False
        self.tableQueue.removeRow(iRow)
        if(iRow > 0): self.tableQueue.setCurrentCell(iRow-1, 0)
        elif(iRow == 0):
            if len(self.jobs.jobs.items()) == 1: self.deleteDeshakeDir()
        self.setQueueBtnStates()

    def queueGetJobIDFromRow(self, iRow = False):
        if iRow is False:
            iRow = self.tableQueue.currentRow()
        itemID = self.tableQueue.item(iRow, 0)
        jobID = itemID.text()
        return jobID, iRow

    def queueGetCurrentState(self, iRow = False):
        if iRow is False:
            iRow = self.tableQueue.currentRow()
        itemState = self.tableQueue.item(iRow, 2)
        stateStr = itemState.text()
        state = self.jobStateStrToID(stateStr)
        return state

    def queueSetState(self, state):
        jobID, iRow = self.queueGetJobIDFromRow()
        job = self.jobs.getJob(jobID)
        job.setState(state)
        itemState = QTableWidgetItem(self.jobStates[state])
        self.tableQueue.setItem(iRow, 2, itemState)
        self.runNextWaitJob()

    def jobStateStrToID(self, stateStr):
        stateStr = stateStr.lower()
        id = False
        try:
            for key, state in self.jobStates.items():
                if state.lower() == stateStr:
                    id = key
                    break
        except:
            id = False
        return id

    def updateDirs(self, dirs : list):
        '''
        Updates the target directory combo box
        '''
        self.dirs = dirs
        self.config.setAppDirs(dirs)
        currentText = self.cmbTgtDirs.currentText()
        self.cmbTgtDirs.clear()
        for i in range(len(self.dirs)):
            self.cmbTgtDirs.insertItem(
                i, self.dirs[i][1], userData=self.dirs[i][0])
            if self.dirs[i][1] == currentText:
                self.cmbTgtDirs.setCurrentText(currentText)

    def updateQueueJobState(self, id, state):
        '''
        Updates the state of a job in the queue by the job ID
        '''
        rowCount = self.tableQueue.rowCount()
        for iRow in range(rowCount):
            idItem = self.tableQueue.item(iRow, 0)
            if(idItem.text() == id):
                stateItem = self.tableQueue.item(iRow, 2)
                stateItem.setText(self.getJobStateString(state))
                break

    def swapJobs(self, move):
        self.jobsSwapping = True
        # Get both jobs to swap
        job1ID = self.queueGetJobIDFromRow(move['from'])[0]
        job1 = self.jobs.getJob(job1ID)
        job1Pos = job1.getPosition()
        job2ID = self.queueGetJobIDFromRow(move['to'])[0]
        job2 = self.jobs.getJob(job2ID)
        job2Pos = job2.getPosition()
        # # Swap job positions
        job1.setPosition(job2Pos)
        job2.setPosition(job1Pos)
        self.jobsSwapping = False

    def queuePlayFile(self):
        jobID = self.queueGetJobIDFromRow()[0]
        job = self.jobs.getJob(jobID)
        filePathLong = job.getTgtFilePathLong()
        opener = Functions.getCurrentSysOpener()
        subprocess.call([opener, filePathLong])

    def queueOpenFolder(self):
        jobID = self.queueGetJobIDFromRow()[0]
        job = self.jobs.getJob(jobID)
        dir = job.getTgtDirName()
        opener = Functions.getCurrentSysOpener()
        subprocess.call([opener, dir])

    def queueShowLog(self):
        jobID = self.queueGetJobIDFromRow()[0]
        job = self.jobs.getJob(jobID)
        log = job.getLog()
        # Todo: handle if no log is set
        self.logUi.setTitle('Log for Job %s' % jobID)
        self.logUi.setLogText(log.replace('\\n', '\n'))
        self.logUi.show()

    def toggleQueuePause(self):
        if self.btnQueuePause.isChecked():
            self.btnQueuePause.setText('契')
            self.btnQueuePause.setToolTip('Resume job processing')
            self.config.setQueueIsPaused(True)
            if self.ffmpegProcess:
                os.kill(self.ffmpegProcess.pid, signal.SIGSTOP)
                job = self.getNextRenderingJob()
                self.updateQueueJobState(job.getID(), 5)
        else:
            self.btnQueuePause.setText('')
            self.btnQueuePause.setToolTip('Pause job processing')
            self.config.setQueueIsPaused(False)
            if self.ffmpegProcess:
                os.kill(self.ffmpegProcess.pid, signal.SIGCONT)
                job = self.getNextPausedJob()
                self.updateQueueJobState(job.getID(), 4)
            else:
                self.runNextWaitJob()

    def moveRowInFiltersGrid(self, index, moveDown):
        rowCount = self.gridLayoutFilters.count()
        if moveDown and index == rowCount-1: return False
        elif not moveDown and index == 0: return False
        items = self.getFilterPositionItems()
        for i in range(len(items)):
            if moveDown:
                if i-1 == index:
                    self.gridLayoutFilters.addItem(items[i-1], i, 0)
                elif i == index:
                    self.gridLayoutFilters.addItem(items[i+1], i, 0)
                else:
                    self.gridLayoutFilters.addItem(items[i], i, 0)
            else:
                if i+1 == index:
                    self.gridLayoutFilters.addItem(items[i+1], i, 0)
                elif i == index:
                    self.gridLayoutFilters.addItem(items[i-1], i, 0)
                else:
                    self.gridLayoutFilters.addItem(items[i], i, 0)
        return True

    def getIndexOfLayoutInFiltersGrid(self, filterLayout):
        layout = self.gridLayoutFilters.layout()
        if not layout: return -1
        index = layout.indexOf(filterLayout)
        return index

    def setFilterBtnStates(self):
        filterPositions = {}
        rowCount = self.gridLayoutFilters.count()
        for key in self.filterAtts:
            atts = self.filterAtts[key]
            index = self.getIndexOfLayoutInFiltersGrid(atts['layout'])
            if index > 0: atts['btnUp'].setEnabled(True)
            else: atts['btnUp'].setEnabled(False)
            if index < rowCount-1: atts['btnDown'].setEnabled(True)
            else: atts['btnDown'].setEnabled(False)
            filterPositions.update({index: key})
        job = self.jobs.getCurrentJob()
        job.setFilterPositions(filterPositions)

    def getFilterPositionItems(self):
        items = []
        rowCount = self.gridLayoutFilters.count()
        for i in range(rowCount):
            item = self.gridLayoutFilters.takeAt(0)
            item.setSizeConstraint(QLayout.SetMinAndMaxSize)
            item.setSpacing(6)
            items.append(item)
        return items

    def loadFilterPositions(self, job):
        items = self.getFilterPositionItems()
        filterPositions = job.getFilterPositions()
        for position in sorted(filterPositions.keys()):
            filter = filterPositions.get(position)
            for item in items:
                name = item.objectName()
                atts = self.filterAtts.get(filter)
                if not atts:
                    msg = 'Filter is not implemented: "%s"' % name
                    self.log(1, msg, 1)
                    self.showMsgBox(msg, btns="ok", icon="warning")
                    return
                layout = atts.get('layout')
                searchName = layout.objectName()
                if name == searchName:
                    self.gridLayoutFilters.addItem(item, int(position), 0)
        self.setFilterBtnStates()

    def loadSections(self, job):
        '''Sets the sections from a job'''
        self.clearSections()
        sections = job.getSections()
        if sections:
            if sections[0]:
                self.setSectionTimeStart(sections[0][0])
                self.setSectionTimeEnd(sections[0][1])
            for section in sections:
                self.sectionAddRow(section[0], section[1])

    def loadTargetDirName(self, job):
        if(job.getTgtDirName()): self.setTgtDirByData(job.getTgtDirName())

    def loadTargetFileName(self, job):
        if(job.getTgtFileName()):
            self.lineEditTgtFileName.setText(job.getTgtFileName())
            self.lineEditTagRateHistoryFile.setText(job.getTgtFileNameLong())

    def loadTargetFileCount(self, job):
        if job.getTgtFileCount():
            self.boxTgtFileCount.setValue(job.getTgtFileCount())
        else:
            self.setTargetFileCount(0)
            if self.btnTgtFileAutoIncrement.isChecked(): self.setTargetFileCount(1)

    def changeTargetFileCount(self, value: int):
        self.boxTgtFileCount.setValue(self.boxTgtFileCount.value()+value)

    def setTargetFileCount(self, value: int):
        self.boxTgtFileCount.setValue(value)

    def setCurrTgtDir(self):
        path = self.cmbTgtDirs.currentData()
        self.jobs.getCurrentJob().setTgtDirName(path)

    def setTgtDirByData(self, path):
        if self.cmbTgtDirs.currentData == path:
            return True
        index = self.cmbTgtDirs.findData(path)
        if not index == -1:
            self.cmbTgtDirs.setCurrentIndex(index)
            return True
        msg = 'Error: Cannot set target path to "%s"' % path
        self.log(1, msg, 1)
        self.showMsgBox(msg, btns="ok", icon="warning")
        return False

    def resetVideoProps(self):
        self.videoProps = {}

    def deleteDeshakeDir(self):
        '''Deletes the deshake directory in the config path'''
        path = self.config.getConfigDeshakePath()
        if path and os.path.isdir(path):
            shutil.rmtree(path)

    def showWarningForKnownFile(self):
        '''Shows a dialog if the currently opened file was already opened in the past'''
        if not self.isFileIsKnownWarningIsActive(): return
        if not self.isTaggerEnabled(): return
        hashID, dateTime = self.isCurrentFileKnown()
        if hashID and dateTime:
            self.log(1, 'Current source file was already opened in the past. (HashID: "%s", Date: %s)' % (hashID, dateTime))
            knownFiles = self.getFileListFromCurrentHashID()
            if knownFiles:
                self.knownUI.setFilesList(knownFiles)
                self.knownUI.show()
            else:
                self.showMsgBox('File was already opened before.', infoText='No target renderings are known.', detailText='Date: %s\nHash ID:%s' % (dateTime, hashID))

    def showWarningForOddVideoSourceSize(self, videoProps):
        '''
        Shows a warning if width or height of a video is odd

        :param videoProps: The video properties dictionary
        '''
        heightIsOdd = False
        if videoProps.get('height') % 2 == 1: heightIsOdd = True
        widthIsOdd = False
        if videoProps.get('width') % 2 == 1: widthIsOdd = True
        msg = ''
        if heightIsOdd and widthIsOdd: msg = 'Width and height of video source file are odd.'
        elif heightIsOdd: msg = 'Height of video source is file odd.'
        elif widthIsOdd: msg = 'Width of video source file is odd.'
        if msg != '': self.showMsgBox(msg, infoText='This can lead to encoding errors. Please crop or resize the video to a size dividable by 2.\n\nVideo size: %s x %s' % (videoProps.get('width'), videoProps.get('height')), icon='warning')

    def isCurrentFileKnown(self):
        '''
        Checks if the currently source file was already opened in PyCut in the past

        :return: HashID and Date if the file is known, else False, False.
        '''
        job = self.jobs.getCurrentJob()
        hash = self.hashFile(job.getSrcFilePathLong())
        if not hash:
            msg = 'Error: The source file cannot be hashed.'
            self.log(1, msg, 1)
            self.showMsgBox(msg, infoText='It is not known if this file was not edited in the past with PyCut.', icon='warning')
            return False, False
        try:
            hashID, dateTime = self.db.getHashData(hash)
            if not hashID:
                self.db.insertHash(hash)
                hashID, dateTime = self.db.getHashData(hash)
                if not hashID:
                    msg = 'Error: Got no hashID for a hash inserted to the database.'
                    self.log(1, msg, 1)
                    self.showMsgBox(msg, icon='warning')
                else:
                    job.setHashID(hashID)
                return False, False
            job.setHashID(hashID)
            return hashID, dateTime
        except Exception as e:
            msg = 'Error on checking for hash info in the database.'
            self.log(1, msg, 1)
            self.showMsgBox(msg, btns="ok", icon="warning", detailText=str(e))
            return False, False

    def getFileListFromCurrentHashID(self):
        '''
        Gets files from the database which were saved with the hash of the current file

        :return: Array with file paths. If none are found, empty array.
        '''
        job = self.jobs.getCurrentJob()
        hashID = job.getHashID()
        if not hashID: return []
        filePaths = self.db.getFileListByHashID(hashID)
        if filePaths: return filePaths
        return []

    def hashFile(self, filePathLong):
        hash = False
        if not os.path.isfile(filePathLong): return hash
        BUF_SIZE = 65536
        md5 = hashlib.md5()
        with open(filePathLong, 'rb') as f:
            while True:
                data = f.read(BUF_SIZE)
                if not data: break
                md5.update(data)
        hash = md5.hexdigest()
        return hash

    def sanitizeSeek(self, value):
        '''
        Seeks a relative value in the player and validates it to set start and end correctly

        :param value: Time value like seconds (+2 jumps 2 seconds forward, -2 jumps 2 seconds backwards)
        '''
        try:
            if value < 0 and self.playerTimeCurrentMs == 0:
                self.setLabelPlayerTimeCurr('0:00:00.000')
                self.playerTimeCurrent = '0:00:00.000'
                self.setSliderPlayerPosFromTimestamp(0)
            elif value < 0 and self.playerTimeCurrentMs+value < 0:
                self.setLabelPlayerTimeCurr('0:00:00.000')
                self.playerTimeCurrent = '0:00:00.000'
                self.setSliderPlayerPosFromTimestamp(0)
                self.playerControl.seek(0, 'absolute', 'exact')
            elif value > 0 and self.playerTimeCurrentMs+value > self.videoProps.get('durationMs'):
                self.sliderPlayer.setValue(self.sliderPlayer.maximum())
                self.playerControl.seek(self.videoProps.get('durationHMS'), 'absolute', 'exact')
            else:
                self.playerControl.seek(value)
        except Exception as e:
            msg = 'Error: Cannot seek played file.'
            self.log(1, msg, 1, traceback=traceback.format_exc())

    def seekFromPlayerSlider(self, value):
        '''Seeks an absolute position based on a player slider value'''
        percentage = (value / self.sliderPlayer.maximum()) * 100
        if percentage <= 0:
            self.setLabelPlayerTimeCurr('0:00:00.000')
            self.setSliderPlayerPosFromTimestamp(0)
            self.playerTimeCurrent = '0:00:00.000'
        elif percentage >= 100:
            self.sliderPlayer.setValue(self.sliderPlayer.maximum())
            self.playerControl.seek(self.videoProps.get('durationHMS'), 'absolute', 'exact')
            self.playerTimeCurrent = self.videoProps.get('durationHMS')
        else:
            self.playerControl.seek(percentage, 'absolute-percent')

    def setSliderPlayerPosFromTimestamp(self, timestamp):
        '''
        Sets the player slider to a position calculated based on a timestamp

        :param timestamp: Timestimp in ms like 123122.304
        '''
        if timestamp >= self.sliderPlayer.maximum():
            self.sliderPlayer.setValue(self.sliderPlayer.maximum())
        elif timestamp > 0:
            percentage = timestamp / self.videoProps.get('durationMs')
            self.sliderPlayer.setValue(int(percentage * self.sliderPlayer.maximum()))
        elif timestamp <= 0:
            self.sliderPlayer.setValue(0)

    def setLabelPlayerTimeCurr(self, timeHMS):
        '''Sets the current time label for the player

        :param: HMS.ms string
        '''
        self.labelPlayerTimeCurr.setText(timeHMS)

    def setCurrentSectionInSlider(self):
        '''Sets the current section time range visually in the player slider'''

        gradient = 'qlineargradient(spread:pad, x1:0, y1:1, x2:1, y2:1, stop:0 BGCOLOR, stop:START1 BGCOLOR, stop:START2 MARKERCOLOR, stop:START3 MARKERCOLOR, stop:START4 CONNCOLOR, stop:END1 CONNCOLOR, stop:END2 MARKERCOLOR, stop:END3 MARKERCOLOR, stop:END4 BGCOLOR, stop:1 BGCOLOR)'

        startPos = (Functions.HMSToTimestamp(self.sectionTimeStart, True) / self.videoProps.get('durationMs'))
        endPos = (Functions.HMSToTimestamp(self.sectionTimeEnd, True) / self.videoProps.get('durationMs'))

        markerWidth = 0.002
        markerColor = 'rgba(225, 225, 225, 225)'
        borderSize = 0.00001

        gradient = gradient.replace('BGCOLOR', self.sliderPlayerBgColor)
        gradient = gradient.replace('MARKERCOLOR', markerColor)
        gradient = gradient.replace('START1', self.sanitizeGradientPos(startPos-(markerWidth/2)-borderSize))
        gradient = gradient.replace('START2', self.sanitizeGradientPos(startPos-(markerWidth/2)))
        gradient = gradient.replace('START3', self.sanitizeGradientPos(startPos+(markerWidth/2)))
        gradient = gradient.replace('START4', self.sanitizeGradientPos(startPos+(markerWidth/2)+borderSize))
        gradient = gradient.replace('END1', self.sanitizeGradientPos(endPos-(markerWidth/2)-borderSize))
        gradient = gradient.replace('END2', self.sanitizeGradientPos(endPos-(markerWidth/2)))
        gradient = gradient.replace('END3', self.sanitizeGradientPos(endPos+(markerWidth/2)))
        gradient = gradient.replace('END4', self.sanitizeGradientPos(endPos+(markerWidth/2)+borderSize))
        if endPos > startPos: gradient = gradient.replace('CONNCOLOR', markerColor)
        else: gradient = gradient.replace('CONNCOLOR', self.sliderPlayerBgColor)

        self.sliderPlayer.setStyleSheet(self.sliderPlayerstyleTemplate.replace('##BG##', gradient))

    def sanitizeGradientPos(self, pos):
        '''Sanitizes a position so it can be safely used in a gradient

        :param pos: a float or int position.
        :return: the position as str
        '''
        if pos <= 0: pos = 0
        if pos >= 1: pos = 1
        return str(pos)

    def log(self, id, line, msgType=0, timestamp=True, traceback=False):
        '''
        Adds a line to a log

        :param line: String to add to the log
        :param msType: 0 = Normal, 1 = Error
        :param timestamp: Adds a timestamp with h:m:s as prefix if true
        :param traceback: Provide a error traceback to print it in a new line after the message (console only)
        '''
        print(line)
        if traceback: print(traceback)
        if timestamp:
            line = '%s %s' % (datetime.datetime.now().strftime('%H:%M:%S'), line)
        if msgType == 1:
            line = '<font color="red">%s</color>' % line
        line = '%s<br>' % line
        textEdit = self.logApp
        if id == 2: textEdit = self.logFFmpeg
        elif id == 3: textEdit = self.logDB
        textEdit.insertHtml(line)
        self.scrollWidgetToEnd(textEdit)

    def isSliderPlayerPressed(self):
        '''
        Checks if the player slider is currently pressed by the user mouse

        :return: True if pressed, else False
        '''
        sliderPressed = False
        try: sliderPressed = self.sliderPlayer.pressed
        except: pass
        return sliderPressed

    def scrollWidgetToEnd(self, element, forceScrolling=False):
        '''
        Scrolls a widget to the end.

        :param forceScrolling: If True, the widget gets scrolled down even if it has focus.
        '''
        scroll = True
        if not forceScrolling:
            if element.hasFocus(): scroll = False
        if scroll: element.verticalScrollBar().setValue(element.verticalScrollBar().maximum() + 1000)

    def setCurrentSectionStart(self):
        self.setSectionTimeStart(self.playerTimeCurrent)
        if self.timeStringToTime(self.sectionTimeStart) > self.timeStringToTime(self.sectionTimeEnd):
            self.setSectionTimeEnd(self.sectionTimeStart)

    def setCurrentSectionEnd(self):
        self.setSectionTimeEnd(self.playerTimeCurrent)
        if self.timeStringToTime(self.sectionTimeEnd) < self.timeStringToTime(self.sectionTimeStart):
            self.setSectionTimeStart(self.sectionTimeEnd)

    def setSectionTimeStart(self, value):
        '''
        Setter for the current section starting time

        :param value: HMS time string
        '''
        self.sectionTimeStart = value
        self.btnCurrentSectionStart.setText(value)
        self.setCurrentSectionInSlider()

    def setSectionTimeEnd(self, value):
        '''
        Setter for the current section ending time

        :param value: HMS time string
        '''
        self.sectionTimeEnd = value
        self.btnCurrentSectionEnd.setText(value)
        self.setCurrentSectionInSlider()

    def setTagsTreeStyle(self):
        '''Sets the TagsTree Stylesheet'''
        self.listWidgetTagsTree.setStyleSheet("""
            QListWidget::item {
                border-style: solid;
                border-width: 1px;
                border-color: """ + str(QPalette().color(QPalette.ToolTipBase).name()) + """;
                background-color: """ + str(QPalette().color(QPalette.Base).name()) + """;
                margin: 0;
                padding: 0;
                line-height: 0;
                height: 12px;
                max-height: 12px;
            }
            QListWidget::item:selected {
                background-color: #7f7f7f;
            }
            QListWidget::item:hover {
                color: #333333;
                background-color: #bbbbbb;
            }
        """)

    def killFFmpegProcess(self):
        if self.ffmpegProcess:
            os.kill(self.ffmpegProcess.pid, signal.SIGKILL)
            self.ffmpegKilled = True

app = QtWidgets.QApplication(sys.argv)
window = MainUi()
# Debug Start
test_input_path = '/home/vommie/videos/pycut/input'
if os.path.exists(test_input_path) and os.path.isdir(test_input_path):
    test_file = 'test_color.mp4'
    test_file = 'test_shake.mp4'
    test_file = 'test_interlace.avi'
    test_file = 'decoding_issues.m4v'
    test_file = 'noaudio.mp4'
    window.newFile('%s/%s' % (test_input_path, test_file))
# Debug End
app.exec_()
