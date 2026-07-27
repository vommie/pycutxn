class PlayerControl():

    volumeStep = 5

    def __init__(self, player, config):
        self.config = config
        self.player = player

    def play(self, filepath):
        try:
            self.player.play(filepath)
        except Exception:
            pass

    def stop(self):
        try:
            self.player.stop()
        except Exception:
            pass

    def togglePause(self):
        try:
            self.player.pause = not self.player.pause
            return self.player.pause
        except Exception:
            return True

    def pause(self, state : bool):
        try:
            self.player.pause = state
            return self.player.pause
        except Exception:
            return True

    def volumeDown(self):
        try:
            if self.player.volume - self.volumeStep >= self.volumeStep:
                self.player.volume -= self.volumeStep
            else:
                self.player.volume = 0.0
            self.config.setPlayerVolume(self.player.volume)
        except Exception:
            pass

    def volumeUp(self):
        try:
            if self.player.volume + self.volumeStep <= 100:
                self.player.volume += self.volumeStep
            else:
                self.player.volume = 100.0
            self.config.setPlayerVolume(self.player.volume)
        except Exception:
            pass

    def volume(self, volume):
        try:
            if volume > 100:
                volume = 100
            if volume < 0:
                volume = 0
            self.player.volume = volume
            self.config.setPlayerVolume(self.player.volume)
        except Exception:
            pass

    def mute(self, mute):
        try:
            self.player.mute = mute
            self.config.setPlayerIsMuted(self.player.mute)
        except Exception:
            pass

    def frameStep(self):
        try:
            self.player.frame_step()
        except Exception:
            pass

    def frameBackStep(self):
        try:
            self.player.frame_back_step()
        except Exception:
            pass

    def seek(self, amount, reference='relative', precision='exact'):
        try:
            self.player.seek(amount, reference, precision)
        except Exception:
            pass
