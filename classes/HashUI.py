from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import *

class HashUI(QtWidgets.QDialog):
    def __init__(self, parent):
        self.parent = parent
        super(HashUI, self).__init__(parent)
        uic.loadUi('%s/gui/hash.ui' % self.parent.rootDir, self)
