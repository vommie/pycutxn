from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import *
from .Functions import Functions

class LogUi(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(LogUi, self).__init__(parent)
        uic.loadUi('./gui/log.ui', self)
        self.parent = parent
        self.initGuiEvents()
        self.initGui()

    def initGuiEvents(self):
        self.buttonBox.accepted.connect(self.onAccepted)

    def initGui(self):
        geometry = self.parent.config.getDialogLogGeometry()
        if geometry: self.restoreGeometry(geometry)

    def onAccepted(self):
        self.reset()

    def setTitle(self, title):
        self.setWindowTitle(title)

    def setLogText(self, text):
        self.textEdit.setText(str(text))

    def reset(self):
        self.parent.config.setDialogLogGeometry(self.saveGeometry())
        self.setTitle('Log')
        self.setLogText('')
