from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QDialog, QListWidgetItem
from PyQt5.QtGui import QFont, QPalette
import copy
import traceback
from collections import defaultdict

class EditDBUI(QDialog):
    def __init__(self, parent, job):
        super(EditDBUI, self).__init__(parent)
        self.parent = parent
        self.job = job
        uic.loadUi('%s/gui/edit_db.ui' % self.parent.rootDir, self)

        # Deep copy tagsTree to avoid side effects on main window's data
        self.tagsTree = [{k: v for k, v in tag.items() if k != 'item'} for tag in self.parent.tagsTree]
        self.tagsTreeSpaceChar = ' '

        self._tags_by_parent = defaultdict(list)
        for i, tag in enumerate(self.tagsTree):
            self._tags_by_parent[tag['parentID']].append(i)

        self.initGuiEvents()
        self.setTagsTreeStyle()
        self.loadData()
        self.setWindowTitle(f"Edit DB: {job.getTgtFileNameLong()}")

    def initGuiEvents(self):
        self.buttonBox.accepted.connect(self.onAccepted)

    def loadData(self):
        self._build_tags_tree_recursive(-1, '')

        job = self.job
        db = self.parent.db

        folderID = db.getFolderID(job.getTgtDirName())
        if not folderID:
            self.parent.log(3, f"Folder not found in DB for job {job.getID()}, cannot load existing data: {job.getTgtDirName()}")
            return

        imageID = db.getImageID(folderID, job.getTgtFileNameLong())
        if not imageID:
            self.parent.log(3, f"Image not found in DB for job {job.getID()}, cannot load existing data: {job.getTgtFileNameLong()}")
            return

        rating = db.getRating(imageID)
        self.setBtnRating(rating or 0)
        tagIDs = db.getTagIDs(imageID)
        self.selectTagsInTagsTree(tagIDs)

    def onAccepted(self):
        job = self.job
        db = self.parent.db

        try:
            folderID = db.getFolderID(job.getTgtDirName())
            if not folderID:
                self.parent.log(3, f"Inserting new path to DB: {job.getTgtDirName()}")
                folderID = db.insertPath(job.getTgtDirName())
            if not folderID:
                raise Exception("Could not get or create FolderID.")

            imageID = db.getImageID(folderID, job.getTgtFileNameLong())
            if not imageID:
                self.parent.log(3, f"Inserting new image to DB: {job.getTgtFileNameLong()}")
                imageID = db.insertImage(folderID, job.getTgtFileNameLong())
            if not imageID:
                raise Exception("Could not get or create ImageID.")

            rating = self.getRatingFromBtns()
            tagIDs = self.getSelectedTagIDsFromTagsTree()
            hashID = job.getHashID()

            if hashID: db.setHashID(imageID, folderID, hashID)
            db.setRating(imageID, folderID, rating)
            db.setTags(imageID, tagIDs)

            self.parent.log(1, f"DB entry for Job {job.getID()} ({job.getTgtFileNameLong()}) updated successfully.")

        except Exception as e:
            msg = 'Error updating DB entry.'
            self.parent.log(1, msg, 1, traceback=traceback.format_exc())
            self.parent.showMsgBox(msg, detailText=str(e), icon='critical')

    def _build_tags_tree_recursive(self, parent_id, prefix):
        child_indices = self._tags_by_parent.get(parent_id, [])

        for i in child_indices:
            tag = self.tagsTree[i]
            item = QListWidgetItem(f'{prefix}{tag["label"]}')
            item.setToolTip(f'TagID: {tag["tagID"]}')

            fontWeight = QFont.Bold if tag['parentID'] == -1 else -1
            item.setFont(QFont('Noto Sans', 8, weight=fontWeight))

            self.listWidgetTagsTree.addItem(item)
            item.setHidden(self.parent.tagOrParentTagsHaveFilter(tag))

            self.tagsTree[i]['item'] = item

            self._build_tags_tree_recursive(tag['tagID'], f'{prefix}{self.tagsTreeSpaceChar}')

    def getSelectedTagIDsFromTagsTree(self):
        tagIDs = []
        for tag in self.tagsTree:
            try:
                if 'item' in tag and tag['item'].isSelected():
                    tagIDs.append(tag['tagID'])
            except Exception:
                continue
        return tagIDs

    def getRatingFromBtns(self):
        if self.radioButton_rate1.isChecked(): return 1
        if self.radioButton_rate2.isChecked(): return 2
        if self.radioButton_rate3.isChecked(): return 3
        if self.radioButton_rate4.isChecked(): return 4
        if self.radioButton_rate5.isChecked(): return 5
        return 0

    def selectTagsInTagsTree(self, tagIDs, clearSelection=True):
        if clearSelection:
            self.listWidgetTagsTree.clearSelection()

        for tag in self.tagsTree:
            if 'item' in tag and tag['tagID'] in tagIDs:
                tag['item'].setSelected(True)

    def setBtnRating(self, rating):
        try: rating = int(rating)
        except: return
        if rating == 1: self.radioButton_rate1.setChecked(True)
        elif rating == 2: self.radioButton_rate2.setChecked(True)
        elif rating == 3: self.radioButton_rate3.setChecked(True)
        elif rating == 4: self.radioButton_rate4.setChecked(True)
        elif rating == 5: self.radioButton_rate5.setChecked(True)
        else: self.radioButton_rate0.setChecked(True)

    def setTagsTreeStyle(self):
        self.listWidgetTagsTree.setStyleSheet("""
            QListWidget::item {
                border-style: solid;
                border-width: 1px;
                border-color: """ + str(QPalette().color(QPalette.ToolTipBase).name()) + """;
                background-color: """ + str(QPalette().color(QPalette.Base).name()) + """;
                margin: 0;
                padding: 0;
                line-height: 0;
                height: 12px;
                max-height: 12px;
            }
            QListWidget::item:selected {
                background-color: #7f7f7f;
            }
            QListWidget::item:hover {
                color: #333333;
                background-color: #bbbbbb;
            }
        """)
