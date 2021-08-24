from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import *
from .Functions import Functions

class DirsUI(QtWidgets.QDialog):
    def __init__(self, parent):
        self.parent = parent
        super(DirsUI, self).__init__(parent)
        uic.loadUi('%s/gui/dirs.ui' % self.parent.rootDir, self)
        self.initGuiEvents()
        self.initGui()
        self.dirs = []

    def initGuiEvents(self):
        self.buttonBox.accepted.connect(self.onAccepted)
        self.tableDirs.currentCellChanged.connect(self.onTableDirsCurrCellChanged)
        self.btnAdd.clicked.connect(self.onBtnAddClicked)
        self.btnUp.clicked.connect(self.onBtnUpClicked)
        self.btnDown.clicked.connect(self.onBtnDownClicked)
        self.btnDelete.clicked.connect(self.onBtnDeleteClicked)

    def initGui(self):
        # GUI elements options
        header = self.tableDirs.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        # Set GUI from config
        dirs = self.parent.config.getTargetDirs()
        for dirSet in dirs:
            self.tableDirsAddRow(Functions.removeTrailingSlash(dirSet[0]), dirSet[1])

    def onAccepted(self):
        self.getTargetDirs()
        self.parent.updateDirs(self.dirs)

    def onBtnAddClicked(self):
        self.tableDirsAddRow('', '')

    def onBtnUpClicked(self):
        Functions.moveTableRow(self.tableDirs, -1)

    def onBtnDownClicked(self):
        Functions.moveTableRow(self.tableDirs, 1)

    def onBtnDeleteClicked(self):
        self.deleteSelectedRow()

    def tableDirsAddRow(self, path, name):
        rowIndex = self.tableDirs.rowCount()
        self.tableDirs.insertRow(rowIndex)
        self.tableDirs.setItem(rowIndex, 0, QTableWidgetItem(path))
        self.tableDirs.setItem(rowIndex, 1, QTableWidgetItem(name))
        self.tableDirs.setCurrentCell(rowIndex, 1)

    def onTableDirsCurrCellChanged(self):
        self.setBtnStates()

    def deleteSelectedRow(self):
        rowIndex = self.tableDirs.currentRow()
        self.tableDirs.removeRow(rowIndex)
        if(rowIndex > 0):
            self.tableDirs.setCurrentCell(rowIndex-1, 0)
        self.setBtnStates()

    def setBtnStates(self):
        rowCount = self.tableDirs.rowCount()
        rowIndex = self.tableDirs.currentRow()
        if rowCount == 0:
            self.btnUp.setEnabled(False)
            self.btnDown.setEnabled(False)
            self.btnDelete.setEnabled(False)
        else:
            self.btnDelete.setEnabled(True)
            if rowIndex == 0:
                self.btnUp.setEnabled(False)
            else:
                self.btnUp.setEnabled(True)
            if rowIndex < rowCount-1:
                self.btnDown.setEnabled(True)
            else:
                self.btnDown.setEnabled(False)

    def getTargetDirs(self):
        dirs = []
        rowCount = self.tableDirs.rowCount()
        for iRow in range(rowCount):
            itemPath = self.tableDirs.item(iRow, 0)
            path = Functions.removeTrailingSlash(itemPath.text())
            self.tableDirs.setItem(iRow, 0, QTableWidgetItem(path))
            itemName = self.tableDirs.item(iRow, 1)
            name = itemName.text()
            if path != '' and name != '':
                dirs.append([path, name])
        self.dirs = dirs
