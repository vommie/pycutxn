from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QStyleOptionSlider, QStyle

class JumpSlider(QtWidgets.QSlider):
    '''
    Slider which jumps to position if the it gets clicked somewhere else than the handle
    See: https://stackoverflow.com/questions/52689047/moving-qslider-to-mouse-click-position
    '''

    def mousePressEvent(self, event):
        super(JumpSlider, self).mousePressEvent(event)
        if event.button() == QtCore.Qt.LeftButton:
            self.pressed = True
            val = self.pixelPosToRangeValue(event.pos())
            self.setValue(val)
            self.sliderMoved.emit(val)
            self.sliderReleased.emit()
            self.pressed = False

    def pixelPosToRangeValue(self, pos):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        gr = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, self)
        sr = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
        if self.orientation() == QtCore.Qt.Horizontal:
            sliderLength = sr.width()
            sliderMin = gr.x()
            sliderMax = gr.right() - sliderLength + 1
        else:
            sliderLength = sr.height()
            sliderMin = gr.y()
            sliderMax = gr.bottom() - sliderLength + 1
        pr = pos - sr.center() + sr.topLeft()
        p = pr.x() if self.orientation() == QtCore.Qt.Horizontal else pr.y()
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), p - sliderMin, sliderMax - sliderMin, opt.upsideDown)
