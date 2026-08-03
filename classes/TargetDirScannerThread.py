import os
from PyQt6 import QtCore
from PyQt6.QtCore import pyqtSignal

class TargetDirScannerThread(QtCore.QThread):
    scanFinished = pyqtSignal(str, list, object, object, str) # (job_id, matches, hashID, dateTime, detailText)

    def __init__(self, job, hashID=False, dateTime=None, detailText=''):
        super().__init__()
        self.job_id = job.getID()
        self.path = job.getTgtDirName()
        self.fileName = job.getTgtFileName()
        self.sep = job.getTgtFileSep()
        self.count = job.getTgtFileCount()
        self.hashID = hashID
        self.dateTime = dateTime
        self.detailText = detailText

    def run(self):
        matches = []
        if self.path and os.path.isdir(self.path):
            searchName = '{f}{s}01'.format(f=self.fileName, s=self.sep) if int(self.count) > 0 else '{f}'.format(f=self.fileName)
            searchNameLower = searchName.lower()
            try:
                with os.scandir(self.path) as entries:
                    for entry in entries:
                        if entry.name.lower().startswith(searchNameLower):
                            matches.append(os.path.join(self.path, entry.name))
            except Exception:
                pass

        self.scanFinished.emit(self.job_id, matches, self.hashID, self.dateTime, self.detailText)
