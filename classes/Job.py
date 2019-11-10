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
                'suffixes': []
            },
            'sections': [],
            'state': 0,
        }

    def initPaths(self, filePath):
        paths = self.splitPath(filePath)
        self.setSrcDirName(paths.get('dirName'))
        self.setSrcFileName(paths.get('fileName'))
        self.setSrcFileExt(paths.get('fileExt'))
        self.setTgtDirName(paths.get('dirName'))
        self.setTgtFileName(paths.get('fileName'))
        self.setTgtFileExt(paths.get('fileExt'))

    # Props observers

    def propValueChanged(self):
        for callback in self._propsObservers:
            callback(self.getID(), self.getProps())

    def bindToProps(self, callback):
        self._propsObservers.append(callback)

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

    def getTgtFileSuffixes(self):
        return self._props['tgtFile'].get('suffixes')

    def getTgtFileCount(self):
        return self._props['tgtFile'].get('count')

    def getTgtFileNameLong(self):
        name = self.getTgtFileName()
        fileNameLong = name
        ext = self.getTgtFileExt()
        count = self.getTgtFileCount()
        suffix = ' '.join(self.getTgtFileSuffixes())
        if(count):
            fileNameLong = "%s - %02d" % (fileNameLong, count)
        if(suffix):
            fileNameLong = "%s - %s" % (fileNameLong, suffix)
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

    def addTgtFileSuffix(self, suffix):
        suffixes = self._props['tgtFile'].get('suffixes')
        if suffix not in suffixes:
            suffixes.append(suffix)
        self._props['tgtFile'].update({'suffixes': suffixes})

    def removeTgtFileSuffix(self, suffix):
        suffixes = self._props['tgtFile'].get('suffixes')
        if suffix in suffixes:
            suffixes.remove(suffix)
        self._props['tgtFile'].update({'suffixes': suffixes})

    def clearTgtFileSuffixes(self):
        self._props['tgtFile'].update({'suffixes': []})

    def addSection(self, timeFrom, timeTo):
        sections = self._props.get('sections')
        sections.append([timeFrom, timeTo])
        self._props.update({'sections': sections})

    def removeSection(self, index):
        sections = self._props.get('sections')
        sections.pop(index)
        self._props.update({'sections': sections})

    def moveSection(self, fromIndex, toIndex):
        if fromIndex == toIndex:
            return False
        sections = self._props.get('sections')
        fromSection = sections[fromIndex]
        toSection = sections[toIndex]
        sections[fromIndex] = toSection
        sections[toIndex] = fromSection
        self._props.update({'sections': sections})

    def clearSections(self):
        self._props.update({'sections': []})
