import os
import traceback

class Job():

    # Init functions

    def __init__(self, id, srcFilePath = False, props = False):
        self._propsObservers = []
        self.id = id
        if srcFilePath:
            self.initProps()
            self.initPaths(srcFilePath)
        if props:
            self._props = props

    def initProps(self):
        self._props = {
            'position': 0,
            'state': 0,
            'hashID': False,
            'srcFile': {
                'dirName': False,
                'fileName': False,
                'fileExt': False,
            },
            'tgtFile': {
                'dirName': False,
                'fileName': False,
                'fileExt': False,
                'count': 0,
                'sep': ' - '
            },
            'sections': [],
            'filters': {
                'crop': {},
                'deinterlace': {},
                'resize': {},
                'rotate': False,
                'deshake': {}
            },
            'renderSettings': {
                'videoCodec': False,
                'crf': False,
                'preset': False,
                'audioCodec': False,
                'audioBitrate': False,
                'container': False
            },
            'log': False,
        }

    def initPaths(self, filePath):
        paths = self.splitPath(filePath)
        self.setSrcDirName(paths.get('dirName'))
        self.setSrcFileName(paths.get('fileName'))
        self.setSrcFileExt(paths.get('fileExt'))
        self.setTgtDirName(paths.get('dirName'))
        self.setTgtFileName(paths.get('fileName'))

    # Props observers

    def propValueChanged(self):
        for callback in self._propsObservers:
            callback(self.getID(), self.getProps())

    def bindToProps(self, callback):
        self._propsObservers.append(callback)

    def clearPropObservers(self):
        self._propsObservers.clear()

    # Props getters

    def getProps(self):
        return self._props

    def getSrcDirName(self):
        return self._props['srcFile'].get('dirName')

    def getSrcFileName(self):
        return self._props['srcFile'].get('fileName')

    def getSrcFileExt(self):
        return self._props['srcFile'].get('fileExt')

    def getSrcFileNameLong(self):
        return '%s%s' % (self.getSrcFileName(), self.getSrcFileExt())

    def getSrcFilePathLong(self):
        return '%s/%s' % (self.getSrcDirName(), self.getSrcFileNameLong())

    def getTgtDirName(self):
        return self._props['tgtFile'].get('dirName')

    def getTgtFileName(self):
        return self._props['tgtFile'].get('fileName')

    def getTgtFileExt(self):
        return self._props['tgtFile'].get('fileExt')

    def getTgtFileCount(self):
        return self._props['tgtFile'].get('count')

    def getTgtFileSep(self):
        return self._props['tgtFile'].get('sep')

    def getTgtFileNameLong(self):
        name = self.getTgtFileName()
        fileNameLong = name
        ext = self.getTgtFileExt()
        count = self.getTgtFileCount()
        sep = self.getTgtFileSep()
        if(count):
            fileNameLong = '{f}{s}{c:02d}'.format(f=fileNameLong, s=sep, c=count)
        fileNameLong = "%s%s" % (fileNameLong, ext)
        return fileNameLong

    def getTgtFilePathLong(self):
        return '%s/%s' % (self.getTgtDirName(), self.getTgtFileNameLong())

    def getSections(self):
        return self._props.get('sections')

    def getState(self):
        return self._props.get('state')

    def getID(self):
        return self.id

    def getLog(self):
        return self._props['log']

    def getHashID(self):
        return self._props['hashID']

    def getPosition(self):
        return self._props.get('position')

    def getFilters(self):
        try:
            return self._props['filters']
        except:
            return False

    def getFilterCropState(self):
        try:
            self._props['filters']['crop']
            return self._props['filters']['crop'].get('active')
        except:
            return False

    def getFilterCropT(self):
        try:
            self._props['filters']['crop']
            px = self._props['filters']['crop'].get('t')
            if not px: px = 0
            return px
        except:
            return False

    def getFilterCropR(self):
        try:
            self._props['filters']['crop']
            px = self._props['filters']['crop'].get('r')
            if not px: px = 0
            return px
        except:
            return False

    def getFilterCropB(self):
        try:
            self._props['filters']['crop']
            px = self._props['filters']['crop'].get('b')
            if not px: px = 0
            return px
        except:
            return False

    def getFilterCropL(self):
        try:
            self._props['filters']['crop']
            px = self._props['filters']['crop'].get('l')
            if not px: px = 0
            return px
        except:
            return False

    def getFilterDeinterlaceState(self):
        try:
            self._props['filters']['deinterlace']
            return self._props['filters']['deinterlace'].get('active')
        except:
            return False

    def getFilterDeinterlaceDeinterlacer(self):
        try:
            self._props['filters']['deinterlace']
            return self._props['filters']['deinterlace'].get('deinterlacer')
        except:
            return False

    def getFilterResizeState(self):
        try:
            self._props['filters']['resize']
            return self._props['filters']['resize'].get('active')
        except:
            return False

    def getFilterResizeWidth(self):
        try:
            self._props['filters']['resize']
            return self._props['filters']['resize'].get('width')
        except:
            return False

    def getFilterResizeHeight(self):
        try:
            self._props['filters']['resize']
            return self._props['filters']['resize'].get('height')
        except:
            return False

    def getFilterDeshakeState(self):
        try:
            self._props['filters']
            return self._props['filters']['deshake'].get('active')
        except:
            return False

    def getFilterDeshakeFile(self):
        try:
            self._props['filters']
            return self._props['filters']['deshake'].get('file')
        except:
            return False

    def getFilterRotate(self):
        try:
            self._props['filters']
            return self._props['filters'].get('rotate')
        except:
            return False

    def getFilterPositions(self):
        try:
            self._props['filterPositions']
            return self._props.get('filterPositions')
        except:
            return { '0': 'crop', '1': 'deinterlace', '2': 'resize', '3': 'rotate', '4': 'deshake' }

    def getRenderSettingVideoCodec(self):
        return self._props['renderSettings'].get('videoCodec')

    def getRenderSettingCRF(self):
        return self._props['renderSettings'].get('crf')

    def getRenderSettingPreset(self):
        return self._props['renderSettings'].get('preset')

    def getRenderSettingAudioCodec(self):
        return self._props['renderSettings'].get('audioCodec')

    def getRenderSettingAudioBitrate(self):
        return self._props['renderSettings'].get('audioBitrate')

    def getRenderSettingContainer(self):
        return self._props['renderSettings'].get('container')

    # Props Setters

    def setProps(self, props):
        self._props = props
        self.propValueChanged()

    def setSrcDirName(self, dirName):
        self._props['srcFile'].update({'dirName': dirName})
        self.propValueChanged()

    def setSrcFileName(self, fileName):
        self._props['srcFile'].update({'fileName': fileName})
        self.propValueChanged()

    def setSrcFileExt(self, fileExt):
        self._props['srcFile'].update({'fileExt': fileExt})
        self.propValueChanged()

    def setTgtDirName(self, dirName):
        self._props['tgtFile'].update({'dirName': dirName})
        self.propValueChanged()

    def setTgtFileName(self, fileName):
        self._props['tgtFile'].update({'fileName': fileName})
        self.propValueChanged()

    def setTgtFileExt(self, fileExt):
        if fileExt[0] != '.': fileExt = '.%s' % fileExt
        self._props['tgtFile'].update({'fileExt': fileExt})
        self.propValueChanged()

    def setTgtFileCount(self, count):
        try:
            self._props['tgtFile'].update({'count': count})
            self.propValueChanged()
        except: raise Exception()

    def setState(self, state):
        self._props.update({'state': state})
        self.propValueChanged()

    def setLog(self, log):
        self._props['log'] = log
        self.propValueChanged()

    def setHashID(self, hashID):
        self._props['hashID'] = hashID
        self.propValueChanged()

    def setPosition(self, position):
        # todo: check, position is not used, or move other jobs 1 down
        self._props.update({'position': position})
        self.propValueChanged()

    def setFilters(self, filters):
        self._props['filters'] = filters
        self.propValueChanged()

    def setFilterCropState(self, state):
        self._props['filters']['crop'].update({'active': state})
        self.propValueChanged()

    def setFilterCropT(self, px):
        self._props['filters']['crop'].update({'t': px})
        self.propValueChanged()

    def setFilterCropR(self, px):
        self._props['filters']['crop'].update({'r': px})
        self.propValueChanged()

    def setFilterCropB(self, px):
        self._props['filters']['crop'].update({'b': px})
        self.propValueChanged()

    def setFilterCropL(self, px):
        self._props['filters']['crop'].update({'l': px})
        self.propValueChanged()

    def setFilterDeinterlaceState(self, state):
        if not self._props['filters']['deinterlace']: self._props['filters']['deinterlace'] = {}
        self._props['filters']['deinterlace'].update({'active': state})
        self.propValueChanged()

    def setFilterDeinterlaceDeinterlacer(self, deinterlacer):
        if not self._props['filters']['deinterlace']: self._props['filters']['deinterlace'] = {}
        self._props['filters']['deinterlace'].update({'deinterlacer': deinterlacer})
        self.propValueChanged()

    def setFilterResizeState(self, state):
        self._props['filters']['resize'].update({'active': state})
        self.propValueChanged()

    def setFilterResizeWidth(self, width):
        self._props['filters']['resize'].update({'width': width})
        self.propValueChanged()

    def setFilterResizeHeight(self, height):
        self._props['filters']['resize'].update({'height': height})
        self.propValueChanged()

    def setFilterDeshakeState(self, state):
        self._props['filters']['deshake'].update({'active': state})
        self.propValueChanged()

    def setFilterDeshakeFile(self, file):
        self._props['filters']['deshake'].update({'file': file})
        self.propValueChanged()

    def setFilterRotate(self, deg):
        self._props['filters'].update({'rotate': deg})
        self.propValueChanged()

    def setFilterPositions(self, positions):
        self._props.update({'filterPositions': positions})
        self.propValueChanged()

    def setRenderSettingVideoCodec(self, videoCodec : str):
        self._props['renderSettings'].update({'videoCodec': videoCodec})

    def setRenderSettingCRF(self, crf : int):
        self._props['renderSettings'].update({'crf': crf })

    def setRenderSettingPreset(self, preset : int):
        self._props['renderSettings'].update({'preset': preset })

    def setRenderSettingAudioCodec(self, audioCodec : str):
        self._props['renderSettings'].update({'audioCodec': audioCodec})

    def setRenderSettingAudioBitrate(self, audioBitrate : int):
        self._props['renderSettings'].update({'audioBitrate': audioBitrate})

    def setRenderSettingContainer(self, container : str):
        self._props['renderSettings'].update({'container': container})

    def setID(self, id):
        self.id = id

    # Other functions

    def splitPath(self, path):
        path = os.path.normpath(path)
        dirName, baseName = os.path.split(path)
        fileName, fileExt = os.path.splitext(baseName)
        return {
            'dirName': dirName,
            'fileName': fileName,
            'fileExt': fileExt
        }

    def addSection(self, timeFrom, timeTo):
        try:
            sections = self._props.get('sections')
            sections.append([timeFrom, timeTo])
            self._props.update({'sections': sections})
            self.propValueChanged()
        except Exception as e:
            raise Exception(traceback.format_exc())

    def removeSection(self, index):
        try:
            sections = self._props.get('sections')
            sections.pop(index)
            self._props.update({'sections': sections})
            self.propValueChanged()
        except Exception as e:
            raise Exception(traceback.format_exc())

    def moveSection(self, fromIndex, toIndex):
        if fromIndex == toIndex:
            return False
        sections = self._props.get('sections')
        fromSection = sections[fromIndex]
        toSection = sections[toIndex]
        sections[fromIndex] = toSection
        sections[toIndex] = fromSection
        self._props.update({'sections': sections})
        self.propValueChanged()

    def clearSections(self):
        self._props.update({'sections': []})
        self.propValueChanged()

    def unbindFromProps(self, callback):
        if callback in self._propsObservers:
            self._propsObservers.remove(callback)
