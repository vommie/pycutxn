import os

# Own dictionary to be informed when props change
class JobDict(dict):
    def __init__(self, parent, initialDict):
        self.parent = parent
        for k,v in initialDict.items():
          if isinstance(v,dict):
            initialDict[k] = JobDict(self.parent, v)
        super().__init__(initialDict)

    def __setitem__(self, item, value):
        if isinstance(value,dict):
          _value = JobDict(self.parent, value)
        else:
          _value = value
        super().__setitem__(item, _value)
        self.parent.jobUpdated()

    def update(self, iterable):
        super(JobDict, self).update(iterable)
        self.parent.jobUpdated()

class Job():

    def __init__(self, parent = False, srcFilePath = False, props = False):
        self.parent = parent
        if srcFilePath:
            self.initProps()
            self.initPaths(srcFilePath)
        if props:
            self.props = props

    def jobUpdated(self):
        if self.parent:
            self.parent.jobUpdated()

    def initProps(self):
        self.props = JobDict(self, {
            'srcFile': {
                'dirName': False,
                'baseName': False,
                'fileName': False,
                'fileExt': False,
            },
            'tgtFile': {
                'dirName': False,
                'baseName': False,
                'fileName': False,
                'fileExt': False,
                'count': 0,
                'suffixes': []
            },
            'sections': [],
            'state': 'pending',
        })

    def reset(self):
        self.initProps()

    def initPaths(self, filePath):
        paths = self.splitPath(filePath)
        self.setSrcDirName(paths.get('dirName'))
        self.setSrcBaseName(paths.get('baseName'))
        self.setSrcFileName(paths.get('fileName'))
        self.setSrcFileExt(paths.get('fileExt'))
        self.setTgtDirName(paths.get('dirName'))
        self.setTgtBaseName(paths.get('baseName'))
        self.setTgtFileName(paths.get('fileName'))
        self.setTgtFileExt(paths.get('fileExt'))

    def splitPath(self, path):
        path = os.path.normpath(path)
        dirName, baseName = os.path.split(path)
        fileName, fileExt = os.path.splitext(baseName)
        return {
            'dirName': dirName,
            'baseName': baseName,
            'fileName': fileName,
            'fileExt': fileExt
        }

    def resetSections(self):
        self.sections = []

    def getSrcDirName(self):
        return self.props['srcFile'].get('dirName')

    def getSrcBaseName(self):
        return self.props['srcFile'].get('baseName')

    def getSrcFileName(self):
        return self.props['srcFile'].get('fileName')

    def getSrcFileExt(self):
        return self.props['srcFile'].get('fileExt')

    def getTgtDirName(self):
        return self.props['tgtFile'].get('dirName')

    def getTgtBaseName(self):
        return self.props['tgtFile'].get('baseName')

    def getTgtFileName(self):
        return self.props['tgtFile'].get('fileName')

    def getTgtFileExt(self):
        return self.props['tgtFile'].get('fileExt')

    def getTgtFileSuffixes(self):
        return self.props['tgtFile'].get('suffixes')

    def getTgtFileCount(self):
        return self.props['tgtFile'].get('count')

    def getTgtFileNameLong(self):
        return "%s%s" % (self.getTgtFileName(), self.getTgtFileExt())

    def getSections(self):
        return self.props.get('sections')

    def getState(self):
        return self.props.get('state')

    def setSrcDirName(self, dirName):
        self.props['srcFile'].update({'dirName': dirName})

    def setSrcBaseName(self, baseName):
        self.props['srcFile'].update({'baseName': baseName})

    def setSrcFileName(self, fileName):
        self.props['srcFile'].update({'fileName': fileName})

    def setSrcFileExt(self, fileExt):
        self.props['srcFile'].update({'fileExt': fileExt})

    def setTgtDirName(self, dirName):
        self.props['tgtFile'].update({'dirName': dirName})

    def setTgtBaseName(self, baseName):
        self.props['tgtFile'].update({'baseName': baseName})

    def setTgtFileName(self, fileName):
        self.props['tgtFile'].update({'fileName': fileName})

    def setTgtFileExt(self, fileExt):
        self.props['tgtFile'].update({'fileExt': fileExt})

    def setTgtFileCount(self, count):
        self.props['tgtFile'].update({'count': count})

    def setState(self, state):
        self.props.update({'state': state})

    def addTgtFileSuffix(self, suffix):
        suffixes = self.props['tgtFile'].get('suffixes')
        if suffix not in suffixes:
            suffixes.append(suffix)
        self.props['tgtFile'].update({'suffixes': suffixes})

    def removeTgtFileSuffix(self, suffix):
        suffixes = self.props['tgtFile'].get('suffixes')
        if suffix in suffixes:
            suffixes.remove(suffix)
        self.props['tgtFile'].update({'suffixes': suffixes})

    def clearTgtFileSuffixes(self):
        self.props['tgtFile'].update({'suffixes': []})

    def addSection(self, timeFrom, timeTo):
        sections = self.props.get('sections')
        sections.append([timeFrom, timeTo])
        self.props.update({'sections': sections})

    def removeSection(self, index):
        sections = self.props.get('sections')
        sections.pop(index)
        self.props.update({'sections': sections})

    def moveSection(self, fromIndex, toIndex):
        if fromIndex == toIndex:
            return False
        sections = self.props.get('sections')
        fromSection = sections[fromIndex]
        toSection = sections[toIndex]
        sections[fromIndex] = toSection
        sections[toIndex] = fromSection
        self.props.update({'sections': sections})

    def clearSections(self):
        self.props.update({'sections': []})
