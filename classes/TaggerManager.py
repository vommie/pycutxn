from PyQt6.QtWidgets import QListWidgetItem
from PyQt6.QtGui import QFont, QPalette
from classes.Functions import Functions

class TaggerManager:
    """
    Manages metadata tagging, star ratings, XnView SQLite database synchronization,
    recursive tag tree rendering, tag filters, and tag/rating history mode.
    """

    def __init__(self, parent_widget, config, db, jobs_db, rating_ui, logger, show_msg_box_fn,
                 dock_tagger, label_tagger_error, list_widget_tags_tree, list_widget_last_tags,
                 btn_last_rating, btn_tagger_active, btn_tagger_warning, btn_tagger_filter,
                 rate_radio_btns, widget_history_ctrl, widget_edit_ctrl, btn_export_save):

        self.parent = parent_widget
        self.config = config
        self.db = db
        self.jobs = jobs_db
        self.ratingUI = rating_ui
        self.log = logger
        self.showMsgBox = show_msg_box_fn

        self.dockTagger = dock_tagger
        self.labelTaggerError = label_tagger_error
        self.listWidgetTagsTree = list_widget_tags_tree
        self.listWidgetLastTags = list_widget_last_tags
        self.btnLastRating = btn_last_rating
        self.btnTaggerActive = btn_tagger_active
        self.btnTaggerWarning = btn_tagger_warning
        self.btnTaggerFilter = btn_tagger_filter

        self.radioButton_rate0 = rate_radio_btns.get(0)
        self.radioButton_rate1 = rate_radio_btns.get(1)
        self.radioButton_rate2 = rate_radio_btns.get(2)
        self.radioButton_rate3 = rate_radio_btns.get(3)
        self.radioButton_rate4 = rate_radio_btns.get(4)
        self.radioButton_rate5 = rate_radio_btns.get(5)

        self.widgetTagRateHistoryCtrl = widget_history_ctrl
        self.widgetTagRateEditCtrl = widget_edit_ctrl
        self.btnExportSave = btn_export_save

        self.tagsTree = []
        self.lastTagIDs = []
        self.historyMode = False
        self.tagsTreeItemPrefix = ''
        self.tagsTreeSpaceChar = ' '
        self.toolTipBtnExportSave = self.btnExportSave.toolTip() if self.btnExportSave else ''

    def init_tagger(self):
        self.set_tags_tree_style()
        self.set_history_mode(False)
        self.btnTaggerActive.setChecked(self.config.getTaggerIsActive())
        self.btnTaggerWarning.setChecked(self.config.getTaggerIsWarningActive())

    def build_tags_tree(self, currTagID: int = -1):
        """
        Fills the TagsTree widget with tags of member variable 'tagsTree'.
        Recursive function starting with currTagID = -1.
        """
        if currTagID == -1:
            self.tagsTreeItemPrefix = ''
            self.listWidgetTagsTree.clear()

        if currTagID != -1:
            self.tagsTreeItemPrefix = '%s%s' % (self.tagsTreeSpaceChar, self.tagsTreeItemPrefix)

        for i, tag in enumerate(self.tagsTree):
            if tag['parentID'] == currTagID:
                item = QListWidgetItem('%s%s' % (self.tagsTreeItemPrefix, tag['label']))
                item.setToolTip('TagID: %s' % tag['tagID'])
                fontWeight = -1
                if tag['parentID'] == -1:
                    fontWeight = QFont.Weight.Bold.value
                item.setFont(QFont('Noto Sans', 8, weight=fontWeight))
                self.listWidgetTagsTree.addItem(item)
                item.setHidden(self.tag_or_parent_tags_have_filter(tag))
                self.build_tags_tree(tag['tagID'])
                self.tagsTree[i]['item'] = item

        self.tagsTreeItemPrefix = self.tagsTreeItemPrefix[0:-1]

    def tag_or_parent_tags_have_filter(self, currTag: dict, setFilter: bool = False) -> bool:
        """Checks if the given tag or any parent tag has an active filter."""
        if setFilter:
            return True
        if 'filter' in currTag and currTag['filter']:
            return True
        else:
            for tag in self.tagsTree:
                if tag['tagID'] == currTag['parentID']:
                    return self.tag_or_parent_tags_have_filter(tag, setFilter)
        return setFilter

    def set_tags_and_rating_to_tree(self, forSource: bool = True) -> bool:
        """Sets tags and rating for source or target file into UI tree and rating panel."""
        if not self.is_tagger_enabled():
            return False

        job = self.jobs.get_current_job()
        if not job:
            return False

        try:
            if forSource:
                folderID = self.db.getFolderID(job.getSrcDirName())
            else:
                folderID = self.db.getFolderID(job.getTgtDirName())

            if not folderID:
                return False

            if forSource:
                imageID = self.db.getImageID(folderID, job.getSrcFileNameLong())
            else:
                imageID = self.db.getImageID(folderID, job.getTgtFileNameLong())

            if not imageID:
                if forSource:
                    return False
                imageID = self.db.insertImage(folderID, job.getTgtFileNameLong(), job.getHashID())
                if not imageID:
                    msg = 'Error: Cannot create ImageID for file.'
                    self.log(1, msg, 1)
                    if self.showMsgBox:
                        self.showMsgBox(msg, btns="ok", icon="critical")
                    return False

            rating = self.db.getRating(imageID)
            if rating:
                self.set_btn_rating(rating)
            else:
                self.set_btn_rating(0)

            tagIDs = self.db.getTagIDs(imageID)
            self.select_tags_in_tags_tree(tagIDs)
        except Exception as e:
            self.disable_tagger_panel()
            msg = 'Error on setting Tags and Rating to the Tagger Panel.'
            self.log(1, msg, 1)
            if self.showMsgBox:
                self.showMsgBox(msg, btns="ok", icon="warning", detailText=str(e))
            return False

        return True

    def warn_when_no_tags_or_rating(self) -> bool:
        """Displays a warning if no tags or rating are set."""
        if self.is_tagger_warning_active():
            tagIDs = self.get_selected_tag_ids_from_tags_tree()
            rating = self.get_rating_from_btns()
            if not tagIDs and not rating:
                if self.showMsgBox and not self.showMsgBox('No rating and no tags are set.', btns='yesno', icon='question', infoText='Save anyways?'):
                    return False
            elif not tagIDs:
                if self.showMsgBox and not self.showMsgBox('No tags are set.', btns='yesno', icon='question', infoText='Save anyways?'):
                    return False
            elif not rating and self.ratingUI:
                rating = self.ratingUI.customExec()
                self.set_btn_rating(rating)
        return True

    def save_current_tags_and_rating(self, video_props: dict = None) -> bool:
        """Saves current tags and rating for target file to XnView SQLite DB."""
        if not self.is_tagger_enabled():
            return False

        self.log(1, 'Save Tags and Rating to DB ...')
        job = self.jobs.get_current_job()
        if not job:
            return False

        try:
            folderID = self.db.getFolderID(job.getTgtDirName())
            if not folderID:
                folderID = self.db.insertPath(job.getTgtDirName())
            if not folderID:
                msg = 'Error: Got no folderID. Cannot save tags and rating.'
                self.log(1, msg, 1)
                if self.showMsgBox:
                    self.showMsgBox(msg, btns='ok', icon='warning')
                return False

            imageID = self.db.getImageID(folderID, job.getTgtFileNameLong())
            if not imageID:
                imageID = self.db.insertImage(folderID, job.getTgtFileNameLong())
            if not imageID:
                msg = 'Error: Got no imageID. Cannot save tags and rating.'
                self.log(1, msg, 1)
                if self.showMsgBox:
                    self.showMsgBox(msg, btns='ok', icon='warning')
                return False
        except Exception as e:
            msg = 'Error when saving Tags and Rating to database'
            self.log(1, '%s: %s' % (msg, e), 1)
            if self.showMsgBox:
                self.showMsgBox('%s.' % msg, btns='ok', icon='warning', detailText=str(e))
            self.disable_tagger_panel()
            return False

        hashID = job.getHashID()
        rating = self.get_rating_from_btns()
        tagIDs = self.get_selected_tag_ids_from_tags_tree()

        try:
            self.log(1, 'Save hashID to database ...')
            self.db.setHashID(imageID, folderID, hashID)
            self.log(1, 'HashID saved: %s' % hashID)
            self.log(1, 'Save rating to database ...')
            self.db.setRating(imageID, folderID, rating)
            self.log(1, 'Rating saved: %s' % rating)
            self.log(1, 'Save tags to database ...')
            self.db.setTags(imageID, tagIDs)
            self.log(1, 'Tags saved: %s' % tagIDs)
            self.log(1, 'Save ImagesInfo to database ...')
            images_info = Functions.calculateJobImagesInfo(job, video_props)
            self.db.setImagesInfo(imageID, images_info)
            self.log(1, 'ImagesInfo saved: %s' % images_info)
        except Exception:
            msg = 'Error: No database connection possible'
            self.log(1, msg, 1)
            if self.showMsgBox:
                self.showMsgBox(msg, btns='ok', icon="warning")
            self.disable_tagger_panel()
            return False

        self.insert_tags_in_last_tags_list(tagIDs)
        self.set_last_rating(rating)
        self.clear_rating()
        self.clear_tags_tree()
        return True

    def get_selected_tag_ids_from_tags_tree(self) -> list:
        tagIDs = []
        for i, tag in enumerate(self.tagsTree):
            try:
                item = tag['item']
                if item.isSelected():
                    tagIDs.append(tag['tagID'])
            except Exception as e:
                msg = 'Error: Cannot get the selection state for a tags tree item.'
                self.log(1, msg, 1)
                if self.showMsgBox:
                    self.showMsgBox(msg, infoText='This could mean this Tag will not be set to the database', detailText=str(e), icon="warning")
                continue
        return tagIDs

    def get_rating_from_btns(self) -> int:
        if self.radioButton_rate0 and self.radioButton_rate0.isChecked():
            return 0
        if self.radioButton_rate1 and self.radioButton_rate1.isChecked():
            return 1
        if self.radioButton_rate2 and self.radioButton_rate2.isChecked():
            return 2
        if self.radioButton_rate3 and self.radioButton_rate3.isChecked():
            return 3
        if self.radioButton_rate4 and self.radioButton_rate4.isChecked():
            return 4
        if self.radioButton_rate5 and self.radioButton_rate5.isChecked():
            return 5
        return 0

    def select_tags_in_tags_tree(self, tagIDs: list, clearSelection: bool = True):
        if clearSelection or not tagIDs:
            self.log(1, 'Clear tags ...')
            for i in range(self.listWidgetTagsTree.count()):
                self.listWidgetTagsTree.item(i).setSelected(False)

        selected = []
        hiddenTags = []
        for tagID in tagIDs:
            for tag in self.tagsTree:
                if str(tag['tagID']) == str(tagID) or tag['tagID'] == tagID:
                    if 'item' in tag and tag['item']:
                        tag['item'].setSelected(True)
                        if 'filter' in tag and tag['filter']:
                            hiddenTags.append('"%s" (TagID "%s")' % (tag['label'], tag['tagID']))
                        selected.append(tag['item'].text().replace(self.tagsTreeSpaceChar, ''))

        if tagIDs:
            self.log(1, 'Selecting tags: %s' % ', '.join(selected))
        if hiddenTags:
            msg = 'Warning: Tags were loaded from job which are hidden in the Tags Tree.'
            self.log(1, msg, 1)
            if self.showMsgBox:
                self.showMsgBox(msg, detailText='%s' % '\n'.join(hiddenTags))

    def insert_tags_in_last_tags_list(self, tagIDs: list, clearTags: bool = True):
        if clearTags:
            self.listWidgetLastTags.clear()

        self.lastTagIDs = tagIDs
        for tagID in tagIDs:
            for tag in self.tagsTree:
                if str(tag['tagID']) == str(tagID) or tag['tagID'] == tagID:
                    item = QListWidgetItem(tag['label'])
                    item.setData(100, tag['tagID'])
                    self.listWidgetLastTags.addItem(item)

    def update_tags_filter(self, tagIDs: list):
        for tag in self.tagsTree:
            if tag['tagID'] in tagIDs:
                tag['filter'] = True
                if 'item' in tag and tag['item']:
                    tag['item'].setHidden(self.tag_or_parent_tags_have_filter(tag))
                    tag['item'].setSelected(False)
            else:
                tag['filter'] = False
                if 'item' in tag and tag['item']:
                    tag['item'].setHidden(self.tag_or_parent_tags_have_filter(tag))

    def set_last_rating(self, rating: int):
        self.btnLastRating.setText(str(rating))

    def set_btn_rating(self, rating: int):
        self.log(1, 'Selecting rating: %s' % rating)
        try:
            rating = int(rating)
        except Exception:
            self.log(1, 'Error: Rating is no number convertable to an integer.')
            return False

        if rating == 0 and self.radioButton_rate0:
            self.radioButton_rate0.setChecked(True)
        elif rating == 1 and self.radioButton_rate1:
            self.radioButton_rate1.setChecked(True)
        elif rating == 2 and self.radioButton_rate2:
            self.radioButton_rate2.setChecked(True)
        elif rating == 3 and self.radioButton_rate3:
            self.radioButton_rate3.setChecked(True)
        elif rating == 4 and self.radioButton_rate4:
            self.radioButton_rate4.setChecked(True)
        elif rating == 5 and self.radioButton_rate5:
            self.radioButton_rate5.setChecked(True)
        else:
            self.log(1, 'Error: Cannot set rating to value "%s"' % rating)

    def disable_tagger_panel(self):
        if not self.is_tagger_enabled():
            return
        if self.showMsgBox:
            self.showMsgBox('Tagger got disabled as there was no succesful database connection possible.', btns="ok", icon="warning")
        self.dockTagger.setEnabled(False)
        self.empty_tags_tree()
        self.clear_rating()
        self.labelTaggerError.setHidden(False)
        self.set_history_mode(False)

    def enable_tagger_panel(self):
        if not self.tagsTree:
            try:
                tagsTree = self.db.getTagsTree()
            except Exception:
                return False
            self.tagsTree = self.set_filter_state_for_tags_tree(tagsTree)
            self.build_tags_tree(-1)

        self.set_tags_tree_style()
        self.labelTaggerError.setHidden(True)
        self.dockTagger.setEnabled(True)

    def set_filter_state_for_tags_tree(self, tagsTree: list) -> list:
        filterTagIDs = self.config.getTaggerFilterTagIDs()
        for i in range(len(tagsTree)):
            tag = tagsTree[i]
            if tag['tagID'] in filterTagIDs:
                tagsTree[i]['filter'] = True
            else:
                tagsTree[i]['filter'] = False
        return tagsTree

    def check_db_connectivity(self):
        if self.db.testConnection():
            self.db.createHashTable()
            self.enable_tagger_panel()
        else:
            self.disable_tagger_panel()

    def is_tagger_enabled(self) -> bool:
        return self.dockTagger.isEnabled() if self.dockTagger else False

    def is_tagger_warning_active(self) -> bool:
        return self.btnTaggerWarning.isChecked() if self.btnTaggerWarning else False

    def empty_tags_tree(self):
        self.tagsTree = []
        self.listWidgetTagsTree.clear()

    def clear_tags_tree(self):
        self.select_tags_in_tags_tree([])

    def clear_last_tags_list(self):
        self.insert_tags_in_last_tags_list([])

    def clear_rating(self):
        self.set_btn_rating(0)

    def set_history_mode(self, state: bool, update_btn_export_state_fn=None):
        if state and self.is_tagger_enabled():
            self.log(1, 'Activate Tags and Rating History Mode.')
            self.historyMode = True
            self.widgetTagRateHistoryCtrl.setVisible(True)
            self.widgetTagRateEditCtrl.setVisible(False)
            if self.btnExportSave:
                self.btnExportSave.setToolTip('Cannot save while Tags & Rating is in History Mode. Save current Tags & Rating first.')
        elif not state and self.is_tagger_enabled():
            self.log(1, 'Disable Tags and Rating History Mode.')
            self.historyMode = False
            self.widgetTagRateHistoryCtrl.setVisible(False)
            self.widgetTagRateEditCtrl.setVisible(True)
            if self.btnExportSave:
                self.btnExportSave.setToolTip(self.toolTipBtnExportSave)
        else:
            self.widgetTagRateHistoryCtrl.setVisible(False)
            self.widgetTagRateEditCtrl.setVisible(True)
            self.historyMode = False

        if update_btn_export_state_fn:
            update_btn_export_state_fn()

    def set_tags_tree_style(self):
        self.listWidgetTagsTree.setStyleSheet("""
            QListWidget::item {
                border-style: solid;
                border-width: 1px;
                border-color: """ + str(QPalette().color(QPalette.ColorRole.ToolTipBase).name()) + """;
                background-color: """ + str(QPalette().color(QPalette.ColorRole.Base).name()) + """;
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

    def on_btn_tag_rate_history_save_clicked(self, video_props=None, update_btn_export_state_fn=None):
        if self.save_current_tags_and_rating(video_props):
            self.set_history_mode(False, update_btn_export_state_fn)

    def on_list_widget_last_tags_item_clicked(self, item):
        if item:
            tagID = item.data(100)
            self.select_tags_in_tags_tree([tagID], clearSelection=False)
            item.setSelected(False)

    def on_btn_tags_last_clicked(self):
        self.select_tags_in_tags_tree(self.lastTagIDs, clearSelection=False)

    def on_btn_tags_clear_clicked(self):
        self.clear_tags_tree()

    def on_btn_last_rating_clicked(self):
        if self.btnLastRating:
            self.set_btn_rating(int(self.btnLastRating.text()))

    def on_btn_tagger_active_clicked(self):
        if self.btnTaggerActive:
            self.config.setTaggerIsActive(not self.config.getTaggerIsActive())

    def on_btn_tagger_warning_clicked(self):
        if self.btnTaggerWarning:
            self.config.setTaggerIsWarningActive(not self.config.getTaggerIsWarningActive())
