from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QDialog
from .Functions import Functions
import os
import subprocess

class KnownUI(QtWidgets.QDialog):
    def __init__(self, parent):
        self.parent = parent
        super(KnownUI, self).__init__(parent)
        uic.loadUi('%s/gui/known.ui' % self.parent.rootDir, self)
        self.listWidgetFiles.itemDoubleClicked.connect(self.onListWidgeFilesItemDoubleClicked)
        self.buttonBox.accepted.connect(self.onAccepted)

    def addRow(self, file):
        self.listWidgetFiles.addItem(file)

    def setFilesList(self, filesList):
        for file in filesList:
            self.addRow(file)

    def setLabel(self, label):
        self.labelInfo.setText(label)

    def setIcon(self, icon):
        self.labelIcon.setText(icon)

    def setTitle(self, title):
        self.setWindowTitle(title)

    def onListWidgeFilesItemDoubleClicked(self, item):
        file = item.text()
        if os.path.isfile(file):
            opener = Functions.getCurrentSysOpener()
            subprocess.call([opener, file])

    def onAccepted(self):
        self.listWidgetFiles.clear()

    def closeEvent(self, event):
        self.listWidgetFiles.clear()
