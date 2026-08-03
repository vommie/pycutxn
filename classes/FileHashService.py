import os
import re
import hashlib
import datetime
from PyQt6 import QtWidgets

class FileHashService:
    """
    Handles file hashing (MD5), sidecar .md5 file checking, and integration with
    the XnView SQLite database to identify previously edited duplicate files.
    """

    def __init__(self, db, hash_ui, logger, show_msg_box_fn, hash_file_ext='md5'):
        self.db = db
        self.hashUI = hash_ui
        self.log = logger
        self.showMsgBox = show_msg_box_fn
        self.hashFileExt = hash_file_ext

    def video_path_to_hash_path(self, file_path: str) -> str:
        """Generates the sidecar hash file path for a given video path."""
        return f"{os.path.dirname(file_path)}/.{os.path.basename(file_path)}.{self.hashFileExt}"

    def read_hash_from_file(self, file_path: str):
        """
        Reads a pre-computed MD5 hash from a sidecar .md5 file if present.

        :param file_path: Path to the video file
        :return: MD5 string if valid, False otherwise
        """
        hashFilePath = self.video_path_to_hash_path(file_path)
        self.log(1, f'Looking for hash file "{hashFilePath}" from "{file_path}"', 0)
        if os.path.exists(hashFilePath):
            self.log(1, f'Looking for hash in file "{hashFilePath}"', 0)
            try:
                with open(hashFilePath, 'r', encoding='utf-8') as f:
                    hashContent = f.read().strip()
                    if re.match(r'^[a-fA-F0-9]{32}$', hashContent):
                        self.log(1, f'Found hash for current file in "{hashFilePath}"', 0)
                        return hashContent
            except Exception as e:
                self.log(1, f'Could not read hash file "{hashFilePath}": {e}', 1)
        return False

    def hash_file(self, file_path_long: str):
        """
        Computes MD5 hash for a file. Shows a progress dialog for files larger than 200MB.

        :param file_path_long: Full path to the file
        :return: MD5 hexdigest string, None if cancelled by user, or False on error.
        """
        if not os.path.isfile(file_path_long):
            self.log(1, f"Hash target file not found: {file_path_long}", 1)
            return False

        BUF_SIZE = 65536
        md5 = hashlib.md5()
        fileSize = os.path.getsize(file_path_long)
        isBigFile = fileSize / 1024 / 1024 > 200

        if isBigFile and self.hashUI:
            self.hashUI.reset()
            self.hashUI.progressBar.setMaximum(int(fileSize / 1000))
            self.hashUI.show()

        cancelled = False
        try:
            with open(file_path_long, 'rb') as f:
                for chunk in iter(lambda: f.read(BUF_SIZE), b""):
                    if isBigFile and self.hashUI and self.hashUI.cancelled:
                        cancelled = True
                        break

                    md5.update(chunk)

                    if isBigFile and self.hashUI:
                        self.hashUI.progressBar.setValue(self.hashUI.progressBar.value() + int(len(chunk) / 1000))
                        QtWidgets.QApplication.processEvents()
        except (IOError, OSError) as e:
            self.log(1, f"Error reading file for hashing: {e}", 1)
            if isBigFile and self.hashUI:
                self.hashUI.close()
            return False

        if isBigFile and self.hashUI:
            self.hashUI.close()

        if cancelled:
            return None

        return md5.hexdigest()

    def is_job_file_known(self, job):
        """
        Checks if a job's source file has been processed in PyCutXn previously.
        Sets the job's HashID and returns hash metadata.

        :param job: Job instance
        :return: Tuple of (hashID, dateTime) if known, else (False, False)
        """
        src_path = job.getSrcFilePathLong()

        hash_val = self.read_hash_from_file(src_path)
        if not hash_val:
            hash_val = self.hash_file(src_path)

        if hash_val is None:
            self.log(1, "Hashing was cancelled by the user.")
            job.setHashID(f"cancelled_{datetime.datetime.now().timestamp()}")
            return False, False

        if hash_val is False:
            msg = 'Error: The source file cannot be hashed.'
            self.log(1, msg, 1)
            if self.showMsgBox:
                self.showMsgBox(msg, infoText='It is not known if this file was not edited in the past with PyCutXn.', icon='warning')
            return False, False

        try:
            hashID, dateTime = self.db.getHashData(hash_val)
            if not hashID:
                self.db.insertHash(hash_val)
                hashID, dateTime = self.db.getHashData(hash_val)
                if not hashID:
                    msg = 'Error: Got no hashID for a hash inserted to the database.'
                    self.log(1, msg, 1)
                    if self.showMsgBox:
                        self.showMsgBox(msg, icon='warning')
                else:
                    job.setHashID(hashID)
                return False, False
            job.setHashID(hashID)
            return hashID, dateTime
        except Exception as e:
            msg = 'Error on checking for hash info in the database.'
            self.log(1, msg, 1)
            if self.showMsgBox:
                self.showMsgBox(msg, btns="ok", icon="warning", detailText=str(e))
            return False, False

    def get_file_list_from_job(self, job):
        """
        Retrieves all files from the XnView DB sharing the same hashID as the given job.

        :param job: Job instance
        :return: List of file paths
        """
        hashID = job.getHashID()
        if not hashID:
            return []
        return self.get_file_list_by_hash_id(hashID)

    def get_file_list_by_hash_id(self, hash_id):
        """Retrieves list of file paths from DB associated with a hashID."""
        if not hash_id or not self.db:
            return []
        try:
            filePaths = self.db.getFileListByHashID(hash_id)
            return filePaths if filePaths else []
        except Exception as e:
            self.log(1, f"Error getting file list by HashID '{hash_id}': {e}", 1)
            return []
