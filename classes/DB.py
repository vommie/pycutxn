import sqlite3
import os
from .Functions import Functions

# XnView Database Schema:
#
# Folders:
# FolderID INT PRIMARY KEY AUTOINCREMENT
# Pathname TEXT NOT NULL UNIQUE
#
# Images:
# ImageID INT PRIMARY KEY AUTOINCREMENT
# FolderID INT NOT NULL REFERENCES Folders(FolderID) ON DELETE CASCADE
# Filename TEXT NOT NULL
# Size INT
# ModifiedDate DATE
# Rating INT DEFAULT 0
# Color INT DEFAULT 0
# Meta BLOB
# UNIQUE (Filename, FolderID))
# HashID INT (Added by Pycut)
#
# Tags:
# TagID INT PRIMARY KEY
# Label CHAR(64)
# ParentID INT
# ID INT
# Hidden INTEGER DEFAULT 0
# Description CHAR(96)
# Shortcut CHAR(32)
# UNIQUE (Label, ParentID)
#
# TagsTree:
# ImageID INT NOT NULL REFERENCES Images(ImageID)
# TagID INT NOT NULL REFERENCES Tags(TagID)
# UNIQUE(ImageID, TagID)
#
# Hashes (Added by PyCut):
# HashID INT PRIMARY KEY AUTOINCREMENT
# Hash TEXT NOT NULL UNIQUE
# DateTime TEXT

