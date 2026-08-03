import os
from PyQt6.QtWidgets import QMessageBox
from classes.TimerMessageBox import TimerMessageBox

class PowerManager:
    """
    Manages system power states (sleep and shutdown) triggered after queue rendering finishes.
    Controls UI button states and invokes system-level power commands after countdown confirmation.
    """

    def __init__(self, parent_widget, btn_sleep, btn_shutdown):
        self.parent = parent_widget
        self.btnSleep = btn_sleep
        self.btnShutdown = btn_shutdown
        self.powerMode = False

    def toggle_power_mode(self, mode: str, state: bool):
        """
        Toggles the queue shutdown / sleep buttons and sets the internal power mode.

        :param mode: 'sleep' or 'shutdown'
        :param state: True if button is checked, False otherwise
        """
        if state:
            self.powerMode = mode
        else:
            self.powerMode = False

        if mode == 'sleep':
            self.btnShutdown.setChecked(False)
        elif mode == 'shutdown':
            self.btnSleep.setChecked(False)

    def disable_power_mode(self):
        """
        Disables active power modes and unchecks corresponding UI buttons.
        """
        self.powerMode = False
        self.btnShutdown.setChecked(False)
        self.btnSleep.setChecked(False)

    def run_power_mode(self, mode: str = None) -> bool:
        """
        Executes the PC power mode action (sleep, shutdown) with a countdown timer dialog.

        :param mode: "sleep" or "shutdown". Uses current self.powerMode if None.
        :return: True if power action was executed, False if aborted or no mode set.
        """
        target_mode = mode or self.powerMode
        if not target_mode:
            return False

        if target_mode == 'sleep':
            messagebox = TimerMessageBox(
                timeout=5,
                title="Send to sleep",
                text="All jobs completed. Sending the PC to sleep mode.",
                parent=self.parent
            )
            result = messagebox.exec()
            if not result or result == QMessageBox.StandardButton.Abort:
                self.disable_power_mode()
                return False
            os.system('systemctl suspend')

        elif target_mode == 'shutdown':
            messagebox = TimerMessageBox(
                timeout=5,
                title="Shutdown",
                text="All jobs completed. Shutting down the PC.",
                parent=self.parent
            )
            result = messagebox.exec()
            if not result or result == QMessageBox.StandardButton.Abort:
                self.disable_power_mode()
                return False
            os.system('shutdown now -h')

        self.disable_power_mode()
        return True

    def get_active_mode(self):
        """Returns the currently active power mode ('sleep', 'shutdown', or False)."""
        return self.powerMode
