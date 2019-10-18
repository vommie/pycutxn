class PlayerControl():

    volume_step = 5

    def __init__(self, player):
        self.player = player
        player.loop_playlist = 'inf'
        self.set_keybindings()

    def set_keybindings(self):
        @self.player.on_key_press('MBTN_RIGHT')
        def binding_mbtn_left():
            self.pause()

        @self.player.on_key_press('WHEEL_DOWN')
        def binding_wheel_down():
            self.volume_down()

        @self.player.on_key_press('WHEEL_UP')
        def binding_wheel_up():
            self.volume_up()

    def play(self, filepath):
        self.player.play(filepath)

    def stop(self):
        self.player.stop()

    def pause(self):
        self.player.pause = not self.player.pause
        return self.player.pause

    def volume_down(self):
        if self.player.volume - self.volume_step >= self.volume_step:
            self.player.volume -= self.volume_step
        else:
            self.player.volume = 0.0

    def volume_up(self):
        if self.player.volume + self.volume_step <= 100:
            self.player.volume += self.volume_step
        else:
            self.player.volume = 100.0

    def frame_step(self):
        self.player.frame_step()

    def frame_back_step(self):
        self.player.frame_back_step()
