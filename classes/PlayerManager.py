import sys
import os
import locale
import traceback
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtCore import Qt, QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QPalette

from libs.mpv import MPV
from classes.PlayerControl import PlayerControl
from classes.Functions import Functions

class MPVSignalBridge(QObject):
    time_pos_changed = pyqtSignal(float)
    pause_changed = pyqtSignal(bool)
    volume_changed = pyqtSignal(float)

class PlayerManager(QtCore.QObject):
    """
    Manages the MPV player initialization, event bridge, seeking logic, frame-stepping,
    volume/mute states, and synchronization with UI player controls.
    Inherits from QObject to allow thread-safe Qt Signal/Slot routing.
    """

    def __init__(self, parent_widget, config, logger, show_msg_box_fn,
                 render_frame, btn_pause, btn_mute, slider_volume,
                 slider_player, label_time_curr, label_time_total,
                 frame_player_btns, frame_player_progress):
        super().__init__()

        self.parent = parent_widget
        self.config = config
        self.log = logger
        self.showMsgBox = show_msg_box_fn

        self.renderFrame = render_frame
        self.btnPause = btn_pause
        self.btnMute = btn_mute
        self.sliderVolume = slider_volume
        self.sliderPlayer = slider_player
        self.labelPlayerTimeCurr = label_time_curr
        self.labelPlayerTimeTotal = label_time_total
        self.framePlayerBtns = frame_player_btns
        self.framePlayerProgress = frame_player_progress

        self.bridge = MPVSignalBridge()
        self.playerControl = None

        self.timeFormat = '0:00:00.000'
        self.playerTimeCurrent = self.timeFormat
        self.playerTimeCurrentMs = 0
        self.playerTimeTotalS = 0
        self.frameStep = False
        self.endMuteActive = False

        self._connect_bridge()

    def _connect_bridge(self):
        self.bridge.pause_changed.connect(self.on_player_pause_main_thread)
        self.bridge.time_pos_changed.connect(self.on_player_time_pos_main_thread)
        self.bridge.volume_changed.connect(self.on_player_volume_main_thread)

    def _configure_render_widget(self):
        if not self.renderFrame:
            return
        self.renderFrame.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors)
        self.renderFrame.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.renderFrame.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.renderFrame.setAutoFillBackground(True)

        palette = self.renderFrame.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#000000"))
        self.renderFrame.setPalette(palette)
        self.renderFrame.setStyleSheet("background-color: #000000;")

    def get_valid_background_color(self) -> str:
        bg_color = self.config.getPlayerBgColor()
        if not bg_color or not bg_color.startswith('#'):
            return '#000000'
        return bg_color

    def _build_mpv_options(self, win_id: str, qpa_platform: str) -> dict:
        bg_color = self.get_valid_background_color()

        options = {
            'wid': win_id,
            'loglevel': 'fatal',
            'keep_open': 'always',
            'idle': 'yes',
            'force_window': 'immediate',
            'input_cursor': True,
            'input_default_bindings': False,
            'hwdec': 'auto-copy',
            'background': 'color',
            'background_color': bg_color,
        }

        if 'xcb' in qpa_platform:
            options.update({
                'vo': 'gpu,gpu-next',
                'gpu_context': 'x11egl,x11',
            })
        elif 'wayland' in qpa_platform:
            options.update({
                'vo': 'gpu,gpu-next',
                'gpu_context': 'waylandegl,waylandvk',
            })
        else:
            options.update({
                'vo': 'gpu,gpu-next,xv,x11',
            })

        return options

    def _setup_property_observers(self):
        if not self.playerControl or not self.playerControl.player:
            return

        self.playerControl.player.observe_property(
            'pause',
            lambda name, val: self.bridge.pause_changed.emit(val) if val is not None else None
        )
        self.playerControl.player.observe_property(
            'time-pos',
            lambda name, val: self.bridge.time_pos_changed.emit(val) if val is not None else None
        )
        self.playerControl.player.observe_property(
            'volume',
            lambda name, val: self.bridge.volume_changed.emit(val) if val is not None else None
        )

    def set_background_color(self, bg_color: str = None):
        color = bg_color or self.get_valid_background_color()
        if self.renderFrame:
            self.renderFrame.setStyleSheet(f"background-color: {color};")

        if self.playerControl and self.playerControl.player:
            try:
                self.playerControl.player['background'] = 'color'
                self.playerControl.player['background-color'] = color
            except Exception:
                pass

    def init_player(self):
        try:
            self._configure_render_widget()
            locale.setlocale(locale.LC_NUMERIC, 'C')

            qpa_platform = QtWidgets.QApplication.platformName().lower()
            self.log(1, f"MPV Init - Aktive Qt QPA Plattform: '{qpa_platform}'")

            win_id = str(int(self.renderFrame.winId()))
            mpv_options = self._build_mpv_options(win_id, qpa_platform)

            player = MPV(**mpv_options)
            self.playerControl = PlayerControl(player, self.config)
            self.playerControl.volume(self.config.getPlayerVolume())
            self.set_mute_state(self.config.getPlayerIsMuted())

            self._setup_property_observers()
            self.set_background_color()

        except Exception as e:
            msg = 'Error: Cannot initialize the video player.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            if self.showMsgBox:
                self.showMsgBox(msg, detailText=traceback.format_exc(), icon='critical')
            sys.exit(1)

    def stop(self):
        if self.playerControl:
            self.playerControl.stop()

    def reset_canvas(self):
        self.stop()
        self.set_background_color()

    def load_video_file(self, video_file_path: str, start_time: str, video_props: dict):
        self.playerTimeCurrent = self.timeFormat
        self.set_slider_pos_from_timestamp(0, video_props)
        self.set_label_time_curr(self.timeFormat)
        duration_hms = video_props.get('durationHMS', self.timeFormat)
        self.set_label_time_total(duration_hms)
        self.playerTimeTotalS = Functions.HMSToTimestamp(duration_hms)

        if video_props and self.playerControl:
            audioFilter = 'lavfi=[loudnorm=I=-22:TP=-1.5:LRA=2]'
            self.playerControl.player.loadfile(video_file_path, 'replace', start=start_time, af=audioFilter)
            self.set_background_color()

            if not self.config.getPlayerAutoPlay():
                self.playerControl.pause(True)
            else:
                self.playerControl.pause(False)

            self.set_controls_state(True)

    @pyqtSlot(bool)
    def on_player_pause_main_thread(self, state: bool):
        self.on_player_pause('pause', state)

    @pyqtSlot(float)
    def on_player_time_pos_main_thread(self, timestamp: float):
        self.on_player_time_pos('time-pos', timestamp)

    @pyqtSlot(float)
    def on_player_volume_main_thread(self, volume: float):
        self.on_player_volume('volume', volume)

    def on_player_pause(self, action: str, state: bool):
        if not self.frameStep:
            if state:
                self.btnPause.setText('契')
            else:
                self.btnPause.setText('')
        self.frameStep = False

    def on_player_time_pos(self, action: str, timestamp: float, video_props: dict = None):
        """Callback function when player time position changes."""
        if not timestamp:
            return
        try:
            time_str = Functions.timestampToHMS(timestamp)
            self.playerTimeCurrentMs = timestamp
            self.playerTimeCurrent = time_str
            self.set_label_time_curr(time_str)

            if self.playerTimeTotalS - timestamp < 1:
                if self.config.getPlayerMuteVideoEnd():
                    if not self.playerControl.player.mute:
                        self.endMuteActive = True
                        self.playerControl.player.mute = True
            elif self.playerControl.player.mute and not self.config.getPlayerIsMuted():
                self.endMuteActive = False
                self.playerControl.player.mute = False

            if not self.is_slider_player_pressed():
                self.set_slider_pos_from_timestamp(timestamp, video_props)
        except Exception as e:
            self.log(1, 'Error: Cannot set player time to time label. %s' % e, 1)

    def on_player_volume(self, action: str, volume: float):
        self.set_volume_slider(int(volume), relative=False)

    def sanitize_seek(self, value: float, video_props: dict = None):
        """Seeks a relative time value in the player and validates bounds."""
        if video_props is None:
            video_props = getattr(self.parent, 'videoProps', {})
        if not video_props or not self.playerControl:
            return
        try:
            duration_ms = video_props.get('durationMs', 0)
            duration_hms = video_props.get('durationHMS', self.timeFormat)

            if value < 0 and self.playerTimeCurrentMs == 0:
                self.set_label_time_curr(self.timeFormat)
                self.playerTimeCurrent = self.timeFormat
                self.set_slider_pos_from_timestamp(0, video_props)
            elif value < 0 and self.playerTimeCurrentMs + value < 0:
                self.set_label_time_curr(self.timeFormat)
                self.playerTimeCurrent = self.timeFormat
                self.set_slider_pos_from_timestamp(0, video_props)
                self.playerControl.seek(0, 'absolute', 'exact')
            elif value > 0 and self.playerTimeCurrentMs + value > duration_ms:
                if self.sliderPlayer:
                    self.sliderPlayer.setValue(self.sliderPlayer.maximum())
                self.playerControl.seek(duration_hms, 'absolute', 'exact')
            else:
                self.playerControl.seek(value)
        except Exception as e:
            msg = 'Error: Cannot seek played file.'
            self.log(1, msg, 1, traceback=traceback.format_exc())

    def seek_from_slider(self, value: int, video_props: dict = None):
        """Seeks an absolute position based on slider value."""
        if video_props is None:
            video_props = getattr(self.parent, 'videoProps', {})
        if not self.sliderPlayer or not self.playerControl or not video_props:
            return
        max_val = self.sliderPlayer.maximum()
        if max_val <= 0:
            return
        percentage = (value / max_val) * 100
        duration_hms = video_props.get('durationHMS', self.timeFormat)
        try:
            if percentage <= 0:
                self.set_label_time_curr(self.timeFormat)
                self.set_slider_pos_from_timestamp(0, video_props)
                self.playerTimeCurrent = self.timeFormat
            elif percentage >= 100:
                self.sliderPlayer.setValue(max_val)
                self.playerControl.seek(duration_hms, 'absolute', 'exact')
                self.playerTimeCurrent = duration_hms
            else:
                self.playerControl.seek(percentage, 'absolute-percent')
        except SystemError as e:
            msg = 'Error: Cannot seek played file. Is any video loaded?'
            self.log(1, msg, 1, traceback=traceback.format_exc())

    def set_slider_pos_from_timestamp(self, timestamp: float, video_props: dict = None):
        if not self.sliderPlayer:
            return
        if video_props is None:
            video_props = getattr(self.parent, 'videoProps', {})
        duration = video_props.get('durationMs', 0) if video_props else 0
        if not duration or duration <= 0:
            self.sliderPlayer.setValue(0)
            return

        max_val = self.sliderPlayer.maximum()
        if timestamp >= duration:
            self.sliderPlayer.setValue(max_val)
        elif timestamp > 0:
            percentage = timestamp / duration
            self.sliderPlayer.setValue(int(percentage * max_val))
        elif timestamp <= 0:
            self.sliderPlayer.setValue(0)

    def is_slider_player_pressed(self) -> bool:
        slider_pressed = False
        try:
            slider_pressed = self.sliderPlayer.pressed
        except Exception:
            pass
        return slider_pressed

    def set_label_time_curr(self, timeHMS: str):
        if self.labelPlayerTimeCurr:
            self.labelPlayerTimeCurr.setText(timeHMS)

    def set_label_time_total(self, timeHMS: str):
        if self.labelPlayerTimeTotal:
            self.labelPlayerTimeTotal.setText(timeHMS)

    def set_mute_state(self, mute: bool):
        if self.playerControl:
            self.playerControl.mute(mute)
        if self.btnMute:
            if mute:
                self.btnMute.setText('婢')
            else:
                self.btnMute.setText('墳')

    def set_volume_slider(self, value: int, relative: bool = True):
        if not self.sliderVolume:
            return
        volume = self.sliderVolume.value()
        if relative:
            volume = volume + value
        else:
            volume = value
        volume = max(0, min(100, volume))
        self.sliderVolume.setValue(volume)

    def set_controls_state(self, state: bool):
        if self.framePlayerBtns:
            self.framePlayerBtns.setEnabled(state)
        if self.framePlayerProgress:
            self.framePlayerProgress.setEnabled(state)

    def toggle_pause(self):
        if self.playerControl:
            return self.playerControl.togglePause()
        return True

    def frame_step_forward(self):
        if self.playerControl:
            self.frameStep = True
            self.playerControl.frameStep()
            if self.btnPause:
                self.btnPause.setText('契')

    def frame_step_backward(self):
        if self.playerControl:
            self.frameStep = True
            self.playerControl.frameBackStep()
            if self.btnPause:
                self.btnPause.setText('契')

    def terminate_player(self):
        if self.playerControl and self.playerControl.player:
            try:
                self.log(1, "Terminating MPV player instance...")
                self.playerControl.player.terminate()
                if self.playerControl.player._event_thread:
                    self.playerControl.player._event_thread.join(timeout=2)
            except Exception as e:
                self.log(1, f"Error terminating MPV player: {e}", 1)
