import os

class Job():

    def __init__(self, srcFilePath):
        path = os.path.normpath(srcFilePath)
        dirname, basename = os.path.split(path)
        filename, ext = os.path.splitext(basename)
        self.srcDirName = dirname
        self.srcBaseName = basename
        self.srcFileName = filename
        self.srcFileExt = ext
        self.tgtDirName = dirname
        self.tgtBaseName = basename
        self.tgtFileName = filename
        self.tgtFileExt = ext
        self.tgtFileCount = 0
        self.tgtFileSuffix = ''
        self.sections = []

    def reset(self):
        self.srcDirName = None
        self.srcBaseName = None
        self.srcFileName = None
        self.srcFileExt = None
        self.tgtDirName = None
        self.tgtBaseName = None
        self.tgtFileName = None
        self.tgtFileExt = None
        self.tgtFileCount = 0
        self.tgtFileSuffix = ''
        self.resetSections()

    def resetSections(self):
        self.sections = []

    def setSrcDirName(self, dirName):
        self.srcDirName = dirName

    def setSrcBaseName(self, baseName):
        self.srcBaseName = baseName

    def setSrcFileName(self, fileName):
        self.srcFileName = fileName

    def setSrcFileExt(self, fileExt):
        self.srcFileExt = fileExt

    def setTgtDirName(self, dirName):
        self.tgtDirName = dirName

    def setTgtBaseName(self, baseName):
        self.tgtBaseName = baseName

    def setTgtFileName(self, fileName):
        self.tgtFileName = fileName

    def setTgtFileExt(self, fileExt):
        self.tgtFileExt = fileExt

    def setTgtFileCount(self, fileCount):
        self.tgtFileCount = fileCount

    def setTgtFileSuffix(self, fileSuffix):
        self.tgtFileSuffix = fileSuffix

    def plusMinusFileCount(self, count = 0):
        self.tgtFileCount += count
        if self.tgtFileCount <= 0:
            self.tgtFileCount = 1

    def addRemoveSuffix(self, suffix):
        if suffix == False:
            suffix = self.tgtFileSuffix
        else:
            self.tgtFileSuffix = suffix

    def addSection(self, timeFrom, timeTo):
        self.sections.append([timeFrom, timeTo])
