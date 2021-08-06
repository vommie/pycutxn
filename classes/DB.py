import sqlite3
import os

class DB:

    def __init__(self, dbPath):
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
        conn = self.connect()
        c = conn.cursor()
        c.execute("select folderid from folders where pathname = '%s'" % path)
        conn.commit()
        print(c.fetchone())
        self.disconnect(conn)

    def setFolderID(self):
        pass

    def getImageID(self):
        pass

    def setImageID(self, folder_id):
        pass

    def getFileCategories(self, image_id):
        pass

    def getFileRating(self, image_id):
        pass

    def getCategoriesTree(self):
        conn = self.connect()
        c = conn.cursor()
        tagTree = []
        for row in c.execute("select tagid, label, parentid, id from tags order by parentid, label;"):
            # tagTree.update({row[0]: {'parentID': row[2], 'label': row[1]}})
            tagTree.append({'tagID': row[0], 'parentID': row[2], 'label': row[1]})
        conn.commit()
        self.disconnect(conn)
        return tagTree
