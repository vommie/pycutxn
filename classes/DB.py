import sqlite3
import os

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
        conn.close()

    def getFolderID(self, path):
        if not path[:-1] == '/': path = '%s/' % path
        self.log(3, 'Get FolderID for path: "%s" ...' % path)
        conn = self.connect()
        c = conn.cursor()
        c.execute("select folderid from folders where pathname = '%s'" % path)
        conn.commit()
        folderID = c.fetchone()
        self.disconnect(conn)
        if folderID:
            folderID = folderID[0]
            folderID = int(folderID)
            self.log(3, 'FolderID found: %s' % folderID)
        else:
            self.log(3, 'No FolderID found')
            folderID = False
        return folderID

    def setFolderID(self):
        pass

    def getImageID(self, folderID, fileName):
        self.log(3, 'Get ImageID for folderID "%s" with file name "%s" ...' % (folderID, fileName))
        conn = self.connect()
        c = conn.cursor()
        c.execute("select imageid from images where folderid = %s and filename = '%s'" % (folderID, fileName))
        conn.commit()
        imageID = c.fetchone()
        self.disconnect(conn)
        if imageID:
            imageID = imageID[0]
            imageID = int(imageID)
            self.log(3, 'ImageID found: %s' % imageID)
        else:
            self.log(3, 'No ImageID found')
            imageID = False
        return imageID

    def setImageID(self, folderID):
        pass

    def getTagIDs(self, imageID):
        self.log(3, 'Get TagIDs for imageID: "%s" ...' % imageID)
        conn = self.connect()
        c = conn.cursor()
        tags = []
        for row in c.execute("select tagid from tagstree where imageid = %s" % imageID):
            tags.append(row[0])
        conn.commit()
        self.disconnect(conn)
        if tags: self.log(3, 'TagIDs found: %s' % tags)
        else: self.log(3, 'No TagIDs found')
        return tags

    def getRating(self, imageID):
        self.log(3, 'Get Rating for imageID: "%s" ...' % imageID)
        conn = self.connect()
        c = conn.cursor()
        c.execute("select rating from images where imageid = %s" % imageID)
        conn.commit()
        rating = c.fetchone()
        self.disconnect(conn)
        if rating:
            rating = rating[0]
            rating = int(rating)
            self.log(3, 'Rating found: %s' % rating)
        else:
            self.log(3, 'No Rating found')
            rating = False
        return rating

    def getCategoriesTree(self):
        self.log(3, 'Get TagTree ...')
        conn = self.connect()
        c = conn.cursor()
        tagTree = []
        for row in c.execute("select tagid, label, parentid, id from tags order by parentid, label;"):
            tagTree.append({'tagID': row[0], 'parentID': row[2], 'label': row[1]})
        conn.commit()
        self.disconnect(conn)
        self.log(3, 'TagTree found:\n%s' % tagTree)
        return tagTree
