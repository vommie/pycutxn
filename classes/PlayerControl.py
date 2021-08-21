class PlayerControl():

    volumeStep = 5

    def __init__(self, player, config):
        self.config = config
        self.player = player
        player.loop_file = 'inf'

    def play(self, filepath):
        self.player.play(filepath)

    def stop(self):
        self.player.stop()

    def togglePause(self):
        self.player.pause = not self.player.pause
        return self.player.pause

    def pause(self, state : bool):
        self.player.pause = state
        return self.player.pause

    def volumeDown(self):
        if self.player.volume - self.volumeStep >= self.volumeStep:
            self.player.volume -= self.volumeStep
        else:
            self.player.volume = 0.0
        self.config.setPlayerVolume(self.player.volume)

    def volumeUp(self):
        if self.player.volume + self.volumeStep <= 100:
            self.player.volume += self.volumeStep
        else:
            self.player.volume = 100.0
        self.config.setPlayerVolume(self.player.volume)

    def volume(self, volume):
        if volume > 100:
            volume = 100
        if volume < 0:
            volume = 0
        self.player.volume = volume
        self.config.setPlayerVolume(self.player.volume)

    def mute(self, mute):
        self.player.mute = mute
        self.config.setPlayerIsMuted(self.player.mute)

    def frameStep(self):
        self.player.frame_step()

    def frameBackStep(self):
        self.player.frame_back_step()

    def seek(self, amount, reference='relative', precision='exact'):
        self.player.seek(amount, reference, precision)
