import os
from PyQt6.QtCore import QSettings

class Config:

    ORGANIZATION_NAME = 'vommie'
    APP_NAME = 'PyCutXn'

    def __init__(self):
        self.settings = QSettings(self.ORGANIZATION_NAME, self.APP_NAME)
        self.configFilePath = self.getConfigFilePath()
        self.configPath = self.getConfigPath()

    def getConfigFilePath(self):
        try:
            if hasattr(self, 'configFilePath') and self.configFilePath:
                return self.configFilePath
        except Exception:
            pass
        self.configFilePath = self.settings.fileName()
        return self.configFilePath

    def getConfigPath(self):
        try:
            if hasattr(self, 'configPath') and self.configPath:
                return self.configPath
        except Exception:
            pass
        filePath = self.getConfigFilePath()
        path = os.path.normpath(filePath)
        dirName, _ = os.path.split(path)
        self.configPath = dirName
        os.makedirs(self.configPath, exist_ok=True)
        return self.configPath

    def getConfigDeshakePath(self):
        return os.path.join(self.getConfigPath(), 'deshake')

    def getJobsFilePath(self):
        return os.path.join(self.getConfigPath(), 'jobs.json')

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

    def getAppWarnTgtFileExistsInTgtDir(self) -> bool:
        return self.settings.value('app/warnTgtFileExistsInTgtDir', True, type=bool)

    def getAppWarnBaseFileExistsInTgtDir(self) -> bool:
        return self.settings.value('app/warnBaseFileExistsInTgtDir', True, type=bool)

    def getAppWarnFileExistsInJobs(self) -> bool:
        return self.settings.value('app/warnFileExistsInJobs', True, type=bool)

    def getAppWarnFileHashExistsInDB(self) -> bool:
        return self.settings.value('app/warnFileHashExistsInDB', True, type=bool)

    def getAppWarnCloseWhileRender(self) -> bool:
        return self.settings.value('app/warnCloseWhileRender', True, type=bool)

    def getSectionsAutoCreate(self) -> bool:
        return self.settings.value('sections/autoCreate', True, type=bool)

    def getSectionsAutoRemove(self) -> bool:
        return self.settings.value('sections/autoRemove', True, type=bool)

    def getDialogLogGeometry(self):
        return self.settings.value('dialogLog/geometry')

    def getDialogEditDBGeometry(self):
        return self.settings.value('dialogEditDB/geometry')

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

    def getPlayerMuteVideoEnd(self) -> bool:
        return self.settings.value('player/muteVideoEnd', True, type=bool)

    def getPlayerBgColor(self) -> str:
        return self.settings.value('player/bgColor', '#444444', type=str)

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
        if not isinstance(tagIDs, list):
            tagIDs = []
        return tagIDs

    def getFiltersDeinterlacer(self) -> str:
        return self.settings.value('filters/deinterlacer', 'yadif', type=str)

    def getFiltersPreview(self) -> bool:
        return self.settings.value('filters/preview', True, type=bool)

    def getRenderVideoCodec(self) -> str:
        return self.settings.value('render/videoCodec', 'libsvtav1', type=str)

    def getRenderCRF(self) -> int:
        return self.settings.value('render/crf', 26, type=int)

    def getRenderContainer(self) -> str:
        return self.settings.value('render/container', 'mkv', type=str)

    def getRenderPreset(self) -> str:
        return self.settings.value('render/preset', '6', type=str)

    def getRenderAudioCodec(self) -> str:
        return self.settings.value('render/audioCodec', 'libopus', type=str)

    def getRenderAudioBitrate(self) -> int:
        return self.settings.value('render/audioBitrate', 128, type=int)

    # Config File Setters

    def setAppDirs(self, dirs: list) -> None:
        self.settings.setValue('app/targetDirs', dirs)

    def setAppTgtDirName(self, dirName: str) -> None:
        self.settings.setValue('app/targetDirName', dirName)

    def setAppGeometry(self, geometry) -> None:
        self.settings.setValue('app/geometry', geometry)

    def setAppState(self, state: bool) -> None:
        self.settings.setValue('app/state', state)

    def setAppIncrementFilename(self, state: bool) -> None:
        self.settings.setValue('app/incrementFilename', state)

    def setAppPauseQueueOnStartWhenWaitingJobs(self, state: bool) -> None:
        self.settings.setValue('app/pauseQueueOnStartWhenWaitingJobs', state)

    def setAppWarnTgtFileExistsInTgtDir(self, state: bool) -> None:
        self.settings.setValue('app/warnTgtFileExistsInTgtDir', state)

    def setAppWarnBaseFileExistsInTgtDir(self, state: bool) -> None:
        self.settings.setValue('app/warnBaseFileExistsInTgtDir', state)

    def setAppWarnFileExistsInJobs(self, state: bool) -> None:
        self.settings.setValue('app/warnFileExistsInJobs', state)

    def setAppWarnFileHashExistsInDB(self, state: bool) -> None:
        self.settings.setValue('app/warnFileHashExistsInDB', state)

    def setAppWarnCloseWhileRender(self, state: bool) -> None:
        self.settings.setValue('app/warnCloseWhileRender', state)

    def setSectionsAutoCreate(self, state: bool) -> None:
        self.settings.setValue('sections/autoCreate', state)

    def setSectionsAutoRemove(self, state: bool) -> None:
        self.settings.setValue('sections/autoRemove', state)

    def setDialogLogGeometry(self, geometry) -> None:
        self.settings.setValue('dialogLog/geometry', geometry)

    def setDialogEditDBGeometry(self, geometry) -> None:
        self.settings.setValue('dialogEditDB/geometry', geometry)

    def setPlayerVolume(self, volume: int) -> None:
        self.settings.setValue('player/volume', volume)

    def setPlayerVolumeStep(self, volumeStep: int) -> None:
        self.settings.setValue('player/volumeStep', volumeStep)

    def setPlayerIsMuted(self, state: bool) -> None:
        self.settings.setValue('player/isMuted', state)

    def setPlayerAutoPlay(self, state: bool) -> None:
        self.settings.setValue('player/autoPlay', state)

    def setPlayerMuteVideoEnd(self, state: bool) -> None:
        self.settings.setValue('player/muteVideoEnd', state)

    def setPlayerSliderFactor(self, factor: int) -> None:
        self.settings.setValue('player/sliderFactor', factor)

    def setPlayerBgColor(self, color: str) -> None:
        self.settings.setValue('player/bgColor', color)

    def setQueueIsPaused(self, isPaused: bool) -> None:
        self.settings.setValue('queue/isPaused', isPaused)

    def setTaggerDBPath(self, path: str) -> None:
        self.settings.setValue('tagger/dbPath', path)

    def setTaggerIsActive(self, state: bool) -> None:
        self.settings.setValue('tagger/isActive', state)

    def setTaggerIsWarningActive(self, state: bool) -> None:
        self.settings.setValue('tagger/isWarningActive', state)

    def setTaggerFilterTagIDs(self, tagIDs: list) -> None:
        self.settings.setValue('tagger/filterTagIDs', tagIDs)

    def setFiltersDeinterlacer(self, deinterlacer: str) -> None:
        self.settings.setValue('filters/deinterlacer', deinterlacer)

    def setFiltersPreview(self, state: bool) -> None:
        self.settings.setValue('filters/preview', state)

    def setRenderVideoCodec(self, codec: str) -> None:
        self.settings.setValue('render/videoCodec', codec)

    def setRenderCRF(self, crf: int) -> None:
        self.settings.setValue('render/crf', crf)

    def setRenderContainer(self, container: str) -> None:
        self.settings.setValue('render/container', container)

    def setRenderPreset(self, preset: str) -> None:
        self.settings.setValue('render/preset', str(preset))

    def setRenderAudioCodec(self, audioCodec: str) -> None:
        self.settings.setValue('render/audioCodec', audioCodec)

    def setRenderAudioBitrate(self, audioBitrate: int) -> None:
        self.settings.setValue('render/audioBitrate', audioBitrate)
