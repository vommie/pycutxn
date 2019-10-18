#!/usr/bin/env python3
import mpv
from player_control import PlayerControl
import sys
from functions import *

from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

class Ui(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super(Ui, self).__init__()
        uic.loadUi('./gui/main.ui', self)

        self.init_player()
        self.show()

        self.btn_pause.clicked.connect(self.on_pause)
        self.btn_frame_step.clicked.connect(self.on_frame_step)
        self.btn_frame_step_back.clicked.connect(self.on_frame_step_back)

    def init_player(self):
        self.render_frame = self.findChild(QtWidgets.QFrame, 'render_frame')
        self.render_frame.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.render_frame.setAttribute(Qt.WA_NativeWindow)
        import locale
        locale.setlocale(locale.LC_NUMERIC, 'C')
        player = mpv.MPV(wid=str(int(self.render_frame.winId())), vo='x11', log_handler=print, loglevel='debug')
        #
        self.player_control = PlayerControl(player)
        # Register observers
        self.player_control.player.observe_property('pause', self.on_player_pause)
        self.player_control.player.observe_property('percent-pos', self.on_player_percent_pos)
        # self.player_control.player.observe_property('duration', self.on_player_duration)
        self.player_control.player.observe_property('time-pos', self.on_player_time_pos)

    # Player observer events

    def on_player_pause(self, action, state):
        if state:
            self.btn_pause.setText('||')
        else:
            self.btn_pause.setText('>')

    def on_player_percent_pos(self, action, pos):
        self.player_progress_bar.setValue(pos)

    def on_player_time_pos(self, action, timestamp):
        # Convert timestamp format s.ms to h:m:s.ms
        time_split = str(timestamp).split('.', 1)
        time_ms = time_split[1]
        if len(time_ms) == 1:
            time_ms = '%s0' % time_split[1]
        time_ms = '{:03d}'.format(int(time_split[1][:3]))
        time = "%s.%s" % (convert_seconds_to_hmsf(int(time_split[0])), time_ms)
        self.player_time_curr_label.setText(time)


    # GUI control events

    def on_pause(self):
        self.player_control.pause()

    def on_frame_step(self):
        self.player_control.frame_step()

    def on_frame_step_back(self):
        self.player_control.frame_back_step()


app = QtWidgets.QApplication(sys.argv)
window = Ui()
window.player_control.play('/home/vommie/videos/Musikvideos/60s/Uriah Heep - Lady In Black 1971 (1977)  (HQ) (480p_25fps_H264-128kbit_AAC).mp4')
app.exec_()
