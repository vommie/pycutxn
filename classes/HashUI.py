from PyQt6 import QtWidgets, uic

class HashUI(QtWidgets.QDialog):
    def __init__(self, parent):
        self.parent = parent
        super(HashUI, self).__init__(parent)
        uic.loadUi('%s/gui/hash.ui' % self.parent.rootDir, self)
        self.cancelled = False

    def reset(self):
        """Resets the state of the dialog for a new hashing operation."""
        self.cancelled = False
        self.progressBar.setValue(0)

    def closeEvent(self, event):
        """
        This event is called when the user closes the dialog window.
        We set the cancelled flag to signal the hashing process to stop.
        """
        self.cancelled = True
        self.parent.log(1, "Hashing dialog closed by user, cancelling operation.")
        event.accept()
