import sys
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5.QtWidgets import QMessageBox

class TimerMessageBox(QMessageBox):
    def __init__(self, timeout=3, title="", text="", parent=None):
        self.text = text
        super(TimerMessageBox, self).__init__(parent)
        self.setIcon(QMessageBox.Warning)
        self.setStandardButtons(QMessageBox.Ok | QMessageBox.Abort)
        self.setWindowTitle(title)
        self.time_to_wait = timeout
        self.setText(self.text + "\n\n{0} seconds remaining ...".format(timeout))
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.changeContent)
        self.timer.start()

    def changeContent(self):
        self.time_to_wait -= 1
        self.setText(self.text + "\n\n{0} seconds remaining ...".format(self.time_to_wait))
        if self.time_to_wait <= 0:
            self.close()

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()
