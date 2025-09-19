import sqlite3
import json
import os
import copy
from shutil import move
from .Job import Job

class JobsDB:
    def __init__(self, db_path):
        self.db_path = db_path.replace('.json', '.sqlite')
        self.db_bak_path = f"{self.db_path}._bak"
        self.jobs = {}
        self.current_job = None
        self.conn = self._connect()
        self._create_table()
        self.load_all_jobs()

    def _connect(self):
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            raise Exception(f"Cannot connect to Jobs database: {e}")

    def _create_table(self):
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY,
            position INTEGER NOT NULL,
            state INTEGER,
            hashID INTEGER,
            srcDirName TEXT,
            srcFileName TEXT,
            srcFileExt TEXT,
            tgtDirName TEXT,
            tgtFileName TEXT,
            tgtFileExt TEXT,
            tgtFileCount INTEGER,
            tgtFileSep TEXT,
            sections TEXT,
            filters TEXT,
            filterPositions TEXT,
            renderSettings TEXT,
            log TEXT
        );
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(create_table_sql)
            self.conn.commit()
        except sqlite3.Error as e:
            raise Exception(f"Failed to create jobs table: {e}")

    def on_job_props_updated(self, job_id, props):
        """Callback, der bei jeder Änderung eines Job-Objekts aufgerufen wird."""
        if job_id == 'default' or not str(job_id).isdigit():
            return

        try:
            db_tuple = self._job_props_to_db_tuple(props)
            sql = """
                UPDATE jobs SET
                    position = ?, state = ?, hashID = ?, srcDirName = ?, srcFileName = ?,
                    srcFileExt = ?, tgtDirName = ?, tgtFileName = ?, tgtFileExt = ?,
                    tgtFileCount = ?, tgtFileSep = ?, sections = ?, filters = ?,
                    filterPositions = ?, renderSettings = ?, log = ?
                WHERE id = ?
            """
            cursor = self.conn.cursor()
            cursor.execute(sql, (*db_tuple, job_id))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"CRITICAL: Failed to update job {job_id} in database: {e}")

    def load_all_jobs(self):
        """Lädt alle Jobs aus der Datenbank in den Speicher."""
        self.jobs = {}
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM jobs ORDER BY position ASC")
            rows = cursor.fetchall()
            max_pos = 0
            for i, row in enumerate(rows):
                props = self._db_row_to_job_props(row)
                job_id = row['id']
                job = Job(str(job_id), props=props)

                if job.getPosition() != i:
                    job.setPosition(i)

                job.bindToProps(self.on_job_props_updated)
                self.jobs[str(job_id)] = job
                max_pos = i

            if any(j.getPosition() != i for i, j in enumerate(self.get_sorted_jobs())):
                 self.reindex_positions()

        except sqlite3.Error as e:
            raise Exception(f"Failed to load jobs from database: {e}")

    def get_sorted_jobs(self):
        """Gibt eine nach Position sortierte Liste von Job-Objekten zurück."""
        return sorted(self.jobs.values(), key=lambda j: j.getPosition())

    def reindex_positions(self):
        """Schreibt die Positionen aller Jobs neu, um Lücken zu füllen."""
        try:
            cursor = self.conn.cursor()
            sorted_jobs = self.get_sorted_jobs()
            for i, job in enumerate(sorted_jobs):
                if job.getPosition() != i:
                    job.setPosition(i)
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error re-indexing job positions: {e}")
            self.conn.rollback()

    def new_current_job(self, videoFilePath=False, job=False):
        """Erstellt einen neuen temporären 'default' Job."""
        if self.current_job:
            pass

        if videoFilePath and not job:
            new_job = Job('default', srcFilePath=videoFilePath)
        elif not videoFilePath and job:
            props = copy.deepcopy(job.getProps())
            new_job = Job('default', props=props)
            new_job.setLog(False)
        else:
            raise ValueError("Cannot create new job with conflicting parameters.")

        self.current_job = new_job

    def create_empty_current_job(self):
        """Erstellt einen leeren 'default' Job, um einen validen Startzustand zu garantieren."""
        self.current_job = Job('default')

    def get_current_job(self):
        return self.current_job

    def _get_next_job_id(self):
        if not self.jobs:
            return 1

        existing_ids = sorted([int(job_id) for job_id in self.jobs.keys()])

        expected_id = 1
        for eid in existing_ids:
            if eid != expected_id:
                return expected_id
            expected_id += 1

        return expected_id

    def save_current_job(self):
        if not self.current_job:
            return None

        job_to_save = copy.deepcopy(self.current_job)
        job_to_save.clearPropObservers()
        job_to_save.setState(0)

        new_id = self._get_next_job_id()
        job_to_save.setID(str(new_id))

        new_position = len(self.jobs)
        job_to_save.setPosition(new_position)

        props = job_to_save.getProps()
        db_tuple = self._job_props_to_db_tuple(props)

        sql = """
            INSERT INTO jobs (
                id, position, state, hashID, srcDirName, srcFileName, srcFileExt,
                tgtDirName, tgtFileName, tgtFileExt, tgtFileCount, tgtFileSep,
                sections, filters, filterPositions, renderSettings, log
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql, (new_id, *db_tuple))
            self.conn.commit()

            job_to_save.bindToProps(self.on_job_props_updated)
            self.jobs[str(new_id)] = job_to_save
            return job_to_save
        except sqlite3.Error as e:
            self.conn.rollback()
            raise Exception(f"Failed to save new job to database: {e}")

    def get_job(self, job_id):
        return self.jobs.get(str(job_id))

    def remove_job(self, job_id):
        job_id_str = str(job_id)
        if job_id_str not in self.jobs:
            return

        try:
            self.delete_deshake_file(job_id_str)

            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            self.conn.commit()

            del self.jobs[job_id_str]
            self.reindex_positions()
        except sqlite3.Error as e:
            self.conn.rollback()
            raise Exception(f"Failed to remove job {job_id} from database: {e}")

    def remove_jobs_by_state(self, state: int) -> list[str]:
        job_ids_to_remove = []
        try:
            cursor = self.conn.cursor()

            cursor.execute("SELECT id FROM jobs WHERE state = ?", (state,))
            rows = cursor.fetchall()
            job_ids_to_remove = [str(row['id']) for row in rows]

            if not job_ids_to_remove:
                return []

            for job_id in job_ids_to_remove:
                self.delete_deshake_file(job_id)

            cursor.execute("DELETE FROM jobs WHERE state = ?", (state,))
            self.conn.commit()

            for job_id in job_ids_to_remove:
                if job_id in self.jobs:
                    del self.jobs[job_id]

            self.reindex_positions()

            return job_ids_to_remove
        except sqlite3.Error as e:
            self.conn.rollback()
            raise Exception(f"Failed to remove jobs with state {state} from database: {e}")

    def swap_jobs(self, job1, job2):
        """Tauscht die Positionen von zwei Jobs in der Datenbank."""
        pos1 = job1.getPosition()
        pos2 = job2.getPosition()

        job1.unbindFromProps(self.on_job_props_updated)
        job2.unbindFromProps(self.on_job_props_updated)

        job1.setPosition(pos2)
        job2.setPosition(pos1)

        job1.bindToProps(self.on_job_props_updated)
        job2.bindToProps(self.on_job_props_updated)

        self.on_job_props_updated(job1.getID(), job1.getProps())
        self.on_job_props_updated(job2.getID(), job2.getProps())

    def reorder_jobs(self, job_ids_in_new_order: list[str]):
        try:
            cursor = self.conn.cursor()
            for new_pos, job_id in enumerate(job_ids_in_new_order):
                cursor.execute("UPDATE jobs SET position = ? WHERE id = ?", (new_pos, int(job_id)))
            self.conn.commit()

            self.load_all_jobs()
        except sqlite3.Error as e:
            self.conn.rollback()
            raise Exception(f"Failed to reorder jobs in database: {e}")

    def delete_deshake_file(self, job_id):
        job = self.get_job(job_id)
        if not job: return
        deshakeFile = job.getFilterDeshakeFile()
        if deshakeFile and os.path.isfile(deshakeFile):
            os.remove(deshakeFile)

    def _db_row_to_job_props(self, row):
        """Konvertiert eine sqlite3.Row in ein Job-Properties-Dictionary."""
        return {
            'position': row['position'],
            'state': row['state'],
            'hashID': row['hashID'],
            'srcFile': {
                'dirName': row['srcDirName'],
                'fileName': row['srcFileName'],
                'fileExt': row['srcFileExt'],
            },
            'tgtFile': {
                'dirName': row['tgtDirName'],
                'fileName': row['tgtFileName'],
                'fileExt': row['tgtFileExt'],
                'count': row['tgtFileCount'],
                'sep': row['tgtFileSep']
            },
            'sections': json.loads(row['sections'] or '[]'),
            'filters': json.loads(row['filters'] or '{}'),
            'filterPositions': json.loads(row['filterPositions'] or '{}'),
            'renderSettings': json.loads(row['renderSettings'] or '{}'),
            'log': row['log'],
        }

    def _job_props_to_db_tuple(self, props):
        """Konvertiert ein Job-Properties-Dictionary in ein Tupel für die DB."""
        return (
            props.get('position', 0),
            props.get('state', 0),
            props.get('hashID'),
            props['srcFile'].get('dirName'),
            props['srcFile'].get('fileName'),
            props['srcFile'].get('fileExt'),
            props['tgtFile'].get('dirName'),
            props['tgtFile'].get('fileName'),
            props['tgtFile'].get('fileExt'),
            props['tgtFile'].get('count'),
            props['tgtFile'].get('sep'),
            json.dumps(props.get('sections', [])),
            json.dumps(props.get('filters', {})),
            json.dumps(props.get('filterPositions', {})),
            json.dumps(props.get('renderSettings', {})),
            props.get('log')
        )

    def __del__(self):
        if self.conn:
            self.conn.close()
