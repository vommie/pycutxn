#!/usr/bin/env python3

import sys
import datetime
import json

from libs.mpv import *

from classes.PlayerControl import PlayerControl
from classes.DirsUi import DirsUi
from classes.Functions import Functions
from classes.Config import Config
from classes.Jobs import Jobs
from classes.FFmpegControl import FFmpegControl

from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QIcon
import res  # pyrcc5 -o res.py res/res.qrc


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
            4: 'Rendering'
        }
        self.FFmpegControl = FFmpegControl()
        self.FFmpegControl.bindToProgress(self.onFFmpegProgress)
        self.FFmpegControl.bindToStart(self.onFFmpegStart)
        self.FFmpegControl.bindToExit(self.onFFmpegExit)
        # Init member variables
        self.dirsUi = DirsUi(self)
        timeFormat = '0:00:0.0'
        self.playerTimeCurrent = timeFormat
        self.sectionTimeStart = timeFormat
        self.sectionTimeEnd = timeFormat
        self.iconPlay = QIcon(':/icons/ic_play_arrow_24px.svg')
        self.iconPause = QIcon(':/icons/ic_pause_24px.svg')
        self.iconIsMuted = QIcon(':/icons/ic_volume_off_24px.svg')
        self.iconIsNotMuted = QIcon(':/icons/ic_volume_up_24px.svg')
        self.frameStep = False

    # Event handler while ffmpeg is rendering
    def onFFmpegProgress(self, line, job, totalSeconds):
        if not isinstance(line, list):
            return
        if not len(line) == 2:
            return
        if line[0] == 'progress':
            if line[1] == 'end':
                # Reset progress bar
                pass
        elif line[0] == 'speed':
            # Set speed label
            pass
        elif line[0] == 'fps':
            # set fps label
            pass
        elif line[0] == 'out_time':
            currentSecond = int(
                Functions.timeStrToSeconds(line[1][:-3], True) * 100)
            totalSeconds = int(totalSeconds * 100)
            if currentSecond > totalSeconds:
                currentSecond = totalSeconds
            self.progressBarRender.setValue(currentSecond)

    # Event handler when ffmpeg exits rendering
    def onFFmpegExit(self, job, code, output, error):
        if self.progressBarRender.isEnabled():
            self.progressBarRender.setValue(0)
            self.progressBarRender.setEnabled(False)
        state = job.getState()
        if code == 0:
            state = 1
        else:
            job.setErrorID(code)
            job.setErrorMsg(str(error))
            state = 3
        job.setState(state)
        # todo append output and error to job, display it if clicked on queue item
        # Update queue table with job state
        id = job.getID()
        self.updateQueueJobState(id, state)
        self.runNextWaitJob()

    # Event handler when ffmpeg starts to render
    def onFFmpegStart(self, job, totalSeconds):
        job.setState(4)
        self.updateQueueJobState(job.getID(), 4)
        if not self.progressBarRender.isEnabled():
            self.progressBarRender.setEnabled(True)
        self.progressBarRender.setMaximum(int(totalSeconds * 100))
        self.progressBarRender.setValue(0)

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
        self.tableSections.currentCellChanged.connect(
            self.onTableSectionCurrCellChanged)
        self.tableSections.itemDoubleClicked.connect(
            self.onTableSectionItemDblClicked)
        self.btnSectionAdd2.clicked.connect(self.onBtnSectionAddClicked)
        self.btnSectionDelete.clicked.connect(self.onBtnSectionDeleteClicked)
        self.btnSectionUp.clicked.connect(self.onBtnSectionUpClicked)
        self.btnSectionDown.clicked.connect(self.onBtnSectionDownClicked)
        # Job Finalization
        self.lineEditTgtFileName.textChanged.connect(
            self.onLineEditTgtFileNameChanged)
        self.boxTgtFileCount.valueChanged.connect(self.onBoxFileCountChanged)
        self.btnTgtWxSuffix.clicked.connect(self.onBtnExportWxClicked)
        self.btnExportSave.clicked.connect(self.onBtnExportSave)
        self.btnExportDirs.clicked.connect(self.onBtnExportDirsClicked)
        self.cmbTgtDirs.currentTextChanged.connect(
            self.onCmbTgtDirsCurrTextChanged)
        # Queue
        self.tableQueue.currentCellChanged.connect(
            self.onTableQueueCurrCellChanged)
        self.btnQueueDelete.clicked.connect(self.onBtnQueueDeleteClicked)

    def initGui(self):
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
        # Jobs
        for id, job in self.jobs.jobs.items():
            try:
                int(id) # Skip 'default' job
                state = job.getState()
                self.queueAddRow(id, job.getTgtFileNameLong(), self.getJobStateString(state))
                if(state == 0):
                    self.runNextWaitJob()
            except:
                pass

    def initPlayer(self):
        self.renderFrame = self.findChild(QtWidgets.QWidget, 'renderFrame')
        self.renderFrame.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.renderFrame.setAttribute(Qt.WA_NativeWindow)
        import locale
        locale.setlocale(locale.LC_NUMERIC, 'C')
        player = MPV(wid=str(int(self.renderFrame.winId())), vo='x11')
        # player = MPV(wid=str(int(self.renderFrame.winId())), vo='x11', log_handler=print, loglevel='debug')
        self.playerControl = PlayerControl(player, self.config)
        # Register observers
        self.playerControl.player.observe_property('pause', self.onPlayerPause)
        self.playerControl.player.observe_property(
            'percent-pos', self.onPlayerPercentPos)
        self.playerControl.player.observe_property(
            'duration', self.onPlayerDuration)
        self.playerControl.player.observe_property(
            'time-pos', self.onPlayerTimePos)
        self.playerControl.player.observe_property(
            'volume', self.onPlayerVolume)

    def newFile(self, videoFilePath):
        self.videoFilePath = videoFilePath
        self.jobs.newCurrentJob(videoFilePath)
        self.lineEditTgtFileName.setText(
            self.jobs.getCurrentJob().getTgtFileName())
        self.sliderPlayerIsPressed = False
        self.sliderPlayer.setMinimum(0)
        self.sliderPlayer.setMaximum(99 * self.config.getPlayerSliderFactor())
        self.btnTgtWxSuffix.setChecked(False)
        window.playerControl.play(videoFilePath)
        self.playerControl.volume(self.config.getPlayerVolume())
        self.setMuteState(self.config.getPlayerIsMuted())
        self.btnPause.setIcon(self.iconPause)
        self.setPlayerControlsState(True)

    def addJob(self):
        id, job = self.jobs.saveCurrentJob()
        state = job.getState()
        self.queueAddRow(id, job.getTgtFileNameLong(), self.getJobStateString(state))
        self.runNextWaitJob()

    def runNextWaitJob(self):
        if self.FFmpegControl.busy():
            return False
        job = self.getNextWaitingJob()
        if(job):
            self.FFmpegControl.renderJob(job)

    def getNextWaitingJob(self):
        job = False
        jobItems = self.tableQueue.findItems(self.getJobStateString(0), Qt.MatchExactly)
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

    # Player observer events

    def onPlayerPause(self, action, state):
        if not self.frameStep:
            if state:
                self.btnPause.setIcon(self.iconPlay)
            else:
                self.btnPause.setIcon(self.iconPause)
        self.frameStep = False

    def onPlayerPercentPos(self, action, pos):
        if not self.sliderPlayerIsPressed:
            self.sliderPlayer.setValue(
                pos * self.config.getPlayerSliderFactor())

    def onPlayerTimePos(self, action, timestamp):
        # Convert timestamp format s.ms to h:m:s.ms
        timeSplit = str(timestamp).split('.', 1)
        timeMs = timeSplit[1]
        if len(timeMs) == 1:
            timeMs = '%s0' % timeSplit[1]
        timeMs = '{:03d}'.format(int(timeSplit[1][:3]))
        time = "%s.%s" % (Functions.convertSecondsToHMFS(
            int(timeSplit[0])), timeMs)
        self.playerTimeCurrent = time
        self.labelPlayerTimeCurr.setText(time)

    def onPlayerDuration(self, action, duration):
        self.duration = duration

    def onPlayerVolume(self, action, volume):
        self.sliderVolume.setValue(volume)

    # GUI control events

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

    def onBoxFileCountChanged(self, text):
        self.jobs.getCurrentJob().setTgtFileCount(text)

    def onBtnExportSave(self):
        self.addJob()

    def onBtnExportDirsClicked(self):
        self.dirsUi.show()

    def onCmbTgtDirsCurrTextChanged(self, text):
        path = self.cmbTgtDirs.currentData()
        self.jobs.getCurrentJob().setTgtDirName(path)
        self.config.setTgtDirName(text)

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

    def onBtnQueueDeleteClicked(self):
        self.queueDeleteSelectedRow()

    # GUI Control

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

    def queueAddRow(self, id, filename, state):
        rowIndex = self.tableQueue.rowCount()
        self.tableQueue.insertRow(rowIndex)
        self.tableQueue.setItem(rowIndex, 0, QTableWidgetItem(id))
        self.tableQueue.setItem(rowIndex, 1, QTableWidgetItem(filename))
        self.tableQueue.setItem(rowIndex, 2, QTableWidgetItem(state))

    # Set the states of the section buttons
    def setSectionBtnStates(self):
        rowCount = self.tableSections.rowCount()
        rowIndex = self.tableSections.currentRow()
        if rowCount == 0:
            self.btnSectionUp.setEnabled(False)
            self.btnSectionDown.setEnabled(False)
            self.btnSectionDelete.setEnabled(False)
        else:
            self.btnSectionDelete.setEnabled(True)
            if rowIndex == 0:
                self.btnSectionUp.setEnabled(False)
            else:
                self.btnSectionUp.setEnabled(True)
            if rowIndex < rowCount-1:
                self.btnSectionDown.setEnabled(True)
            else:
                self.btnSectionDown.setEnabled(False)

    def setQueueBtnStates(self):
        rowCount = self.tableQueue.rowCount()
        rowIndex = self.tableQueue.currentRow()
        if rowCount == 0:
            self.btnQueueUp.setEnabled(False)
            self.btnQueueDown.setEnabled(False)
            self.btnQueueDelete.setEnabled(False)
            self.btnQueueLoad.setEnabled(False)
        else:
            self.btnQueueDelete.setEnabled(True)
            self.btnQueueLoad.setEnabled(True)
            if rowIndex == 0:
                self.btnQueueUp.setEnabled(False)
            else:
                self.btnQueueUp.setEnabled(True)
            if rowIndex < rowCount-1:
                self.btnQueueDown.setEnabled(True)
            else:
                self.btnQueueDown.setEnabled(False)

    def queueDeleteSelectedRow(self):
        iRow = self.tableQueue.currentRow()
        itemID = self.tableQueue.item(iRow, 0)
        jobID = itemID.text()
        self.tableQueue.removeRow(iRow)
        self.jobs.removeJob(jobID)
        if(iRow > 0):
            self.tableQueue.setCurrentCell(iRow-1, 0)
        self.setQueueBtnStates()

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

app = QtWidgets.QApplication(sys.argv)
window = MainUi()
# window.newFile('/home/vommie/videos/test.mp4')
window.newFile('/home/vommie/videos/test.mp4')
app.exec_()
