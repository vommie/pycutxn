from PyQt5.QtCore import QSettings

class Config:

    ORGANIZATION_NAME = 'vommie'
    APP_NAME = 'PyCut'

    def __init__(self):
        self.settings = QSettings(self.ORGANIZATION_NAME, self.APP_NAME)

    # Getters

    def getTargetDirs(self):
        return self.settings.value('app/targetDirs', [], type=list)

    def getTgtDirName(self):
        return self.settings.value('app/targetDirName', '', type=str)

    def getAppGeometry(self):
        return self.settings.value('app/geometry')

    def getAppState(self):
        return self.settings.value('app/state')

    def getAppJobsPath(self):
        return 'jobs.json'

    def getPlayerVolume(self):
        return self.settings.value('player/volume', 75, type=int)

    def getPlayerVolumeStep(self):
        return self.settings.value('player/volumeStep', 5, type=int)

    def getPlayerIsMuted(self):
        return self.settings.value('player/isMuted', False, type=bool)

    def getPlayerSliderFactor(self):
        return self.settings.value('player/sliderFactor', 100, type=int)

    def getQueueIsPaused(self):
        return self.settings.value('queue/isPaused', False, type=bool)

    def getTaggerDBPath(self):
        return self.settings.value('tagger/dbPath', False, type=str)

    def getTaggerIsActive(self):
        return self.settings.value('tagger/isActive', True, type=bool)

    def getTaggerIsWarningActive(self):
        return self.settings.value('tagger/isWarningActive', True, type=bool)

    def getFiltersDeinterlacer(self):
        return self.settings.value('filters/deinterlacer', 'yadif', type=str)

    # Setters

    def setDirs(self, dirs):
        self.settings.setValue('app/targetDirs', dirs)

    def setTgtDirName(self, dirName):
        self.settings.setValue('app/targetDirName', dirName)

    def setAppGeometry(self, geometry):
        self.settings.setValue('app/geometry', geometry)

    def setAppState(self, state):
        self.settings.setValue('app/state', state)

    def setPlayerVolume(self, volume):
        self.settings.setValue('player/volume', volume)

    def setPlayerVolumeStep(self, volumeStep):
        self.settings.setValue('player/volumeStep', volumeStep)

    def setPlayerIsMuted(self, state):
        self.settings.setValue('player/isMuted', state)

    def setPlayerSliderFactor(self, factor):
        self.settings.setValue('player/sliderFactor', factor)

    def setQueueIsPaused(self, isPaused):
        self.settings.setValue('queue/isPaused', isPaused)

    def setTaggerDBPath(self, path):
        self.settings.setValue('tagger/dbPath', path)

    def setTaggerIsActive(self, state):
        self.settings.setValue('tagger/isActive', state)

    def setTaggerIsWarningActive(self, state):
        self.settings.setValue('tagger/isWarningActive', state)

    def setFiltersDeinterlacer(self, deinterlacer):
        self.settings.setValue('filters/deinterlacer', deinterlacer)
