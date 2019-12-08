import os
import json

class Config:

    def __init__(self):
        self.configFilePath = 'config.json'
        self.config = {
            'playerSliderFactor': 100,
            'playerVolumeStep': 5,
            'playerVolume': 75,
            'playerisMuted': False,
            'targetDirName': '',
            'targetDirs': [],
            'isQueuePaused': False,
        }
        self.initConfig()

    def initConfig(self):
        tmpConfig = False
        # Create config file or read it if it exists
        if not os.path.exists(self.configFilePath):
            self.saveConfig()
        else:
            with open(self.configFilePath) as jsonFile:
                try:
                    tmpConfig = json.load(jsonFile)
                except:
                    self.saveConfig()
        # Compare hardcoded config with json to add missing keys into json
        save = False
        if tmpConfig:
            for k, v in self.config.items():
                if k not in tmpConfig:
                    save = True
                    tmpConfig[k] = v
        self.config = tmpConfig
        if save:
            self.saveConfig()

    def saveConfig(self):
        with open(self.configFilePath, 'w') as outfile:
            json.dump(self.config, outfile, indent=1)

    def getPlayerVolume(self):
        return self.config['playerVolume']

    def getPlayerIsMuted(self):
        return self.config['playerisMuted']

    def getPlayerSliderFactor(self):
        return self.config['playerSliderFactor']

    def getTargetDirs(self):
        return self.config['targetDirs']

    def getTgtDirName(self):
        return self.config['targetDirName']

    def getQueueIsPaused(self):
        return self.config['queueIsPaused']

    def setPlayerVolume(self, volume):
        self.config['playerVolume'] = volume
        self.saveConfig()

    def setPlayerIsMuted(self, isMuted):
        self.config['playerisMuted'] = isMuted
        self.saveConfig()

    def setDirs(self, dirs):
        self.config['targetDirs'] = dirs
        self.saveConfig()

    def setTgtDirName(self, dirName):
        self.config['targetDirName'] = dirName
        self.saveConfig()

    def setQueueIsPaused(self, isPaused):
        self.config['queueIsPaused'] = isPaused
        self.saveConfig()
