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

from libs.mpv import *

from classes.PlayerControl import PlayerControl
from classes.DirsUI import DirsUI
from classes.TagsFilterUI import TagsFilterUI
from classes.LogUi import LogUi
from classes.Functions import Functions
from classes.Config import Config
from classes.Jobs import Jobs
from classes.FFmpegThread import FFmpegThread
from classes.DB import DB

from PyQt5 import QtWidgets, uic, QtGui
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QFont, QFontDatabase
import res  # pyrcc5 -o res.py res/res.qrc

import ffmpeg

class MainUi(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        _id = QtGui.QFontDatabase.addApplicationFont('res/font_droid_sans_mono_nerd.otf') # Init Nerd Fronts Font for Icons
        super(MainUi, self).__init__()
        uic.loadUi('./gui/main.ui', self)
        self.initMembers()
        self.initGui()
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
        self.tagsFilterUI = TagsFilterUI(self)
        self.config.setTaggerDBPath('/home/vommie/.config/xnviewmp/XnView.db') # Todo: Set path per UI
        self.db = DB(self.config.getTaggerDBPath(), self.log)
        self.labelTaggerError.setHidden(True)
        self.tagsTree = []
        self.lastTagIDs = []
        self.lastRating = 0
        self.logUi = LogUi(self)
        self.timeFormat = '0:00:0.0'
        self.playerTimeCurrent = self.timeFormat
        self.frameStep = False
        self.jobsSwapping = False # Prevents crash when printing progress while jobs in queue getting switched
        self.resetVideoProps()
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
        # GUI elements options
        header = self.tableSections.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header = self.tableQueue.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        # Set GUI from config
        self.updateDirs(self.config.getTargetDirs())
        self.cmbTgtDirs.setCurrentText(self.config.getTgtDirName())
        if self.config.getQueueIsPaused():
            self.btnQueuePause.setChecked(True)
            self.toggleQueuePause()
        self.btnTgtFileAutoIncrement.setChecked(self.config.getAppIncrementFilename())
        # Queue Jobs
        if len(self.jobs.jobs.items()) > 1:
            for id, job in self.jobs.jobs.items():
                try:
                    int(id) # Skip 'default' job
                    state = job.getState()
                    if state == 4:
                        job.setErrorID(-105)
                        job.setErrorMsg('Job had state "Rendering" when the program started.')
                        job.setState(3)
                        state = 3
                    elif state == 5:
                        job.setErrorId(-124)
                        job.setErrorMsg('Job had state "Paused" when the program started.')
                        job.setState(3)
                        state = 3
                    self.queueAddRow(id, job.getTgtFileNameLong(), self.getJobStateString(state))
                    if state == 0 and not self.btnQueuePause.isChecked():
                        self.runNextWaitJob()
                except: pass
        else:
            self.deleteDeshakeDir()
        self.tableQueue.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tableQueue.customContextMenuRequested.connect(self.onQueueContextMenu)
        self.renderFrame.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.renderFrame.setAttribute(Qt.WA_NativeWindow)
        # Add custom slider to control the player time position
        self.sliderPlayer = Slider(Qt.Horizontal)
        self.framePlayerProgress.insertWidget(0, self.sliderPlayer)
        self.sliderPlayerIsPressed = False
        self.sliderPlayer.setMinimum(0)
        self.sliderPlayer.setMaximum(99 * self.config.getPlayerSliderFactor())
        # Init categories tree
        self.tagsTreeItemPrefix =  ''
        self.tagsTreeSpaceChar = ' '
        self.buildTagsTree(-1)
        # Tagger
        self.setHistoryMode(False)
        self.btnTaggerActive.setChecked(self.config.getTaggerIsActive())
        self.btnTaggerWarning.setChecked(self.config.getTaggerIsWarningActive())

    def initGuiEvents(self):
        # Player control
        self.btnPause.clicked.connect(self.onBtnPauseClicked)
        self.btnFrameStep.clicked.connect(self.onBtnFrameStepClicked)
        self.btnFrameStepBack.clicked.connect(self.onBtnFrameStepBackClicked)
        self.btnSectionStart.clicked.connect(self.onBtnSectionStartClicked)
        self.btnSectionEnd.clicked.connect(self.onBtnSectionEndClicked)
        self.btnSectionAdd1.clicked.connect(self.onBtnSectionAddClicked)
        self.btnMute.clicked.connect(self.onBtnMuteClicked)
        self.sliderVolume.sliderMoved.connect(self.onSliderVolumeMoved)
        self.sliderVolume.sliderReleased.connect(self.onSliderVolumeReleased)
        # Player Progress
        self.sliderPlayer.sliderMoved.connect(self.onSliderPlayerMoved)
        self.sliderPlayer.sliderPressed.connect(self.onSliderPlayerPressed)
        self.sliderPlayer.sliderReleased.connect(self.onSliderPlayerReleased)
        # Sections
        self.tableSections.currentCellChanged.connect(self.onTableSectionCurrCellChanged)
        self.tableSections.itemDoubleClicked.connect(self.onTableSectionItemDblClicked)
        self.btnSectionAdd2.clicked.connect(self.onBtnSectionAddClicked)
        self.btnSectionDelete.clicked.connect(self.onBtnSectionDeleteClicked)
        self.btnSectionUp.clicked.connect(self.onBtnSectionUpClicked)
        self.btnSectionDown.clicked.connect(self.onBtnSectionDownClicked)
        # Job Finalization
        self.lineEditTgtFileName.textChanged.connect(self.onLineEditTgtFileNameChanged)
        self.boxTgtFileCount.valueChanged.connect(self.onBoxFileCountChanged)
        self.btnExportSave.clicked.connect(self.onBtnExportSave)
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
        self.actionQuit.triggered.connect(self.onExit)
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

    def initPlayer(self):
        self.renderFrame = self.findChild(QtWidgets.QWidget, 'renderFrame')
        self.renderFrame.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.renderFrame.setAttribute(Qt.WA_NativeWindow)
        import locale
        locale.setlocale(locale.LC_NUMERIC, 'C')
        player = MPV(wid=str(int(self.renderFrame.winId())), vo='x11', log_handler=print, loglevel='fatal')
        # player = MPV(wid=str(int(self.renderFrame.winId())), vo='x11', log_handler=print, loglevel='debug')
        self.playerControl = PlayerControl(player, self.config)
        self.playerControl.volume(self.config.getPlayerVolume())
        self.setMuteState(self.config.getPlayerIsMuted())
        # Register observers
        self.playerControl.player.observe_property('pause', self.onPlayerPause)
        self.playerControl.player.observe_property('percent-pos', self.onPlayerPercentPos)
        self.playerControl.player.observe_property('duration', self.onPlayerDuration)
        self.playerControl.player.observe_property('time-pos', self.onPlayerTimePos)
        self.playerControl.player.observe_property('volume', self.onPlayerVolume)

    def newFile(self, videoFilePath = False):
        '''
        Loads a file as new curent job into PyCut. (Re)sets the GUI.

        :param videoFilePath: The path to the video file to open. If not set, the currently selected job in the queue gets loaded.
        '''
        self.log(1, '---New File-----------------------------------')
        self.log(3, '---New File -----------------------------------')
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
            if self.btnTgtFileAutoIncrement.isChecked(): self.setTargetFileCount(1)
            else: self.setTargetFileCount(0)
        if not videoFilePath: videoFilePath = job.getSrcFilePathLong()
        self.log(1, 'Source path: "%s".' % videoFilePath)
        # Get Video Props
        self.videoProps = Functions.getVideoProperties(videoFilePath)
        self.log(1, 'Video properties: %s' % self.videoProps)
        # Set properties
        self.loadFilterCrop(job)
        self.loadFilterDeinterlace(job)
        self.loadFilterRotate(job)
        self.loadFilterResize(job)
        self.loadFilterDeshake(job)
        self.loadFilterPositions(job)
        self.loadSections(job)
        self.loadTargetFileName(job)
        self.loadTargetFileCount(job)
        self.playerTimeCurrent = self.timeFormat
        self.sectionTimeStart = self.timeFormat
        self.setFilterBtnStates()
        # Load video file
        if self.videoProps:
            self.playerControl.play(videoFilePath)
            self.setPlayerControlsState(True)

    def loadFilterCrop(self, job):
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

    def loadFilterDeinterlace(self, job):
        state = job.getFilterDeinterlaceState()
        if not state: self.resetDeinterlaceFilter()
        if state:
            self.btnFilterDeinterlace.setChecked(True)
        deinterlacer = job.getFilterDeinterlaceDeinterlacer()
        self.comboBoxFilterDeinterlaceDeinterlacer.setCurrentText(deinterlacer)


    def loadFilterRotate(self, job):
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

    def loadFilterResize(self, job):
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

    def loadFilterDeshake(self, job):
        state = job.getFilterDeshakeState()
        if state: self.btnFilterDeshake.setChecked(True)
        else: self.btnFilterDeshake.setChecked(False)

    def saveSession(self):
        '''
        Saves the current job session as new job and into the database
        '''
        if(self.historyMode): return False
        self.log(1, 'Saving current session ...')
        currentJob = self.jobs.getCurrentJob()
        if not currentJob.getSections():
            currentJob.addSection(self.timeFormat, self.videoProps['duration'])
        job = self.addCurrentJobToQueue()
        if not job: return False
        if not self.saveCurrentTagsAndRating(): return
        if self.btnTgtFileAutoIncrement.isChecked(): self.changeTargetFileCount(1)
        self.log(1, 'Session saved as new job in queue.')

    def addCurrentJobToQueue(self):
        '''Adds the current job session as new job to the jobs queue'''
        job = False
        try:
            id, job = self.jobs.saveCurrentJob()
            state = job.getState()
            iRow = self.queueAddRow(id, job.getTgtFileNameLong(), self.getJobStateString(state))
            job.setPosition(iRow)
            self.runNextWaitJob()
        except Exception as e:
            msg = 'Error: Cannot add session to job queue.'
            self.log(1, msg, 1)
            self.showMsgBox(msg, detailText=str(e), icon='critical')
        return job

    def runNextWaitJob(self):
        self.log(1, 'Running next job ...')
        if self.ffmpegProcess or self.btnQueuePause.isChecked():
            return False
        job = self.getNextWaitingJob()
        if job and self.checkJobForRenderbility(job):
            self.FFmpegThread = FFmpegThread(job, self.config.getConfigDeshakePath())
            self.FFmpegThread.finished.connect(self.onFFmpegThreadFinished)
            self.FFmpegThread.ffmpegStart.connect(self.onFFmpegStart)
            self.FFmpegThread.ffmpegProcess.connect(self.onFFmpegProgress)
            self.FFmpegThread.ffmpegExit.connect(self.onFFmpegExit)
            self.FFmpegThread.start()
            self.log(1, 'FFmpeg thread started.')

    def checkJobForRenderbility(self, job):
        if Functions.isSameString(job.getSrcFilePathLong(), job.getTgtFilePathLong()):
            msg = 'Error: Input and Output Path are the same.'
            self.log(1, msg, 1)
            self.onFFmpegExit([job, -100, msg, msg, False])
            self.showMsgBox(msg, btns="ok", icon="critical")
            return False
        if len(job.getSections()) == 0:
            msg = 'Error: No sections to render.'
            self.log(1, msg, 1)
            self.onFFmpegExit([job, -101, msg, msg, False])
            self.showMsgBox(msg, btns="ok", icon="critical")
            return False
        return True

    def getNextWaitingJob(self):
        return self.getNextJobByStateID(0)

    def getNextPausedJob(self):
        return self.getNextJobByStateID(5)

    def getNextRenderingJob(self):
        return self.getNextJobByStateID(4)

    def getNextJobByStateID(self, stateID):
        job = False
        jobItems = self.tableQueue.findItems(self.getJobStateString(stateID), Qt.MatchExactly)
        if(jobItems):
            iRow = self.tableQueue.row(jobItems[0])
            jobItem = self.tableQueue.item(iRow, 0)
            jobIndex = jobItem.text()
            job = self.jobs.getJob(jobIndex)
        return job

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

    def onPlayerPercentPos(self, action, pos):
        try:
            if not self.sliderPlayerIsPressed:
                self.sliderPlayer.setValue(int(pos * self.config.getPlayerSliderFactor()))
        except:
            pass

    def onPlayerTimePos(self, action, timestamp):
        # Convert timestamp format s.ms to h:m:s.ms
        try:
            timeSplit = str(timestamp).split('.', 1)
            timeMs = timeSplit[1]
            if len(timeMs) == 1:
                timeMs = '%s0' % timeSplit[1]
            timeMs = '{:03d}'.format(int(timeSplit[1][:3]))
            time = "%s.%s" % (Functions.convertSecondsToHMFS(
                int(timeSplit[0])), timeMs)
            self.playerTimeCurrent = time
            self.labelPlayerTimeCurr.setText(time)
        except:
            pass

    def onPlayerDuration(self, action, duration):
        self.duration = duration

    def onPlayerVolume(self, action, volume):
        self.sliderVolume.setValue(int(volume))

    # GUI control event handlers

    def onExit(self):
        self.closeApp()

    def closeEvent(self, event):
        self.closeApp()

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
        self.playerControl.pause()

    def onBtnFrameStepClicked(self):
        self.frameStep = True
        self.playerControl.frameStep()
        self.btnPause.setText('契')

    def onBtnFrameStepBackClicked(self):
        self.playerControl.frameBackStep()
        self.btnPause.setText('契')

    def onBtnSectionStartClicked(self):
        self.sectionTimeStart = self.playerTimeCurrent
        if self.timeStringToTime(self.sectionTimeStart) > self.timeStringToTime(self.sectionTimeEnd):
            self.sectionTimeEnd = self.sectionTimeStart
        self.setBtnSectionAddState()

    def onBtnSectionEndClicked(self):
        self.sectionTimeEnd = self.playerTimeCurrent
        if self.timeStringToTime(self.sectionTimeEnd) < self.timeStringToTime(self.sectionTimeStart):
            self.sectionTimeStart = self.sectionTimeEnd
        self.setBtnSectionAddState()

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

    def onTableSectionCurrCellChanged(self):
        self.setSectionBtnStates()

    def onTableSectionItemDblClicked(self, item):
        timeStr = item.text()
        self.playerControl.seek(timeStr, 'absolute+exact')

    def onSliderPlayerMoved(self, value):
        self.sliderPlayerIsPressed = True
        self.setPlayerPosByPlayerSlider()

    def onSliderPlayerPressed(self):
        self.sliderPlayerIsPressed = True

    def onSliderPlayerReleased(self):
        self.sliderPlayerIsPressed = False
        self.setPlayerPosByPlayerSlider()

    def onLineEditTgtFileNameChanged(self, text):
        self.jobs.getCurrentJob().setTgtFileName(text)
        self.setBtnExportSaveState()

    def onBoxFileCountChanged(self, text):
        self.jobs.getCurrentJob().setTgtFileCount(text)

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
        self.config.setTgtDirName(text)
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

    def onSliderVolumeMoved(self):
        self.setMuteState(False)
        self.playerControl.volume(self.sliderVolume.value())

    def onSliderVolumeReleased(self):
        self.setMuteState(False)
        self.playerControl.volume(self.sliderVolume.value())

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
        self.setBtnRating(self.lastRating)

    def onBtnTagsClearClicked(self):
        self.clearTagsTree()

    def onBtnLastRatingClicked(self):
        self.setBtnRating(self.lastRating)

    def onBtnTaggerActiveClicked(self):
        self.config.setTaggerIsActive(not self.config.getTaggerIsActive())

    def onBtnTaggerWarningClicked(self):
        self.config.setTaggerIsWarningActive(not self.config.getTaggerIsWarningActive())

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
        if line[0] == 'progress':
            if line[1] == 'end':
                # Todo: Reset progress bar
                pass
        elif line[0] == 'speed':
            # Todo: Set speed label
            pass
        elif line[0] == 'fps':
            # Todo: set fps label
            pass
        elif line[0] == 'out_time':
            currentSecond = int(
                Functions.timeStrToSeconds(line[1][:-3], True) * 100)
            totalSeconds = int(totalSeconds * 100)
            if currentSecond > totalSeconds:
                currentSecond = totalSeconds
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
        state = job.getState()
        if code == 0:
            state = 1
        else:
            if not self.ffmpegKilled: job.setErrorID(code)
            else:
                self.ffmpegKilled = False
                job.setErrorID(-332)
                errorMsg = 'ffmpeg killed while rendering by the user.\n\n%s' % errorMsg
            state = 3
        if errorMsg != '':
            job.setErrorMsg(errorMsg)
        job.setState(state)
        if self.btnQueueKill.isEnabled():
            self.btnQueueKill.setEnabled(False)
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
        if not self.progressBarRender.isEnabled():
            self.progressBarRender.setEnabled(True)
        self.progressBarRender.setMaximum(int(totalSeconds * 100))
        self.progressBarRender.setValue(0)
        if not self.btnQueueKill.isEnabled():
            self.btnQueueKill.setEnabled(True)

    def onFFmpegThreadFinished(self):
        self.ffmpegProcess = False

    # GUI Control

    def onMsgBoxBtn(self, btn):
        print(btn)

    def showMsgBox(self, msg, btns="ok", icon="info", infoText='', detailText='', title='PyCut Message'):
        '''
        Shows a QMessageBox dialog.

        :param msg: The message to display
        :param btns: Choices. Default = "ok". Options: "okcancel", "save", "savecancel", "yesno", "retry", "retryabort", "close"
        :param icon: Icon. Default "info". Options: "info", "question", "warning", "critical". Set to False for no icon.
        :param infoText: Info text which gets displayed below the main message
        :param detailText: Detail text which gets displayed if the user clicks on a "details" button
        :param title: Title of the message box.
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
        msgBox.buttonClicked.connect(self.onMsgBoxBtn)
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
                if 'filter' in tag and tag['filter']: continue
                item = QListWidgetItem('%s%s' % (self.tagsTreeItemPrefix, tag['label']))
                item.setToolTip('TagID: %s' % tag['tagID'])
                fontWeight = -1
                if tag['parentID'] == -1: fontWeight = QFont.Bold
                item.setFont(QFont('DejaVu Sans Mono', -1, weight=fontWeight))
                self.listWidgetTagsTree.addItem(item)
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
                imageID = self.db.insertNewImage(folderID, job.getTgtFileNameLong())
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

    def saveCurrentTagsAndRating(self):
        '''
        Saves the current tags and rating for the target file to the database

        :param return: False if something went wrong. -1 if MsgBox is active due to missing rating or tags. True if successfully saved.
        '''
        if not self.isTaggerEnabled(): return False
        self.log(1, 'Save Tags and Rating to DB ...')
        job = self.jobs.getCurrentJob()
        tagIDs = self.getSelectedTagIDsFromTagsTree()
        rating = self.getRatingFromBtns()

        if self.isTaggerWarningActive():
            if not tagIDs and not rating:
                if not self.showMsgBox('No rating and no tags are set.', btns='yesno', icon='question', infoText='Save anyways?'): return False
            elif not tagIDs:
                if not self.showMsgBox('No rating is set.', btns='yesno', icon='question', infoText='Save anyways?'): return False
            elif not rating:
                if not self.showMsgBox('No tags are set.', btns='yesno', icon='question', infoText='Save anyways?'): return False

        try:
            folderID = self.db.getFolderID(job.getTgtDirName())
            if not folderID: folderID = self.db.insertNewPath(job.getTgtDirName())
            if not folderID:
                msg = 'Error: Got no folderID. Cannot save tags and rating.'
                self.log(1, msg, 1)
                self.showMsgBox(msg, btns='ok', icon='warning')
                return False
            imageID = self.db.getImageID(folderID, job.getTgtFileNameLong())
            if not imageID: imageID = self.db.insertNewImage(folderID, job.getTgtFileNameLong())
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

        self.log(1, 'Save rating to database ...')
        try: self.db.setRating(imageID, folderID, rating)
        except:
            msg = 'Error: No database connection possible'
            self.log(1, msg, 1)
            self.showMsgBox(msg, btns='ok', icon="warning")
            self.disableTaggerPanel()
            return False
        self.log(1, 'Rating saved: %s' % rating)

        self.log(1, 'Save tags to database ...')
        try: self.db.setTags(imageID, tagIDs)
        except:
            msg = 'Error: No database connection possible'
            self.log(1, msg, 1)
            self.showMsgBox(msg, btns='ok', icon="warning")
            self.disableTaggerPanel()
            return False
        self.log(1, 'Tags saved: %s' % tagIDs)

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
            item = tag['item']
            if item.isSelected():
                tagIDs.append(tag['tagID'])
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
        for tagID in tagIDs:
            for tag in self.tagsTree:
                if tag['tagID'] == tagID:
                    tag['item'].setSelected(True)
                    selected.append(tag['item'].text().replace(self.tagsTreeSpaceChar, ''))
        if tagIDs: self.log(1, 'Selecting tags: %s' % ', '.join(selected))

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
        if tagIDs: self.log(1, 'Filter TagIDs: %s' % tagIDs)
        else: self.log(1, 'No TagIDs to filter')
        self.tagsTree = self.setFilterStateForTagsTree(self.tagsTree)
        self.listWidgetTagsTree.clear()
        self.buildTagsTree(-1)

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
            if tag['tagID'] in filterTagIDs: tagsTree[i]['filter'] = True
            else: tagsTree[i]['filter'] = False
        return tagsTree

    def checkDBConnectivity(self):
        '''Checks if the database is available and sets Tagger panel status based on the result'''
        if self.db.testConnection(): self.enableTaggerPanel()
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

    def setPlayerPosByPlayerSlider(self):
        value = self.sliderPlayer.value()
        percentage = value / self.config.getPlayerSliderFactor()
        self.playerControl.seek(percentage, 'absolute-percent+exact')

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
        self.sectionTimeStart = self.timeFormat
        self.sectionTimeEnd = self.videoProps['duration']
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
        itemState = QTableWidgetItem(state)
        self.tableQueue.setItem(iRow, 0, itemID)
        self.tableQueue.setItem(iRow, 1, itemFilename)
        self.tableQueue.setItem(iRow, 2, itemState)
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

    def updateDirs(self, dirs):
        '''
        Updates the target directory combo box
        '''
        self.dirs = dirs
        self.config.setDirs(dirs)
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
        errorMsg = job.getErrorMsg()
        self.logUi.setTitle('Log for Job %s' % jobID)
        self.logUi.setLogText(errorMsg.replace('\\n', '\n'))
        self.logUi.show()

    def toggleQueuePause(self):
        if self.btnQueuePause.isChecked():
            self.btnQueuePause.setText('契')
            self.config.setQueueIsPaused(True)
            if self.ffmpegProcess:
                os.kill(self.ffmpegProcess.pid, signal.SIGSTOP)
                job = self.getNextRenderingJob()
                self.updateQueueJobState(job.getID(), 5)
        else:
            self.btnQueuePause.setText('')
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
        self.clearSections()
        sections = job.getSections()
        if sections:
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
            self.boxTgtFileCount.setValue(0)

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

    def log(self, id, line, msgType=0, timestamp=True):
        '''
        Adds a line to a log

        :param line: String to add to the log
        :param msType: 0 = Normal, 1 = Error
        :param timestamp: Adds a timestamp with h:m:s as prefix if true
        '''
        print(line)
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

    def scrollWidgetToEnd(self, element, forceScrolling=False):
        '''
        Scrolls a widget to the end.

        :param forceScrolling: If True, the widget gets scrolled down even if it has focus.
        '''
        scroll = True
        if not forceScrolling:
            if element.hasFocus(): scroll = False
        if scroll: element.verticalScrollBar().setValue(element.verticalScrollBar().maximum())

    def killFFmpegProcess(self):
        if self.ffmpegProcess:
            os.kill(self.ffmpegProcess.pid, signal.SIGKILL)
            self.ffmpegKilled = True

    def closeApp(self):
        self.config.setAppGeometry(self.saveGeometry())
        self.config.setAppState(self.saveState())

# Custom slider class lets user clicks on position
class Slider(QtWidgets.QSlider):

    def mousePressEvent(self, event):
        super(Slider, self).mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            val = self.pixelPosToRangeValue(event.pos())
            self.setValue(val)
            self.sliderMoved.emit(val)
            self.sliderReleased.emit()

    def pixelPosToRangeValue(self, pos):
        opt = QtWidgets.QStyleOptionSlider()
        self.initStyleOption(opt)
        gr = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt, QtWidgets.QStyle.SC_SliderGroove, self)
        sr = self.style().subControlRect(QtWidgets.QStyle.CC_Slider, opt, QtWidgets.QStyle.SC_SliderHandle, self)

        if self.orientation() == Qt.Horizontal:
            sliderLength = sr.width()
            sliderMin = gr.x()
            sliderMax = gr.right() - sliderLength + 1
        else:
            sliderLength = sr.height()
            sliderMin = gr.y()
            sliderMax = gr.bottom() - sliderLength + 1
        pr = pos - sr.center() + sr.topLeft()
        p = pr.x() if self.orientation() == Qt.Horizontal else pr.y()
        return QtWidgets.QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), p - sliderMin, sliderMax - sliderMin, opt.upsideDown)

app = QtWidgets.QApplication(sys.argv)
window = MainUi()
# window.newFile('/home/vommie/dev/personal/pycut/test_color.mp4')
# window.newFile('/home/vommie/dev/personal/pycut/test_shake.mp4')
window.newFile('/home/vommie/dev/personal/pycut/test_interlace.avi')
app.exec_()
