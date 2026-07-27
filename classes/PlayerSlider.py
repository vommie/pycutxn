from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import QStyleOptionSlider, QStyle

class PlayerSlider(QtWidgets.QSlider):
    '''
    Slider which jumps to position if it gets clicked somewhere else than the handle
    See: https://stackoverflow.com/questions/52689047/moving-qslider-to-mouse-click-position
    '''

    def mousePressEvent(self, event):
        self.pressed = True
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            val = self.pixelPosToRangeValue(event.pos())
            self.setValue(val)

    def mouseReleaseEvent(self, event):
        self.pressed = False

    def mouseMoveEvent(self, event):
        self.pressed = True
        if event.buttons() == QtCore.Qt.MouseButton.LeftButton:
            val = self.pixelPosToRangeValue(event.pos())
            self.setValue(val)

    def wheelEvent(self, event):
        return

    def dragMoveEvent(self, event):
        return

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key.Key_Home, QtCore.Qt.Key.Key_End, QtCore.Qt.Key.Key_PageUp, QtCore.Qt.Key.Key_PageDown):
            event.ignore()
            return
        super().keyPressEvent(event)

    def pixelPosToRangeValue(self, pos):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        gr = self.style().subControlRect(QtWidgets.QStyle.ComplexControl.CC_Slider, opt, QtWidgets.QStyle.SubControl.SC_SliderGroove, self)
        sr = self.style().subControlRect(QtWidgets.QStyle.ComplexControl.CC_Slider, opt, QtWidgets.QStyle.SubControl.SC_SliderHandle, self)
        if self.orientation() == QtCore.Qt.Orientation.Horizontal:
            sliderLength = sr.width()
            sliderMin = gr.x()
            sliderMax = gr.right() - sliderLength + 1
        else:
            sliderLength = sr.height()
            sliderMin = gr.y()
            sliderMax = gr.bottom() - sliderLength + 1
        pr = pos - sr.center() + sr.topLeft()
        p = pr.x() if self.orientation() == QtCore.Qt.Orientation.Horizontal else pr.y()
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), p - sliderMin, sliderMax - sliderMin, opt.upsideDown)
