from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QDialog
from .Functions import Functions

class RatingUI(QtWidgets.QDialog):
    def __init__(self, parent):
        self.parent = parent
        super(RatingUI, self).__init__(parent)
        uic.loadUi('%s/gui/rating.ui' % self.parent.rootDir, self)
        self.radioButton_rate0.clicked.connect(self.onBtnRateClicked)
        self.radioButton_rate1.clicked.connect(self.onBtnRateClicked)
        self.radioButton_rate2.clicked.connect(self.onBtnRateClicked)
        self.radioButton_rate3.clicked.connect(self.onBtnRateClicked)
        self.radioButton_rate4.clicked.connect(self.onBtnRateClicked)
        self.radioButton_rate5.clicked.connect(self.onBtnRateClicked)
        self._rating = 0

    def onBtnRateClicked(self):
        button = self.sender()
        if button:
            self._rating = int(button.text())
            self.accept()

    def reset_ui(self):
        self.radioButton_rate0.setChecked(True)
        self._rating = 0

    def customExec(self):
        self.exec_()
        rating = self._rating
        self.reset_ui()
        return rating
