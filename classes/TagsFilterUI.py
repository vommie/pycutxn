from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import *
from .Functions import Functions

class TagsFilterUI(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(TagsFilterUI, self).__init__(parent)
        uic.loadUi('./gui/tags_filter.ui', self)
        self.parent = parent
        self.initGuiEvents()
        self.initGui()

    def initGuiEvents(self):
        self.buttonBox.accepted.connect(self.onAccepted)
        self.tableTagsFilter.currentCellChanged.connect(self.onTableTagsFilterCurrCellChanged)
        self.btnAdd.clicked.connect(self.onBtnAddClicked)
        self.btnDelete.clicked.connect(self.onBtnDeleteClicked)

    def initGui(self):
        # Set GUI from config
        tagIDs = self.parent.config.getTaggerFilterTagIDs()
        for tagID in tagIDs:
            tagID = self.validateTagID(tagID)
            if tagID: self.tableTagsFilterAddRow(tagID)

    def onAccepted(self):
        tagIDs = self.getTagIDs()
        self.parent.config.setTaggerFilterTagIDs(tagIDs)
        self.parent.updateTagsFilter(tagIDs)

    def validateTagID(self, tagID):
        '''
        Checks if a tagID is a number and returns the number as string or False as bool if tagID is invalid.
        '''
        if isinstance(tagID, int): return str(tagID)
        if isinstance(tagID, str) and tagID.isnumeric(): return tagID
        return False

    def onBtnAddClicked(self):
        self.tableTagsFilterAddRow('')

    def onBtnDeleteClicked(self):
        self.deleteSelectedRow()

    def tableTagsFilterAddRow(self, tagID):
        rowIndex = self.tableTagsFilter.rowCount()
        self.tableTagsFilter.insertRow(rowIndex)
        item = QTableWidgetItem(tagID)
        self.tableTagsFilter.setItem(rowIndex, 0, item)
        # Set focus to new inserted empty cell
        tagID = self.validateTagID(tagID)
        if not tagID: self.tableTagsFilter.editItem(item)

    def onTableTagsFilterCurrCellChanged(self):
        self.setBtnStates()

    def deleteSelectedRow(self):
        rowIndex = self.tableTagsFilter.currentRow()
        self.tableTagsFilter.removeRow(rowIndex)
        if(rowIndex > 0):
            item = self.tableTagsFilter.item(rowIndex-1, 0)
            if item: item.setSelected(True)
        self.setBtnStates()

    def setBtnStates(self):
        rowCount = self.tableTagsFilter.rowCount()
        if rowCount == 0:
            self.btnDelete.setEnabled(False)
        else:
            self.btnDelete.setEnabled(True)

    def getTagIDs(self):
        '''
        Gets the tagIDs from the table as list with tagIDs as int

        :return: Array with tagIDs as value or empty array
        '''
        tagIDs = []
        rowCount = self.tableTagsFilter.rowCount()
        for iRow in range(rowCount):
            tagID = self.tableTagsFilter.item(iRow, 0).text()
            tagID = self.validateTagID(tagID)
            if tagID and int(tagID) not in tagIDs: tagIDs.append(int(tagID))
        return tagIDs
