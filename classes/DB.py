import sqlite3

class DB:

    def __init__(self, dbPath):
        conn = sqlite3.connect(dbPath)
