import os

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
            'srcFile': {
                'dirName': False,
                'fileName': False,
                'fileExt': False,
            },
            'tgtFile': {
                'dirName': False,
                'fileName': False,
                'fileExt': '.mkv',
                'count': 0,
            },
            'sections': [],
            'filters': {
                'crop': {},
                'deinterlace': {},
                'resize': {},
                'rotate': False,
                'deshake': {}
            },
            'state': 0,
            'log': False
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

    def getTgtFileNameLong(self):
        name = self.getTgtFileName()
        fileNameLong = name
        ext = self.getTgtFileExt()
        count = self.getTgtFileCount()
        if(count):
            fileNameLong = "%s - %02d" % (fileNameLong, count)
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

    def getPosition(self):
        return self._props.get('position')

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
        self._props['tgtFile'].update({'fileExt': fileExt})
        self.propValueChanged()

    def setTgtFileCount(self, count):
        self._props['tgtFile'].update({'count': count})
        self.propValueChanged()

    def setState(self, state):
        self._props.update({'state': state})
        self.propValueChanged()

    def setErrorID(self, id):
        self._props['error'].update({'id': id})
        self.propValueChanged()

    def setLog(self, log):
        self._props['log'] = log
        self.propValueChanged()

    def setPosition(self, position):
        # todo: check, position is not used, or move other jobs 1 down
        self._props.update({'position': position})
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
        sections = self._props.get('sections')
        sections.append([timeFrom, timeTo])
        self._props.update({'sections': sections})
        self.propValueChanged()

    def removeSection(self, index):
        sections = self._props.get('sections')
        sections.pop(index)
        self._props.update({'sections': sections})
        self.propValueChanged()

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