class DB:

    def __init__(self, dbPath, log):
        self.log = log
        self.dbPath = dbPath

    def connect(self):
        if os.path.isfile(self.dbPath):
            conn = sqlite3.connect(self.dbPath)
            return conn
        else:
            return False

    def disconnect(self, conn):
        if conn: conn.close()

    def testConnection(self):
        conn = self.connect()
        if conn:
            self.disconnect(conn)
            return True
        return False

    def getFolderID(self, path):
        path = Functions.appendTrailingSlash(path)
        self.log(3, 'Get FolderID for path: "%s" ...' % path)
        folderID = False
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute("select FolderID from Folders where Pathname = '%s' collate nocase;" % path)
            conn.commit()
            folderID = c.fetchone()
            self.disconnect(conn)
        except AttributeError:
            raise Exception('Cannot connect to Database')
        if folderID:
            folderID = int(folderID[0])
            self.log(3, 'FolderID found: %s' % folderID)
        else:
            self.log(3, 'No folderID found')
            folderID = False
        return folderID

    def insertPath(self, path):
        path = Functions.appendTrailingSlash(path)
        self.log(3, 'Insert new path: "%s" ...' % path)
        folderID = False
        maxFolderID = False
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute("select max(FolderID) from Folders;")
            conn.commit()
            maxFolderID = c.fetchone()
        except AttributeError:
            raise Exception('Cannot connect to Database')
        if maxFolderID: maxFolderID = int(maxFolderID[0])
        else: self.log(3, 'No max folderID found. Cannot create new folderID.')
        if not maxFolderID: return False
        folderID = maxFolderID + 1
        try:
            c.execute("insert into Folders(FolderID,Pathname) values('%s','%s');" % (folderID, path))
            conn.commit()
            maxFolderID = c.fetchone()
            self.disconnect(conn)
        except AttributeError:
            raise Exception('Cannot connect to Database')
        self.log(3, 'Path inserted with folderID: "%s".' % folderID)
        return folderID

    def getImageID(self, folderID, fileName):
        self.log(3, 'Get ImageID for folderID "%s" with file name "%s" ...' % (folderID, fileName))
        imageID = False
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute("select ImageID from Images where FolderID = %s and Filename = '%s' collate nocase;" % (folderID, fileName))
            conn.commit()
            imageID = c.fetchone()
            self.disconnect(conn)
        except AttributeError:
            raise Exception('NoConnection')
        if imageID:
            imageID = imageID[0]
            imageID = int(imageID)
            self.log(3, 'ImageID found: %s' % imageID)
        else:
            self.log(3, 'No ImageID found')
            imageID = False
        return imageID

    def insertImage(self, folderID, fileName):
        self.log(3, 'Insert new image: "%s" ...' % fileName)
        imageID = False
        maxImageID = False
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute("select max(ImageID) from Images")
            conn.commit()
            maxImageID = c.fetchone()
        except AttributeError:
            raise Exception('Cannot connect to Database')
        if maxImageID: maxImageID = int(maxImageID[0])
        else: self.log(3, 'No max folderID found. Cannot create new folderID.')
        if not maxImageID: return False
        imageID = maxImageID + 1
        try:
            c.execute("insert into Images(ImageID,FolderID,Filename,Size,ModifiedDate) values('%s','%s','%s',0,0);" % (imageID, folderID, fileName))
            conn.commit()
            maxImageID = c.fetchone()
            self.disconnect(conn)
        except AttributeError:
            raise Exception('Cannot connect to Database')
        self.log(3, 'Image inserted with imageID: "%s".' % imageID)
        return imageID

    def getTagIDs(self, imageID):
        self.log(3, 'Get TagIDs for imageID: "%s" ...' % imageID)
        tags = []
        try:
            conn = self.connect()
            c = conn.cursor()
            for row in c.execute("select TagID from TagsTree where ImageID = %s;" % imageID):
                tags.append(row[0])
            conn.commit()
            self.disconnect(conn)
        except AttributeError:
            raise Exception('NoConnection')
        if tags: self.log(3, 'TagIDs found: %s' % tags)
        else: self.log(3, 'No TagIDs found')
        return tags

    def getRating(self, imageID):
        self.log(3, 'Get Rating for imageID: "%s" ...' % imageID)
        rating = False
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute("select Rating from Images where ImageID = %s collate nocase;" % imageID)
            conn.commit()
            rating = c.fetchone()
            self.disconnect(conn)
        except AttributeError:
            raise Exception('NoConnection')
        if rating:
            rating = rating[0]
            rating = int(rating)
            self.log(3, 'Rating found: %s' % rating)
        else:
            self.log(3, 'No Rating found')
            rating = False
        return rating

    def setRating(self, imageID, folderID, rating):
        self.log(3, 'Set rating "%s" for folderID "%s" / imageID: "%s" ...' % (rating, folderID, imageID))
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute("update Images set Rating='%s' where ImageID='%s' and FolderID='%s';" % (rating, imageID, folderID))
            conn.commit()
            self.disconnect(conn)
        except AttributeError:
            raise Exception('NoConnection')
        return True

    def getTagsTree(self):
        self.log(3, 'Get tags tree ...')
        tagsTree = []
        try:
            conn = self.connect()
            c = conn.cursor()
            for row in c.execute("select TagID, Label, ParentID, ID from Tags order by ParentID, Label;"):
                tagsTree.append({'tagID': row[0], 'parentID': row[2], 'label': row[1]})
            conn.commit()
            self.disconnect(conn)
        except AttributeError:
            raise Exception('NoConnection')
        self.log(3, 'Tags tree found:\n%s' % tagsTree)
        return tagsTree

    def setTags(self, imageID, tagIDs):
        self.log(3, 'Set tagID "%s" for imageID "%s" ...' % (tagIDs, imageID))
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute("delete from TagsTree where ImageID = %s" % (imageID))
            conn.commit()
        except AttributeError:
            raise Exception('NoConnection')
        try:
            for tagID in tagIDs:
                c.execute("insert into TagsTree (ImageID,TagID) values (%s, %s);" % (imageID, tagID))
            conn.commit()
            self.disconnect(conn)
        except AttributeError:
            raise Exception('NoConnection')
        return True

    def createHashTable(self):
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute("create table if not exists Hashes(HashID integer primary key autoincrement, Hash text, DateTime text not null);")
            conn.commit()
            self.disconnect(conn)
        except AttributeError:
            raise Exception('NoConnection')
        try:
            self.addHashIDColumnToImages()
        except Exception as e:
            raise Exception(str(e))
        return True

    def addHashIDColumnToImages(self):
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute("alter table Images add column HashID integer;")
            conn.commit()
            self.disconnect(conn)
        except AttributeError:
            raise Exception('NoConnection')
        except Exception as e:
            if 'dupli' in str(e): return True
            else: raise Exception(str(e))
        return True

    def insertHash(self, hash):
        self.log(3, 'Set hash "%s" ...' % hash)
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute("insert into Hashes(Hash,DateTime) values ('%s', CURRENT_TIMESTAMP);" % hash)
            conn.commit()
            self.disconnect(conn)
        except AttributeError:
            raise Exception('NoConnection')

    def getHashData(self, hash):
        self.log(3, 'Get hash data for hash: "%s" ...' % hash)
        data = [False, False]
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute("select HashID, DateTime from Hashes where hash = '%s';" % hash)
            conn.commit()
            result = c.fetchone()
            self.disconnect(conn)
        except AttributeError:
            raise Exception('Cannot connect to Database')
        if result:
            self.log(3, 'Hash data found with HashID: %s' % result[0])
            data[0] = result[0]
            data[1] = result[1]
        else: self.log(3, 'No hash data found')
        return data

    def getFileListByHashID(self, hashID):
        '''Returns a array of paths to files for a hashID'''
        self.log(3, 'Get filepaths for hashID "%s" ...' % hashID)
        filePaths = []
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute("select Filename, FolderID from Images where HashID = %s collate nocase;" % hashID)
            conn.commit()
            results = c.fetchall()
            self.disconnect(conn)
        except AttributeError:
            raise Exception('NoConnection')
        if not results: return filePaths
        for fileName, folderID in results:
            if not fileName or not folderID: raise Exception('Filename or FolderID missing in query results.')
            try:
                conn = self.connect()
                c = conn.cursor()
                c.execute("select Pathname from Folders where FolderID = %s collate nocase;" % folderID)
                conn.commit()
                results = c.fetchone()
                self.disconnect(conn)
            except AttributeError:
                raise Exception('NoConnection')
            if results:
                pathName = results[0]
                filePaths.append(Functions.removeTrailingSlash('%s%s' % (pathName, fileName)))
        return filePaths

    def setHashID(self, imageID, folderID, hashID):
        self.log(3, 'Set hashID "%s" for folderID "%s" / imageID: "%s" ...' % (hashID, folderID, imageID))
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute("update Images set HashID='%s' where ImageID='%s' and FolderID='%s';" % (hashID, imageID, folderID))
            conn.commit()
            self.disconnect(conn)
        except AttributeError:
            raise Exception('NoConnection')
        return True
