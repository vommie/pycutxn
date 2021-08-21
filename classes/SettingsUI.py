from PyQt5 import QtWidgets, uic

class SettingsUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(SettingsUI, self).__init__(parent)
        uic.loadUi('./gui/settings.ui', self)
        self.parent = parent
        self.loadConfig()
        self.initGuiEvents()

    def loadConfig(self):
        # Player
        self.checkBoxPlayerAutoPlay.setChecked(self.parent.config.getPlayerAutoPlay())
        # Render
        self.comboBoxVideoCodec.setCurrentText(self.parent.config.getRenderVideoCodec())
        self.spinBoxCRF.setValue(self.parent.config.getRenderCRF())
        self.comboBoxContainer.setCurrentText(self.parent.config.getRenderContainer())
        self.comboBoxAudioCodec.setCurrentText(self.parent.config.getRenderAudioCodec())
        self.spinBoxAudioBitrate.setValue(self.parent.config.getRenderAudioBitrate())

    def initGuiEvents(self):
        self.buttonBox.accepted.connect(self.onAccepted)

    def onAccepted(self):
        # Player
        self.parent.config.setPlayerAutoPlay(self.checkBoxPlayerAutoPlay.isChecked())
        # Render
        self.parent.config.setRenderVideoCodec(str(self.comboBoxVideoCodec.currentText()))
        self.parent.config.setRenderCRF(int(self.spinBoxCRF.value()))
        self.parent.config.setRenderContainer(str(self.comboBoxContainer.currentText()))
        self.parent.config.setRenderAudioCodec(str(self.comboBoxAudioCodec.currentText()))
        self.parent.config.setRenderAudioBitrate(int(self.spinBoxAudioBitrate.value()))
