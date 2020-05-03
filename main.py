#!/usr/bin/env python3

import sys
import datetime
import json
import subprocess
import os
import signal

from libs.mpv import *

from classes.PlayerControl import PlayerControl
from classes.DirsUi import DirsUi
from classes.LogUi import LogUi
from classes.Functions import Functions
from classes.Config import Config
from classes.Jobs import Jobs
from classes.FFmpegThread import FFmpegThread
from classes.DB import DB

from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon
import res  # pyrcc5 -o res.py res/res.qrc

import ffmpeg

class MainUi(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(MainUi, self).__init__()
        uic.loadUi('./gui/main.ui', self)
        self.initMembers()
        self.initGui()
        self.initGuiEvents()
        self.initPlayer()
        self.show()

    def initMembers(self):
        self.config = Config()
        self.jobsFilePath = 'jobs.json'
        self.jobs = Jobs(self.jobsFilePath)
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
        self.dirsUi = DirsUi(self)
        self.db = DB(self.config.getDBPath())
        self.logUi = LogUi(self)
        self.timeFormat = '0:00:0.0'
        self.playerTimeCurrent = self.timeFormat
        self.sectionTimeStart = self.timeFormat
        self.sectionTimeEnd = self.timeFormat
        self.iconPlay = QIcon(':/icons/ic_play_arrow_24px.svg')
        self.iconPause = QIcon(':/icons/ic_pause_24px.svg')
        self.iconIsMuted = QIcon(':/icons/ic_volume_off_24px.svg')
        self.iconIsNotMuted = QIcon(':/icons/ic_volume_up_24px.svg')
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
        # Queue Jobs
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
            except:
                pass
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
        self.btnPause.setIcon(self.iconPause)
        # Init categories tree
        self.buildCategoriesTree()

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
        self.btnTgtWxSuffix.clicked.connect(self.onBtnExportWxClicked)
        self.btnExportSave.clicked.connect(self.onBtnExportSave)
        self.btnExportDirs.clicked.connect(self.onBtnExportDirsClicked)
        self.cmbTgtDirs.currentTextChanged.connect(self.onCmbTgtDirsCurrTextChanged)
        # Filters
        self.btnFilterCrop.clicked.connect(self.onBtnFilterCropClicked)
        self.btnFilterCrop.toggled.connect(self.onBtnFilterCropClicked)
        self.boxFilterCropT.valueChanged.connect(self.onBoxFilterCropTChanged)
        self.boxFilterCropR.valueChanged.connect(self.onBoxFilterCropRChanged)
        self.boxFilterCropB.valueChanged.connect(self.onBoxFilterCropBChanged)
        self.boxFilterCropL.valueChanged.connect(self.onBoxFilterCropLChanged)
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
        self.actionShowError.triggered.connect(self.onQueueCtxActionShowError)

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

    def newFile(self, videoFilePath):
        self.log(1, 'New File ...')
        self.log(1, 'Path: %s' % videoFilePath)
        # Reset GUI and variables
        self.resetVideoProps()
        self.resetSections()
        self.resetCropFilter()
        self.resetRotateFilter()
        self.resetResizeFilter()
        self.resetDeshakeFilter()
        self.btnTgtWxSuffix.setChecked(False)
        self.boxTgtFileCount.setValue(0)
        self.playerTimeCurrent = self.timeFormat
        self.sectionTimeStart = self.timeFormat
        # Create new job
        self.jobs.newCurrentJob(videoFilePath)
        self.setCurrTgtDir()
        self.lineEditTgtFileName.setText(self.jobs.getCurrentJob().getTgtFileName())
        # Load video file
        self.videoProps = Functions.getVideoProperties(videoFilePath)
        if self.videoProps:
            self.playerControl.play(videoFilePath)
            self.setPlayerControlsState(True)
        # Other
        self.setFilterBtnStates()

    def loadJobFromQueue(self):
        self.log(1, 'Loading job from queue ...')
        jobID = self.queueGetJobIDFromRow()[0]
        job = self.jobs.getJob(jobID)
        self.log(1, 'JobID: %s, Object: %s' % (jobID, job))
        self.newFile(job.getSrcFilePathLong())
        if not self.setTgtDirByData(job.getTgtDirName()):
            self.log(1, 'Error: Cannot set target path found in job')
        sections = job.getSections()
        for section in sections:
            self.sectionAddRow(section[0], section[1])
            self.jobs.getCurrentJob().addSection(section[0], section[1])
        self.boxTgtFileCount.setValue(job.getTgtFileCount())
        self.lineEditTgtFileName.setText(job.getTgtFileName())
        self.loadFilterCrop(job)
        self.loadFilterRotate(job)
        self.loadFilterResize(job)
        self.loadFilterDeshake(job)
        self.loadFilterPositions(job)

    def loadFilterCrop(self, job):
        state = job.getFilterCropState()
        if state: self.btnFilterCrop.setChecked(True)
        else: self.btnFilterCrop.setChecked(False)
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

    def loadFilterRotate(self, job):
        rotation = job.getFilterRotate()
        if rotation == 90:
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
        if state: self.btnFilterResize.setChecked(True)
        else: self.btnFilterResize.setChecked(False)
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

    def addJob(self):
        id, job = self.jobs.saveCurrentJob()
        state = job.getState()
        iRow = self.queueAddRow(id, job.getTgtFileNameLong(), self.getJobStateString(state))
        job.setPosition(iRow)
        self.runNextWaitJob()

    def runNextWaitJob(self):
        self.log(1, 'Running next job ...')
        if self.ffmpegProcess or self.btnQueuePause.isChecked():
            return False
        job = self.getNextWaitingJob()
        self.log(1, 'Job: %s' % job)
        if job and self.checkJobForRenderbility(job):
            self.FFmpegThread = FFmpegThread(job)
            self.FFmpegThread.finished.connect(self.onFFmpegThreadFinished)
            self.FFmpegThread.ffmpegStart.connect(self.onFFmpegStart)
            self.FFmpegThread.ffmpegProcess.connect(self.onFFmpegProgress)
            self.FFmpegThread.ffmpegExit.connect(self.onFFmpegExit)
            self.FFmpegThread.start()
            self.log(1, 'FFmpeg thread started.')

    def checkJobForRenderbility(self, job):
        if Functions.isSameString(job.getSrcFilePathLong(), job.getTgtFilePathLong()):
            msg = 'Error: Input and Output Path are the same.'
            self.log(1, msg)
            self.onFFmpegExit([job, -100, msg, msg])
            return False
        if len(job.getSections()) == 0:
            msg = 'Error: No sections to render.'
            self.log(1, msg)
            self.onFFmpegExit([job, -101, msg, msg])
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
            self.btnMute.setIcon(self.iconIsMuted)
        else:
            self.btnMute.setIcon(self.iconIsNotMuted)

    # Player observer event handlers

    def onPlayerPause(self, action, state):
        if not self.frameStep:
            if state:
                self.btnPause.setIcon(self.iconPlay)
            else:
                self.btnPause.setIcon(self.iconPause)
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
        self.btnPause.setIcon(self.iconPlay)

    def onBtnFrameStepBackClicked(self):
        self.playerControl.frameBackStep()
        self.btnPause.setIcon(self.iconPlay)

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

    def onBtnExportWxClicked(self):
        if self.btnTgtWxSuffix.isChecked():
            self.jobs.getCurrentJob().addTgtFileSuffix('[WX]')
        else:
            self.jobs.getCurrentJob().removeTgtFileSuffix('[WX]')

    def onLineEditTgtFileNameChanged(self, text):
        self.jobs.getCurrentJob().setTgtFileName(text)
        self.setBtnExportSaveState()

    def onBoxFileCountChanged(self, text):
        self.jobs.getCurrentJob().setTgtFileCount(text)

    def onBtnExportSave(self):
        self.addJob()

    def onBtnExportDirsClicked(self):
        self.dirsUi.show()

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
            self.queueShowError()

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
        self.loadJobFromQueue()

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
            if state == 3:
                menu.addAction(self.actionShowError)
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

    def onQueueCtxActionShowError(self):
        self.queueShowError()

    def onBtnFilterCropDownClicked(self):
        index = self.getIndexOfLayoutInFiltersGrid(self.layoutFilterCrop)
        self.moveRowInFiltersGrid(index, True)
        self.setFilterBtnStates()

    def onBtnFilterCropUpClicked(self):
        index = self.getIndexOfLayoutInFiltersGrid(self.layoutFilterCrop)
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

    # Other Event handlers

    # Event handler while ffmpeg is rendering
    @pyqtSlot('PyQt_PyObject')
    def onFFmpegProgress(self, atts):
        line, job, totalSeconds = atts
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
        job, code, output, error = atts
        if self.progressBarRender.isEnabled():
            self.progressBarRender.setValue(0)
            self.progressBarRender.setEnabled(False)
        state = job.getState()
        if code == 0:
            state = 1
        else:
            if not self.ffmpegKilled:
                job.setErrorID(code)
                job.setErrorMsg(str(error))
            else:
                self.ffmpegKilled = False
                job.setErrorID(-332)
                job.setErrorMsg('ffmpeg killed while rendering by the user.')
            state = 3
        job.setState(state)
        if self.btnQueueKill.isEnabled():
            self.btnQueueKill.setEnabled(False)
        # todo append output and error to job, display it if clicked on queue item
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

    def buildCategoriesTree(self):
        tagTree = self.db.getCategoriesTree()
        print(tagTree)
        for tag in tagTree:
            tag = tagTree[tag]
            self.listWidgetTagsTree.addItem(tag['label'])

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

    def resetSections(self):
        for i in range(self.tableSections.rowCount()):
            self.tableSections.removeRow(0)

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
        self.btnFilterRotateRight.setChecked(False)
        self.btnFilterRotateRight.setChecked(False)

    def resetResizeFilter(self):
        self.boxFilterResizeW.setValue(0)
        self.boxFilterResizeH.setValue(0)
        self.btnFilterResize.setChecked(False)

    def resetDeshakeFilter(self):
        self.btnFilterDeshake.setChecked(False)

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
        if len(self.cmbTgtDirs.currentText()) > 0 and len(self.lineEditTgtFileName.text()) > 0:
            if not self.btnExportSave.isEnabled(): self.btnExportSave.setEnabled(True)
        else:
            if self.btnExportSave.isEnabled(): self.btnExportSave.setEnabled(False)

    def queueDeleteSelectedRow(self):
        jobID, iRow = self.queueGetJobIDFromRow()
        self.tableQueue.removeRow(iRow)
        self.jobs.removeJob(jobID)
        if(iRow > 0):
            self.tableQueue.setCurrentCell(iRow-1, 0)
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

    # Updates the directories combo element
    def updateDirs(self, dirs):
        self.dirs = dirs
        self.config.setDirs(dirs)
        currentText = self.cmbTgtDirs.currentText()
        self.cmbTgtDirs.clear()
        for i in range(len(self.dirs)):
            self.cmbTgtDirs.insertItem(
                i, self.dirs[i][1], userData=self.dirs[i][0])
            if self.dirs[i][1] == currentText:
                self.cmbTgtDirs.setCurrentText(currentText)

    # Updates the state of a job in the queue by the job ID
    def updateQueueJobState(self, id, state):
        rowCount = self.tableQueue.rowCount()
        for iRow in range(rowCount):
            idItem = self.tableQueue.item(iRow, 0)
            if(idItem.text() == id):
                stateItem = self.tableQueue.item(iRow, 2)
                stateItem.setText(self.getJobStateString(state))
                break

    # Swap jobs
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
        self.logUi.show()

    def queueShowError(self):
        jobID = self.queueGetJobIDFromRow()[0]
        job = self.jobs.getJob(jobID)
        errorID = job.getErrorID()
        errorMsg = job.getErrorMsg()
        self.logUi.setTitle('Error %s' % errorID)
        self.logUi.setLogText(errorMsg.replace('\\n', '\n'))
        self.logUi.show()

    def toggleQueuePause(self):
        if self.btnQueuePause.isChecked():
            self.btnQueuePause.setIcon(self.iconPlay)
            self.config.setQueueIsPaused(True)
            if self.ffmpegProcess:
                os.kill(self.ffmpegProcess.pid, signal.SIGSTOP)
                job = self.getNextRenderingJob()
                self.updateQueueJobState(job.getID(), 5)
        else:
            self.btnQueuePause.setIcon(self.iconPause)
            self.config.setQueueIsPaused(False)
            if self.ffmpegProcess:
                os.kill(self.ffmpegProcess.pid, signal.SIGCONT)
                job = self.getNextPausedJob()
                self.updateQueueJobState(job.getID(), 4)
            else:
                self.runNextWaitJob()

    def moveRowInFiltersGrid(self, index, moveDown):
        rowCount = self.gridLayoutFilters.rowCount()
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
        rowCount = self.gridLayoutFilters.rowCount()
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
        rowCount = self.gridLayoutFilters.rowCount()
        for i in range(rowCount):
            item = self.gridLayoutFilters.takeAt(0)
            item.setSizeConstraint(QLayout.SetMinAndMaxSize)
            item.setSpacing(6)
            items.append(item)
        return items

    def loadFilterPositions(self, job):
        self.log(1, 'Loading filter positions ...')
        items = self.getFilterPositionItems()
        filterPositions = job.getFilterPositions()
        for position in sorted(filterPositions.keys()):
            filter = filterPositions.get(position)
            for item in items:
                name = item.objectName()
                atts = self.filterAtts.get(filter)
                if not atts:
                    # Todo: Error if filter is not defined
                    return
                layout = atts.get('layout')
                searchName = layout.objectName()
                if name == searchName:
                    self.gridLayoutFilters.addItem(item, int(position), 0)
        self.setFilterBtnStates()

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
        return False

    def resetVideoProps(self):
        self.videoProps = {}

    def log(self, id, line):
        if id == 1: self.logApp.appendPlainText(line)
        elif id == 2: self.logFfmpeg.appendPlainText(line)
        print(line)

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
# window.newFile('/home/vommie/videos/test.mp4')
window.newFile('/home/vommie/dev/personal/pycut/test.mp4')
app.exec_()
