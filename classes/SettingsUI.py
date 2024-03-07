from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QFileDialog
from os.path import isdir, expanduser, isfile

class SettingsUI(QtWidgets.QDialog):
    def __init__(self, parent):
        self.parent = parent
        super(SettingsUI, self).__init__(parent)
        uic.loadUi('%s/gui/settings.ui' % self.parent.rootDir, self)
        self.tabWidgetSettings.setCurrentIndex(0)
        self.loadConfig()
        self.initGuiEvents()

    def loadConfig(self):
        # General
        self.checkSetAutoSection.setChecked(self.parent.config.getSectionsAutoCreate())
        self.checkBoxPauseQOnStart.setChecked(self.parent.config.getAppPauseQueueOnStartWhenWaitingJobs())
        # Player
        self.checkBoxPlayerAutoPlay.setChecked(self.parent.config.getPlayerAutoPlay())
        self.checkBoxMuteVideoEnd.setChecked(self.parent.config.getPlayerMuteVideoEnd())
        # Database
        self.lineEditDBPath.setText(self.parent.config.getTaggerDBPath())
        # Render
        self.comboBoxVideoCodec.setCurrentText(self.parent.config.getRenderVideoCodec())
        self.spinBoxCRF.setValue(self.parent.config.getRenderCRF())
        self.comboBoxContainer.setCurrentText(self.parent.config.getRenderContainer())
        self.comboBoxPreset.setCurrentText(self.parent.config.getRenderPreset())
        self.comboBoxAudioCodec.setCurrentText(self.parent.config.getRenderAudioCodec())
        self.spinBoxAudioBitrate.setValue(self.parent.config.getRenderAudioBitrate())
        # Warnings
        self.checkBoxWarnTgtTgt.setChecked(self.parent.config.getAppWarnTgtFileExistsInTgtDir())
        self.checkBoxWarnBaseFileExists.setChecked(self.parent.config.getAppWarnBaseFileExistsInTgtDir())
        self.checkBoxWarnJobQueue.setChecked(self.parent.config.getAppWarnFileExistsInJobs())
        self.checkBoxWarnHash.setChecked(self.parent.config.getAppWarnFileHashExistsInDB())
        self.checkBoxWarnCloseWhileRender.setChecked(self.parent.config.getAppWarnCloseWhileRender())

    def initGuiEvents(self):
        self.buttonBox.accepted.connect(self.onAccepted)
        self.pushButtonDBPath.clicked.connect(self.onBtnDBPath)

    def onAccepted(self):
        # General
        self.parent.config.setSectionsAutoCreate(self.checkSetAutoSection.isChecked())
        self.parent.config.setAppPauseQueueOnStartWhenWaitingJobs(self.checkBoxPauseQOnStart.isChecked())
        # Player
        self.parent.config.setPlayerAutoPlay(self.checkBoxPlayerAutoPlay.isChecked())
        self.parent.config.setPlayerMuteVideoEnd(self.checkBoxMuteVideoEnd.isChecked())
        # Database
        self.parent.config.setTaggerDBPath(self.lineEditDBPath.text()) # TODO: Reload Tagger when path changes
        # Render
        self.parent.config.setRenderVideoCodec(str(self.comboBoxVideoCodec.currentText()))
        self.parent.config.setRenderCRF(int(self.spinBoxCRF.value()))
        self.parent.config.setRenderContainer(str(self.comboBoxContainer.currentText()))
        self.parent.config.setRenderPreset(str(self.comboBoxPreset.currentText()))
        self.parent.config.setRenderAudioCodec(str(self.comboBoxAudioCodec.currentText()))
        self.parent.config.setRenderAudioBitrate(int(self.spinBoxAudioBitrate.value()))
        # Warnings
        self.parent.config.setAppWarnTgtFileExistsInTgtDir(self.checkBoxWarnTgtTgt.isChecked())
        self.parent.config.setAppWarnBaseFileExistsInTgtDir(self.checkBoxWarnBaseFileExists.isChecked())
        self.parent.config.setAppWarnFileExistsInJobs(self.checkBoxWarnJobQueue.isChecked())
        self.parent.config.setAppWarnFileHashExistsInDB(self.checkBoxWarnHash.isChecked())
        self.parent.config.setAppWarnCloseWhileRender(self.checkBoxWarnCloseWhileRender.isChecked())

    def onBtnDBPath(self):
        path = expanduser('~')
        xnViewDir = '%s/.config/xnviewmp' % path
        if isdir(xnViewDir): path = xnViewDir
        fileName = QFileDialog.getOpenFileName(self,'Select XnView Database', path, 'XnView Database (*.db)')
        if fileName[0] and fileName[0] != '' and isfile(fileName[0]):
            self.lineEditDBPath.setText(fileName[0])
