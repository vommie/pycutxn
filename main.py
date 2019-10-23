#!/usr/bin/env python3
import mpv
from PlayerControl import PlayerControl
import sys
from functions import *
import datetime

from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

class Ui(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(Ui, self).__init__()
        uic.loadUi('./gui/main.ui', self)

        self.initMembers()
        self.initGuiEvents()
        self.initPlayer()

        self.show()

    def initMembers(self):
        # Config
        self.playerSliderFactor = 100

        # Init member variables
        timeFormat = '0:00:0.0'
        self.playerTimeCurrent = timeFormat
        self.sectionTimeStart = timeFormat
        self.sectionTimeEnd = timeFormat

    def initGuiEvents(self):
        # Player control
        self.btnPause.clicked.connect(self.onBtnPauseClicked)
        self.btnFrameStep.clicked.connect(self.onBtnFrameStepClicked)
        self.btnFrameStepBack.clicked.connect(self.onBtnFrameStepBackClicked)
        self.btnSectionStart.clicked.connect(self.onBtnSectionStartClicked)
        self.btnSectionEnd.clicked.connect(self.onBtnSectionEndClicked)
        self.btnSectionAdd1.clicked.connect(self.onBtnSectionAddClicked)
        # Player Progress
        self.sliderPlayer.sliderMoved.connect(self.onSliderPlayerMoved)
        self.sliderPlayer.sliderPressed.connect(self.onSliderPlayerPressed)
        self.sliderPlayer.sliderReleased.connect(self.onSliderPlayerReleased)
        # Sections
        self.tableSections.cellClicked.connect(self.onTableSectionRowClicked)
        self.tableSections.currentCellChanged.connect(self.onTableSectionCurrCellChanged)
        self.tableSections.itemDoubleClicked.connect(self.onTableSectionItemDblClicked)
        self.btnSectionAdd2.clicked.connect(self.onBtnSectionAddClicked)
        self.btnSectionDelete.clicked.connect(self.onBtnSectionDeleteClicked)
        self.btnSectionUp.clicked.connect(self.onBtnSectionUpClicked)
        self.btnSectionDown.clicked.connect(self.onBtnSectionDownClicked)

    def initGui(self):
        # GUI elements options
        header = self.tableSections.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)

    def initPlayer(self):
        #self.renderFrame = self.findChild(QtWidgets.QFrame, 'renderFrame')
        self.renderFrame = self.findChild(QtWidgets.QWidget, 'renderFrame')
        self.renderFrame.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.renderFrame.setAttribute(Qt.WA_NativeWindow)
        import locale
        locale.setlocale(locale.LC_NUMERIC, 'C')
        player = mpv.MPV(wid=str(int(self.renderFrame.winId())), vo='x11', log_handler=print, loglevel='debug')
        self.playerControl = PlayerControl(player)
        # Register observers
        self.playerControl.player.observe_property('pause', self.onPlayerPause)
        self.playerControl.player.observe_property('percent-pos', self.onPlayerPercentPos)
        self.playerControl.player.observe_property('duration', self.onPlayerDuration)
        self.playerControl.player.observe_property('time-pos', self.onPlayerTimePos)

    def newFile(self, videoFilePath):
        self.videoFilePath = videoFilePath
        self.setExportVideoFilePath(videoFilePath)
        window.playerControl.play(videoFilePath)
        self.sliderPlayerIsPressed = False
        self.sliderPlayer.setMinimum(0)
        self.sliderPlayer.setMaximum(99 * self.playerSliderFactor)

    def setExportVideoFilePath(self, videoFilePath):
        self.lineEditExportFilePath.setText(self.videoFilePath)

    # Convert time string (0:00:0.0) to datetime object
    def timeStringToTime(self, timeStr):
        date_time_obj = datetime.datetime.strptime(timeStr, '%H:%M:%S.%f')
        return date_time_obj

    # Player observer events

    def onPlayerPause(self, action, state):
        if state:
            self.btnPause.setText('||')
        else:
            self.btnPause.setText('>')

    def onPlayerPercentPos(self, action, pos):
        if not self.sliderPlayerIsPressed:
            self.sliderPlayer.setValue(pos * self.playerSliderFactor)

    def onPlayerTimePos(self, action, timestamp):
        # Convert timestamp format s.ms to h:m:s.ms
        timeSplit = str(timestamp).split('.', 1)
        timeMs = timeSplit[1]
        if len(timeMs) == 1:
            timeMs = '%s0' % timeSplit[1]
        timeMs = '{:03d}'.format(int(timeSplit[1][:3]))
        time = "%s.%s" % (convertSecondsToHMFS(int(timeSplit[0])), timeMs)
        self.playerTimeCurrent = time
        self.labelPlayerTimeCurr.setText(time)

    def onPlayerDuration(self, action, duration):
        self.duration = duration

    # GUI control events

    def onBtnPauseClicked(self):
        self.playerControl.pause()

    def onBtnFrameStepClicked(self):
        self.playerControl.frameStep()

    def onBtnFrameStepBackClicked(self):
        self.playerControl.frameBackStep()

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

    def onBtnSectionDeleteClicked(self):
        self.sectionDeleteSelectedRow()

    def onBtnSectionUpClicked(self):
        self.moveSectionItem(-1)

    def onBtnSectionDownClicked(self):
        self.moveSectionItem(1)

    def onTableSectionRowClicked(self):
        pass

    def onTableSectionCurrCellChanged(self):
        self.setSectionBtnStates()

    def onTableSectionItemDblClicked(self, item):
        timeStr = item.text()
        # Set section time range
        col = item.column()
        row = item.row()
        if col == 0:
            self.sectionTimeStart = timeStr
            timeEndStr = self.tableSections.item(row, 1)
            self.sectionTimeEnd = timeEndStr
        elif col == 1:
            self.sectionTimeEnd = timeStr
            timeStartStr = self.tableSections.item(row, 0)
            self.sectionTimeStart = timeStartStr
        # Jump to time position in video
        self.playerControl.seek(timeStr, 'absolute+exact')

    def onSliderPlayerMoved(self, value):
        self.sliderPlayerIsPressed = True
        self.setPlayerPosByPlayerSlider()

    def onSliderPlayerPressed(self):
        self.sliderPlayerIsPressed = True

    def onSliderPlayerReleased(self):
        self.sliderPlayerIsPressed = False
        self.setPlayerPosByPlayerSlider()

    # GUI Control

    def setPlayerPosByPlayerSlider(self):
        value = self.sliderPlayer.value()
        percentage = value / self.playerSliderFactor
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
        self.setSectionBtnStates()

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

    # Move an item up (+1) or down (-1)
    def moveSectionItem(self, directionValue):
        rowCount = self.tableSections.rowCount()
        rowIndex = self.tableSections.currentRow()
        if rowIndex + directionValue >= 0 and  rowIndex + directionValue <= rowCount - 1:
            currItem1 = self.tableSections.takeItem(rowIndex, 0)
            currItem2 = self.tableSections.takeItem(rowIndex, 1)
            prevItem1 = self.tableSections.takeItem(rowIndex + directionValue, 0)
            prevItem2 = self.tableSections.takeItem(rowIndex + directionValue, 1)
            self.tableSections.setItem(rowIndex, 0, prevItem1)
            self.tableSections.setItem(rowIndex, 1, prevItem2)
            self.tableSections.setItem(rowIndex + directionValue, 0, currItem1)
            self.tableSections.setItem(rowIndex + directionValue, 1, currItem2)
            self.tableSections.setCurrentItem(currItem1)


app = QtWidgets.QApplication(sys.argv)
window = Ui()
window.newFile('/home/vommie/videos/Musikvideos/60s/Uriah Heep - Lady In Black 1971 (1977)  (HQ) (480p_25fps_H264-128kbit_AAC).mp4')
app.exec_()
