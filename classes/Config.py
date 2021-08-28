import os
from PyQt5.QtCore import QSettings

class Config:

    ORGANIZATION_NAME = 'vommie'
    APP_NAME = 'PyCut'

    def __init__(self):
        self.settings = QSettings(self.ORGANIZATION_NAME, self.APP_NAME)
        self.configFilePath = self.getConfigFilePath()
        self.configPath = self.getConfigPath()
    # Info Getters

    def getConfigFilePath(self):
        try:
            if self.configFilePath: return self.configFilePath
        except: pass
        self.configFilePath = self.settings.fileName()
        return self.configFilePath

    def getConfigPath(self):
        try:
            if self.configPath: return self.configPath
        except: pass
        filePath = self.getConfigFilePath()
        path = os.path.normpath(filePath)
        dirName, baseName = os.path.split(path)
        self.configPath = dirName
        return self.configPath

    def getConfigDeshakePath(self):
        return '%s/deshake' % self.getConfigPath()

    def getJobsFilePath(self):
        return '%s/jobs.json' % self.getConfigPath()

    # Config File Getters

    def getTargetDirs(self) -> list:
        return self.settings.value('app/targetDirs', [], type=list)

    def getAppTgtDirName(self) -> str:
        return self.settings.value('app/targetDirName', '', type=str)

    def getAppGeometry(self):
        return self.settings.value('app/geometry')

    def getAppState(self):
        return self.settings.value('app/state')

    def getAppIncrementFilename(self) -> bool:
        return self.settings.value('app/incrementFilename', True, type=bool)

    def getAppPauseQueueOnStartWhenWaitingJobs(self) -> bool:
        return self.settings.value('app/pauseQueueOnStartWhenWaitingJobs', True, type=bool)

    def getAppWarnFileExistsInTgtDir(self) -> bool:
        return self.settings.value('app/warnFileExistsInTgtDir', True, type=bool)

    def getAppWarnFileExistsInJobs(self) -> bool:
        return self.settings.value('app/warnFileExistsInJobs', True, type=bool)

    def getAppWarnFileHashExistsInDB(self) -> bool:
        return self.settings.value('app/warnFileHashExistsInDB', True, type=bool)

    def getAppWarnCloseWhileRender(self) -> bool:
        return self.settings.value('app/warnCloseWhileRender', True, type=bool)

    def getAppSetAutoSection(self) -> bool:
        return self.settings.value('app/autoSection', True, type=bool)

    def getDialogLogGeometry(self):
        return self.settings.value('dialogLog/geometry')

    def getPlayerVolume(self) -> int:
        return self.settings.value('player/volume', 75, type=int)

    def getPlayerVolumeStep(self) -> int:
        return self.settings.value('player/volumeStep', 5, type=int)

    def getPlayerIsMuted(self) -> bool:
        return self.settings.value('player/isMuted', False, type=bool)

    def getPlayerSliderFactor(self) -> int:
        return self.settings.value('player/sliderFactor', 100, type=int)

    def getPlayerAutoPlay(self) -> bool:
        return self.settings.value('player/autoPlay', True, type=bool)

    def getQueueIsPaused(self) -> bool:
        return self.settings.value('queue/isPaused', False, type=bool)

    def getTaggerDBPath(self) -> str:
        return self.settings.value('tagger/dbPath', '', type=str)

    def getTaggerIsActive(self) -> bool:
        return self.settings.value('tagger/isActive', True, type=bool)

    def getTaggerIsWarningActive(self) -> bool:
        return self.settings.value('tagger/isWarningActive', True, type=bool)

    def getTaggerFilterTagIDs(self) -> list:
        tagIDs = self.settings.value('tagger/filterTagIDs', [], type=int)
        if not isinstance(tagIDs, list): tagIDs = []
        return tagIDs

    def getFiltersDeinterlacer(self) -> str:
        return self.settings.value('filters/deinterlacer', 'yadif', type=str)

    def getRenderVideoCodec(self) -> str:
        return self.settings.value('render/videoCodec', 'libx265', type=str)

    def getRenderCRF(self) -> int:
        return self.settings.value('render/crf', 21, type=int)

    def getRenderContainer(self) -> str:
        return self.settings.value('render/container', 'mkv', type=str)

    def getRenderPreset(self) -> str:
        return self.settings.value('render/preset', 'medium', type=str)

    def getRenderAudioCodec(self) -> str:
        return self.settings.value('render/audioCodec', 'aac', type=str)

    def getRenderAudioBitrate(self) -> int:
        return self.settings.value('render/audioBitrate', 128, type=int)

    # Config File Setters

    def setAppDirs(self, dirs : list[list[str, str]]) -> None:
        self.settings.setValue('app/targetDirs', dirs)

    def setAppTgtDirName(self, dirName: str) -> None:
        self.settings.setValue('app/targetDirName', dirName)

    def setAppGeometry(self, geometry) -> None:
        self.settings.setValue('app/geometry', geometry)

    def setAppState(self, state : bool) -> None:
        self.settings.setValue('app/state', state)

    def setAppIncrementFilename(self, state : bool) -> None:
        self.settings.setValue('app/incrementFilename', state)

    def setAppPauseQueueOnStartWhenWaitingJobs(self, state : bool) -> None:
        self.settings.setValue('app/pauseQueueOnStartWhenWaitingJobs', state)

    def setAppWarnFileExistsInTgtDir(self, state : bool) -> None:
        self.settings.setValue('app/warnFileExistsInTgtDir', state)

    def setAppWarnFileExistsInJobs(self, state : bool) -> None:
        self.settings.setValue('app/warnFileExistsInJobs', state)

    def setAppWarnFileHashExistsInDB(self, state : bool) -> None:
        self.settings.setValue('app/warnFileHashExistsInDB', state)

    def setAppWarnCloseWhileRender(self, state : bool) -> None:
        self.settings.setValue('app/warnCloseWhileRender', state)

    def setAppSetAutoSection(self, state : bool) -> None:
        self.settings.setValue('app/autoSection', state)

    def setDialogLogGeometry(self, geometry) -> None:
        self.settings.setValue('dialogLog/geometry', geometry)

    def setPlayerVolume(self, volume : int) -> None:
        self.settings.setValue('player/volume', volume)

    def setPlayerVolumeStep(self, volumeStep : int) -> None:
        self.settings.setValue('player/volumeStep', volumeStep)

    def setPlayerIsMuted(self, state : bool) -> None:
        self.settings.setValue('player/isMuted', state)

    def setPlayerAutoPlay(self, state : bool) -> None:
        self.settings.setValue('player/autoPlay', state)

    def setPlayerSliderFactor(self, factor : int) -> None:
        self.settings.setValue('player/sliderFactor', factor)

    def setQueueIsPaused(self, isPaused : bool) -> None:
        self.settings.setValue('queue/isPaused', isPaused)

    def setTaggerDBPath(self, path : str) -> None:
        self.settings.setValue('tagger/dbPath', path)

    def setTaggerIsActive(self, state : bool) -> None:
        self.settings.setValue('tagger/isActive', state)

    def setTaggerIsWarningActive(self, state : bool) -> None:
        self.settings.setValue('tagger/isWarningActive', state)

    def setTaggerFilterTagIDs(self, tagIDs : list[int]) -> None:
        self.settings.setValue('tagger/filterTagIDs', tagIDs)

    def setFiltersDeinterlacer(self, deinterlacer : str) -> None:
        self.settings.setValue('filters/deinterlacer', deinterlacer)

    def setRenderVideoCodec(self, codec : str) -> None:
        self.settings.setValue('render/videoCodec', codec)

    def setRenderCRF(self, crf : int) -> None:
        self.settings.setValue('render/crf', crf)

    def setRenderContainer(self, container : str) -> None:
        self.settings.setValue('render/container', container)

    def setRenderPreset(self, preset : str) -> None:
        self.settings.setValue('render/preset', preset)

    def setRenderAudioCodec(self, audioCodec : str) -> None:
        self.settings.setValue('render/audioCodec', audioCodec)

    def setRenderAudioBitrate(self, audioBitrate : int) -> None:
        self.settings.setValue('render/audioBitrate', audioBitrate)
