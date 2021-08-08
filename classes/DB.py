import sqlite3
import os
from .Functions import Functions

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
            c.execute("select folderid from folders where pathname = '%s'" % path)
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

    def insertNewPath(self, path):
        path = Functions.appendTrailingSlash(path)
        self.log(3, 'Insert new path: "%s" ...' % path)
        folderID = False
        maxFolderID = False
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute("select max(folderid) from folders")
            conn.commit()
            maxFolderID = c.fetchone()
        except AttributeError:
            raise Exception('Cannot connect to Database')
        if maxFolderID: maxFolderID = int(maxFolderID[0])
        else: self.log(3, 'No max folderID found. Cannot create new folderID.')
        if not maxFolderID: return False
        folderID = maxFolderID + 1
        try:
            c.execute("insert into folders(folderid,pathname) values('%s','%s')" % (folderID, path))
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
            c.execute("select imageid from images where folderid = %s and filename = '%s'" % (folderID, fileName))
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

    def insertNewImage(self, folderID, fileName):
        self.log(3, 'Insert new image: "%s" ...' % fileName)
        imageID = False
        maxImageID = False
        try:
            conn = self.connect()
            c = conn.cursor()
            c.execute("select max(imageid) from images")
            conn.commit()
            maxImageID = c.fetchone()
        except AttributeError:
            raise Exception('Cannot connect to Database')
        if maxImageID: maxImageID = int(maxImageID[0])
        else: self.log(3, 'No max folderID found. Cannot create new folderID.')
        if not maxImageID: return False
        imageID = maxImageID + 1
        try:
            c.execute("insert into images(imageid,folderID,filename,size,modifieddate) values('%s','%s','%s',0,0)" % (imageID, folderID, fileName))
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
            for row in c.execute("select tagid from tagstree where imageid = %s" % imageID):
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
            c.execute("select rating from images where imageid = %s" % imageID)
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
            c.execute("update images set rating='%s' where imageid='%s' and folderid='%s'" % (rating, imageID, folderID))
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
            for row in c.execute("select tagid, label, parentid, id from tags order by parentid, label;"):
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
            c.execute("delete from tagstree where imageid = %s" % (imageID))
            conn.commit()
        except AttributeError:
            raise Exception('NoConnection')
        try:
            for tagID in tagIDs:
                c.execute("insert into tagstree (imageid,tagid) values (%s, %s)" % (imageID, tagID))
            conn.commit()
            self.disconnect(conn)
        except AttributeError:
            raise Exception('NoConnection')
        return True
