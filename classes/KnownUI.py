from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import *
from .Functions import Functions
import os
import subprocess

class KnownUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(KnownUI, self).__init__(parent)
        uic.loadUi('./gui/known.ui', self)
        self.parent = parent
        self.listWidgetFiles.itemDoubleClicked.connect(self.onListWidgeFilesItemDoubleClicked)

    def addRow(self, file):
        self.listWidgetFiles.addItem(file)

    def setFilesList(self, filesList):
        for file in filesList:
            self.addRow(file)

    def onListWidgeFilesItemDoubleClicked(self, item):
        file = item.text()
        if os.path.isfile(file):
            opener = Functions.getCurrentSysOpener()
            subprocess.call([opener, file])
