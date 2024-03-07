from PyQt5 import uic
from PyQt5.QtWidgets import QDialog
from .Functions import Functions
import os
import subprocess

class KnownUI(QDialog):
    def __init__(self, parent):
        self.parent = parent
        super(KnownUI, self).__init__(parent)
        uic.loadUi('%s/gui/known.ui' % self.parent.rootDir, self)
        self.listWidgetFilesFound.itemDoubleClicked.connect(self.onListWidgeFilesFoundItemDoubleClicked)
        self.listWidgetFilesKnown.itemDoubleClicked.connect(self.onListWidgeFilesKnownItemDoubleClicked)
        self.buttonBox.accepted.connect(self.onAccepted)
        self.reset()

    def addRowToFound(self, file):
        self.listWidgetFilesFound.addItem(file)

    def addRowToKnown(self, file):
        self.listWidgetFilesKnown.addItem(file)

    def setFilesListToFound(self, filesList):
        self.listWidgetFilesFound.setVisible(True)
        self.labelFound.setVisible(True)
        for file in filesList:
            self.addRowToFound(file)

    def setFilesListToKnown(self, filesList):
        self.listWidgetFilesKnown.setVisible(True)
        self.labelTarget.setVisible(True)
        self.setIcon(text='', color='#00FF00')
        for file in filesList:
            self.addRowToKnown(file)

    def setLabel(self, label):
        self.labelInfo.setText(label)

    def setIcon(self, text, color=False):
        self.labelIcon.setText(text)
        if color:
            self.labelIcon.setStyleSheet(f"color: {color};")
        else:
            self.labelIcon.setStyleSheet("")

    def setTitle(self, title):
        self.setWindowTitle(title)

    def onListWidgeFilesFoundItemDoubleClicked(self, item):
        file = item.text()
        if os.path.isfile(file):
            opener = Functions.getCurrentSysOpener()
            subprocess.call([opener, file])

    def onListWidgeFilesKnownItemDoubleClicked(self, item):
        file = item.text()
        if os.path.isfile(file):
            opener = Functions.getCurrentSysOpener()
            subprocess.call([opener, file])

    def reset(self):
        self.listWidgetFilesFound.clear()
        self.listWidgetFilesKnown.clear()
        self.listWidgetFilesFound.setVisible(False)
        self.listWidgetFilesKnown.setVisible(False)
        self.labelFound.setVisible(False)
        self.labelTarget.setVisible(False)
        self.setLabel('')
        self.setTitle('')
        self.setIcon('')

    def onAccepted(self):
        self.reset()

    def closeEvent(self, event):
        self.reset()
