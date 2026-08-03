import os
import subprocess
import traceback
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import QTableWidgetItem, QMenu
from PyQt6.QtGui import QAction

from classes.FFmpegThread import FFmpegThread
from classes.Functions import Functions

class QueueManager(QtCore.QObject):
    """
    Manages the job queue table, single/multi-selection reordering, context menus,
    FFmpegThread rendering orchestration, progress monitoring, and state transitions.
    Inherits from QObject to allow thread-safe Qt Signal/Slot routing.
    """

    def __init__(self, parent_widget, config, jobs_db, logger, file_hash_service, power_manager,
                 log_ui, show_msg_box_fn, table_queue, btn_queue_up, btn_queue_down,
                 btn_queue_pause, btn_queue_kill, btn_queue_load, btn_queue_delete,
                 btn_queue_delete_all, progress_bar_render, widget_render_details,
                 label_fps, label_speed, label_size, label_time,
                 actions, is_same_render_fn, is_sections_missing_fn, edit_db_entry_cb):
        super().__init__()

        self.parent = parent_widget
        self.config = config
        self.jobs = jobs_db
        self.log = logger
        self.fileHashService = file_hash_service
        self.powerManager = power_manager
        self.logUi = log_ui
        self.showMsgBox = show_msg_box_fn

        self.tableQueue = table_queue
        self.btnQueueUp = btn_queue_up
        self.btnQueueDown = btn_queue_down
        self.btnQueuePause = btn_queue_pause
        self.btnQueueKill = btn_queue_kill
        self.btnQueueLoad = btn_queue_load
        self.btnQueueDelete = btn_queue_delete
        self.btnQueueDeleteAll = btn_queue_delete_all

        self.progressBarRender = progress_bar_render
        self.widgetRenderDetails = widget_render_details
        self.labelRenderFPS = label_fps
        self.labelRenderSpeed = label_speed
        self.labelRenderSize = label_size
        self.labelRenderTime = label_time

        self.actionPlayFile = actions.get('play')
        self.actionOpenFolder = actions.get('open_folder')
        self.actionShowLog = actions.get('show_log')
        self.actionStatePostpone = actions.get('postpone')
        self.actionStateResume = actions.get('resume')
        self.actionStateReset = actions.get('reset')
        self.actionStateCancel = actions.get('cancel')
        self.actionMoveTop = actions.get('move_top')
        self.actionMoveBottom = actions.get('move_bottom')
        self.actionEditDBEntry = actions.get('edit_db')

        self.isSameRenderSrcTgt = is_same_render_fn
        self.isSectionsMissing = is_sections_missing_fn
        self.editDBEntryCallback = edit_db_entry_cb

        self.jobStates = {
            0: 'Waiting',
            1: 'Finished',
            2: 'Pending',
            3: 'Error',
            4: 'Rendering',
            5: 'Paused',
            6: 'Aborted'
        }

        self.ffmpegProcess = False
        self.ffmpegKilled = False
        self.jobsSwapping = False
        self.FFmpegThread = None
        self.timeFormat = '0:00:00.000'

    def get_job_state_string(self, state: int) -> str:
        return self.jobStates.get(state, 'Unknown')

    def job_state_str_to_id(self, stateStr: str):
        if not stateStr:
            return False
        stateStrLower = stateStr.lower()
        for key, state in self.jobStates.items():
            if state.lower() == stateStrLower:
                return key
        return False

    def queue_add_row(self, job_id, filename: str, state: str) -> int:
        iRow = self.tableQueue.rowCount()
        self.tableQueue.insertRow(iRow)
        itemID = QTableWidgetItem(str(job_id))
        itemFilename = QTableWidgetItem(filename)
        itemFilename.setToolTip(filename)
        itemState = QTableWidgetItem(state)
        self.tableQueue.setItem(iRow, 0, itemID)
        self.tableQueue.setItem(iRow, 1, itemFilename)
        self.tableQueue.setItem(iRow, 2, itemState)
        self.tableQueue.scrollToBottom()
        return iRow

    def queue_delete_selected_rows(self):
        selected_rows = self.tableQueue.selectionModel().selectedRows()
        if not selected_rows:
            return

        jobs_to_delete = []
        rows_to_delete = []

        for index in sorted(selected_rows, key=lambda i: i.row(), reverse=True):
            row = index.row()
            jobID, _ = self.queue_get_job_id_from_row(row)
            job = self.jobs.get_job(jobID)
            if job and job.getState() == 4:
                if self.showMsgBox:
                    self.showMsgBox(
                        f'Cannot delete job {jobID} while it is rendering.',
                        infoText='Abort the job first, then delete it.',
                        icon='warning'
                    )
                continue
            if job:
                jobs_to_delete.append(job)
                rows_to_delete.append(row)

        if not jobs_to_delete:
            return

        for job in jobs_to_delete:
            self.log(1, 'Remove Job with ID %s' % job.getID())
            self.jobs.remove_job(job.getID())

        for row in rows_to_delete:
            self.tableQueue.removeRow(row)

        self.set_btn_queue_delete_all_state()
        self.set_queue_btn_states()

    def queue_remove_row_by_job(self, job) -> bool:
        try:
            jobID = str(job.getID())
            for iRow in range(self.tableQueue.rowCount()):
                item = self.tableQueue.item(iRow, 0)
                if not item or not item.text() == jobID:
                    continue
                if job.getState() == 4:
                    if self.showMsgBox:
                        self.showMsgBox(
                            'One of the jobs is currently rendering and is not removed.',
                            infoText='Abort the job manually, then delete it.',
                            icon='warning'
                        )
                    return False
                self.jobs.remove_job(jobID)
                self.tableQueue.removeRow(iRow)
                self.set_btn_queue_delete_all_state()
                self.set_queue_btn_states()
                if iRow > 0:
                    self.tableQueue.setCurrentCell(iRow - 1, 0)
                self.log(1, 'Removed job with ID "%s" from jobs queue.' % jobID)
                return True
        except Exception as e:
            msg = 'Error: Cannot remove job queue row or job.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            if self.showMsgBox:
                self.showMsgBox(msg, btns="ok", icon="warning", detailText=traceback.format_exc())
            return False

    def queue_remove_finished_rows(self):
        try:
            finished_jobs = [job for job in self.jobs.get_sorted_jobs() if job.getState() == 1]

            if not finished_jobs:
                self.log(1, "No finished jobs found to remove.")
                return

            self.log(1, f"Found {len(finished_jobs)} finished jobs to remove. Processing related files...")

            for job in finished_jobs:
                srcPath = job.getSrcFilePathLong()
                if self.fileHashService:
                    hashFilePath = self.fileHashService.video_path_to_hash_path(srcPath)
                    if os.path.isfile(hashFilePath):
                        os.remove(hashFilePath)
                        self.log(1, f"Removed hash file: {hashFilePath}", 0)

            deleted_ids = self.jobs.remove_jobs_by_state(1)

            if not deleted_ids:
                self.log(1, "JobsDB reported no jobs were deleted, skipping GUI update.")
                return

            self.log(1, f"Bulk removed {len(deleted_ids)} jobs from the database. Updating GUI...")

            for iRow in reversed(range(self.tableQueue.rowCount())):
                jobID_in_table = self.tableQueue.item(iRow, 0).text()
                if jobID_in_table in deleted_ids:
                    self.tableQueue.removeRow(iRow)
            self.log(1, "Queue GUI updated successfully.")

        except Exception as e:
            msg = 'Error: Cannot remove all finished jobs in queue.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            if self.showMsgBox:
                self.showMsgBox(msg, btns="ok", icon="warning", detailText=traceback.format_exc())
            return

        self.set_btn_queue_delete_all_state()
        if self.tableQueue.rowCount() > 0:
            self.tableQueue.setCurrentCell(self.tableQueue.rowCount() - 1, 0)
        self.set_queue_btn_states()

    def get_selected_jobs(self) -> list:
        selected_jobs = []
        selected_rows = self.tableQueue.selectionModel().selectedRows()
        for index in selected_rows:
            job_id, _ = self.queue_get_job_id_from_row(index.row())
            job = self.jobs.get_job(job_id)
            if job:
                selected_jobs.append(job)
        return selected_jobs

    def queue_get_job_id_from_row(self, iRow: int = None):
        if iRow is None:
            iRow = self.tableQueue.currentRow()
        itemID = self.tableQueue.item(iRow, 0)
        jobID = itemID.text() if itemID else ''
        return jobID, iRow

    def queue_get_current_state(self, iRow: int = None) -> int:
        if iRow is None:
            iRow = self.tableQueue.currentRow()
        itemState = self.tableQueue.item(iRow, 2)
        stateStr = itemState.text() if itemState else ''
        return self.job_state_str_to_id(stateStr)

    def queue_set_state_by_job(self, job, state: int):
        if not job:
            return
        job.setState(state)
        self.update_queue_job_state(job.getID(), state)
        self.run_next_wait_job()

    def set_btn_queue_delete_all_state(self):
        rowCount = self.tableQueue.rowCount()
        state = False
        for iRow in range(rowCount):
            try:
                itemState = self.tableQueue.item(iRow, 2)
                if itemState and itemState.text() == self.jobStates[1]:
                    state = True
                    break
            except Exception:
                pass
        if self.btnQueueDeleteAll:
            self.btnQueueDeleteAll.setEnabled(state)

    def update_queue_job_state(self, job_id, state: int):
        rowCount = self.tableQueue.rowCount()
        for iRow in range(rowCount):
            idItem = self.tableQueue.item(iRow, 0)
            if idItem and idItem.text() == str(job_id):
                stateItem = self.tableQueue.item(iRow, 2)
                if stateItem:
                    stateItem.setText(self.get_job_state_string(state))
                break

    def set_queue_btn_states(self):
        selected_rows = self.tableQueue.selectionModel().selectedRows()
        num_selected = len(selected_rows)

        if num_selected == 0:
            self.btnQueueUp.setEnabled(False)
            self.btnQueueDown.setEnabled(False)
            self.btnQueueDelete.setEnabled(False)
            self.btnQueueLoad.setEnabled(False)
        elif num_selected == 1:
            self.btnQueueDelete.setEnabled(True)
            self.btnQueueLoad.setEnabled(True)
            iRow = selected_rows[0].row()
            rowCount = self.tableQueue.rowCount()
            self.btnQueueUp.setEnabled(iRow > 0)
            self.btnQueueDown.setEnabled(iRow < rowCount - 1)
        else:
            self.btnQueueDelete.setEnabled(True)
            self.btnQueueLoad.setEnabled(False)
            indices = sorted([index.row() for index in selected_rows])
            is_contiguous = (indices[-1] - indices[0] + 1 == len(indices))
            if is_contiguous:
                self.btnQueueUp.setEnabled(indices[0] > 0)
                self.btnQueueDown.setEnabled(indices[-1] < self.tableQueue.rowCount() - 1)
            else:
                self.btnQueueUp.setEnabled(False)
                self.btnQueueDown.setEnabled(False)

    def swap_jobs(self, direction: int):
        self.jobsSwapping = True

        currentRow = self.tableQueue.currentRow()
        if currentRow < 0:
            self.jobsSwapping = False
            return

        targetRow = currentRow + direction
        if not (0 <= targetRow < self.tableQueue.rowCount()):
            self.jobsSwapping = False
            return

        job1_id, _ = self.queue_get_job_id_from_row(currentRow)
        job2_id, _ = self.queue_get_job_id_from_row(targetRow)

        job1 = self.jobs.get_job(job1_id)
        job2 = self.jobs.get_job(job2_id)

        if job1 and job2:
            self.jobs.swap_jobs(job1, job2)
            Functions.moveTableRow(self.tableQueue, direction)

        self.jobsSwapping = False

    def move_selected_jobs(self, direction: int):
        selection_model = self.tableQueue.selectionModel()
        selected_rows = sorted([index.row() for index in selection_model.selectedRows()])

        if not selected_rows:
            return

        if direction == -1 and selected_rows[0] == 0:
            return
        if direction == 1 and selected_rows[-1] == self.tableQueue.rowCount() - 1:
            return

        self.jobsSwapping = True

        rows_to_move = selected_rows if direction == -1 else reversed(selected_rows)

        for row in rows_to_move:
            target_row = row + direction

            job1_id, _ = self.queue_get_job_id_from_row(row)
            job2_id, _ = self.queue_get_job_id_from_row(target_row)
            job1 = self.jobs.get_job(job1_id)
            job2 = self.jobs.get_job(job2_id)
            if job1 and job2:
                self.jobs.swap_jobs(job1, job2)
                Functions.moveTableRow(self.tableQueue, direction, start_row=row)

        self.jobsSwapping = False

        selection_model.clearSelection()
        for row in selected_rows:
            selection_model.select(
                self.tableQueue.model().index(row + direction, 0),
                QtCore.QItemSelectionModel.SelectionFlag.Select | QtCore.QItemSelectionModel.SelectionFlag.Rows
            )

    def refresh_queue_table(self):
        current_selection_ids = {job.getID() for job in self.get_selected_jobs()}

        self.tableQueue.setRowCount(0)
        for job in self.jobs.get_sorted_jobs():
            self.queue_add_row(job.getID(), job.getTgtFileNameLong(), self.get_job_state_string(job.getState()))

        for i in range(self.tableQueue.rowCount()):
            job_id = self.tableQueue.item(i, 0).text()
            if job_id in current_selection_ids:
                self.tableQueue.selectRow(i)

    def get_next_waiting_job(self):
        return self.get_next_job_by_state_id(0)

    def get_next_paused_job(self):
        return self.get_next_job_by_state_id(5)

    def get_next_rendering_job(self):
        return self.get_next_job_by_state_id(4)

    def get_next_job_by_state_id(self, stateID: int):
        try:
            for job in self.jobs.get_sorted_jobs():
                if job.getState() == stateID:
                    return job
            return None
        except Exception as e:
            msg = 'Error: Cannot get the next job by ID.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            if self.showMsgBox:
                self.showMsgBox(msg, detailText=traceback.format_exc(), icon='critical')
            return False

    def run_next_wait_job(self) -> bool:
        try:
            if self.ffmpegProcess or (self.btnQueuePause and self.btnQueuePause.isChecked()):
                return False
            self.log(1, 'Running next job ...')
            job = self.get_next_waiting_job()
            if job:
                if self.isSameRenderSrcTgt and self.isSameRenderSrcTgt(job, True):
                    return False
                if self.isSectionsMissing and self.isSectionsMissing(job, True):
                    return False

                self.ffmpegProcess = True
                job.setState(4)
                self.update_queue_job_state(job.getID(), 4)

                self.FFmpegThread = FFmpegThread(job, self.config.getConfigDeshakePath(), jobs_db=self.jobs)
                self.FFmpegThread.finished.connect(self.on_ffmpeg_thread_finished)
                self.FFmpegThread.ffmpegStart.connect(self.on_ffmpeg_start)
                self.FFmpegThread.ffmpegProcess.connect(self.on_ffmpeg_progress)
                self.FFmpegThread.ffmpegExit.connect(self.on_ffmpeg_exit)
                self.FFmpegThread.ffmpegLog.connect(self.on_ffmpeg_log)
                self.FFmpegThread.start()
                self.log(1, 'FFmpeg thread started.')
            else:
                if self.powerManager:
                    mode = self.powerManager.get_active_mode()
                    if mode:
                        self.powerManager.run_power_mode(mode)
            return True
        except Exception as e:
            self.ffmpegProcess = False
            msg = 'Error: Cannot run next waiting job in queue.'
            self.log(1, msg, 1, traceback=traceback.format_exc())
            if self.showMsgBox:
                self.showMsgBox(msg, detailText=traceback.format_exc(), icon='critical')
            return False

    def cancel_current_job(self):
        if self.FFmpegThread and self.FFmpegThread.isRunning():
            self.ffmpegKilled = True
            self.FFmpegThread.cancel()
            self.log(1, "Signaled active PyAV render thread to cancel.")
        else:
            self.log(1, "No active render thread to cancel.")

    def toggle_queue_pause(self):
        if not self.btnQueuePause:
            return
        if self.btnQueuePause.isChecked():
            self.btnQueuePause.setText('契')
            self.btnQueuePause.setToolTip('Resume job processing')
            self.config.setQueueIsPaused(True)
            if self.FFmpegThread and self.FFmpegThread.isRunning():
                self.FFmpegThread.pause(True)
                job = getattr(self.FFmpegThread, 'job', None) or self.get_next_rendering_job()
                if job:
                    job.setState(5)
                    self.update_queue_job_state(job.getID(), 5)
        else:
            self.btnQueuePause.setText('')
            self.btnQueuePause.setToolTip('Pause job processing')
            self.config.setQueueIsPaused(False)
            if self.FFmpegThread and self.FFmpegThread.isRunning():
                self.FFmpegThread.pause(False)
                job = getattr(self.FFmpegThread, 'job', None) or self.get_next_paused_job()
                if job:
                    job.setState(4)
                    self.update_queue_job_state(job.getID(), 4)
            else:
                self.run_next_wait_job()

    def reset_render_details(self):
        """Resets the render details labels to 0 and disables panel."""
        if self.widgetRenderDetails:
            self.widgetRenderDetails.setEnabled(False)
        if self.labelRenderFPS:
            self.labelRenderFPS.setText('0 fps')
        if self.labelRenderSpeed:
            self.labelRenderSpeed.setText('0x')
        if self.labelRenderSize:
            self.labelRenderSize.setText('0 MiB')
        if self.labelRenderTime:
            self.labelRenderTime.setText(self.timeFormat)

    @pyqtSlot('PyQt_PyObject')
    def on_ffmpeg_log(self, msg):
        self.log(2, msg, timestamp=False)

    @pyqtSlot('PyQt_PyObject')
    def on_ffmpeg_progress(self, atts):
        line, job, totalSeconds = atts
        if self.jobsSwapping:
            return
        if not isinstance(line, list) or len(line) != 2:
            return

        if line[0] == 'speed':
            try:
                v = float(line[1][:-1])
                if v >= 0 and self.labelRenderSpeed:
                    self.labelRenderSpeed.setText('%.2fx' % v)
            except Exception:
                pass
        elif line[0] == 'fps':
            try:
                v = float(line[1])
                if v >= 0 and self.labelRenderFPS:
                    self.labelRenderFPS.setText('%.2f %s' % (v, line[0]))
            except Exception:
                pass
        elif line[0] == 'total_size':
            try:
                v = int(line[1])
                if v >= 0 and self.labelRenderSize:
                    self.labelRenderSize.setText('%.2f MiB' % float(v / 1000000))
            except Exception:
                pass
        elif line[0] == 'out_time':
            try:
                if line[1][:-3][0] != '-' and self.labelRenderTime:
                    self.labelRenderTime.setText(line[1][:-3])
            except Exception:
                pass
        elif line[0] == 'out_time_ms':
            if not line[1].isdigit() or int(line[1]) < 0 or not self.progressBarRender:
                return
            currentSecond = int(int(line[1]) / 10000)
            totalSecs = int(totalSeconds * 100)
            if currentSecond > totalSecs:
                currentSecond = totalSecs

            if currentSecond == 0:
                self.progressBarRender.setMaximum(0)
            else:
                self.progressBarRender.setMaximum(totalSecs)
                self.progressBarRender.setValue(currentSecond)
        elif line[0] == 'pass_info':
            try:
                if self.labelRenderSpeed:
                    self.labelRenderSpeed.setText(line[1])
            except Exception:
                pass

    @pyqtSlot('PyQt_PyObject')
    def on_ffmpeg_exit(self, atts):
        self.log(1, 'FFmpeg exited.')

        if len(atts) >= 6:
            job, code, output, error, deshakeFile, full_log = atts
        else:
            job, code, output, error, deshakeFile = atts
            full_log = ""

        errorMsg = ''
        if self.ffmpegKilled:
            self.ffmpegKilled = False
            errorMsg = 'ffmpeg killed while rendering by the user.\n\n'

        if full_log:
            job.setLog(full_log)
        elif errorMsg:
            job.setLog(errorMsg)

        job.setFilterDeshakeFile(deshakeFile)
        if self.progressBarRender and self.progressBarRender.isEnabled():
            self.progressBarRender.setValue(0)
            self.progressBarRender.setEnabled(False)
        if self.widgetRenderDetails and self.widgetRenderDetails.isEnabled():
            self.reset_render_details()

        state = 1 if code == 0 else 3
        if errorMsg and 'killed' in errorMsg.lower():
            state = 6

        if state in (3, 6):
            tgtPath = job.getTgtFilePathLong()
            Functions.safeDeleteTargetFile(tgtPath, self.jobs, currentJobId=job.getID(), logger=lambda msg: self.log(1, msg))

        job.setState(state)
        if self.btnQueueKill and self.btnQueueKill.isEnabled():
            self.btnQueueKill.setEnabled(False)

        job_id = job.getID()
        self.update_queue_job_state(job_id, state)

    @pyqtSlot('PyQt_PyObject')
    def on_ffmpeg_start(self, atts):
        job = atts[0]
        totalSeconds = atts[1]
        self.ffmpegProcess = atts[2]

        if self.progressBarRender and not self.progressBarRender.isEnabled():
            self.progressBarRender.setEnabled(True)
            self.progressBarRender.setMinimum(0)
            self.progressBarRender.setMaximum(0)
            self.progressBarRender.setValue(0)

        if self.widgetRenderDetails and not self.widgetRenderDetails.isEnabled():
            self.widgetRenderDetails.setEnabled(True)

        if self.btnQueueKill and not self.btnQueueKill.isEnabled():
            self.btnQueueKill.setEnabled(True)

    @pyqtSlot()
    def on_ffmpeg_thread_finished(self):
        self.ffmpegProcess = False
        self.FFmpegThread = None
        Functions.trimMemory()
        self.run_next_wait_job()

    def on_queue_context_menu(self, point):
        selected_rows = self.tableQueue.selectionModel().selectedRows()
        num_selected = len(selected_rows)

        if num_selected == 0:
            return

        menu = QMenu(self.parent)

        if num_selected == 1:
            if self.actionPlayFile:
                self.actionPlayFile.setEnabled(True)
            if self.actionShowLog:
                self.actionShowLog.setEnabled(True)

            state = self.queue_get_current_state()

            if state == 4: # Rendering
                if self.actionPlayFile:
                    self.actionPlayFile.setEnabled(False)
                if self.actionPlayFile:
                    menu.addAction(self.actionPlayFile)
                if self.actionOpenFolder:
                    menu.addAction(self.actionOpenFolder)
                menu.addSeparator()
                if self.actionStateCancel:
                    menu.addAction(self.actionStateCancel)
                menu.addSeparator()
                if self.actionMoveTop:
                    menu.addAction(self.actionMoveTop)
                if self.actionMoveBottom:
                    menu.addAction(self.actionMoveBottom)
                menu.addSeparator()
                if self.actionShowLog:
                    self.actionShowLog.setEnabled(False)
                    menu.addAction(self.actionShowLog)
            else:
                if state == 1 and self.actionPlayFile:
                    menu.addAction(self.actionPlayFile)
                if self.actionOpenFolder:
                    menu.addAction(self.actionOpenFolder)
                menu.addSeparator()

                if state == 0 and self.actionStatePostpone:
                    menu.addAction(self.actionStatePostpone)
                if state == 2 and self.actionStateResume:
                    menu.addAction(self.actionStateResume)
                if state in (1, 3, 6) and self.actionStateReset:
                    menu.addAction(self.actionStateReset)

                menu.addSeparator()
                if self.actionMoveTop:
                    menu.addAction(self.actionMoveTop)
                if self.actionMoveBottom:
                    menu.addAction(self.actionMoveBottom)

                if state != 0 and state != 4:
                    menu.addSeparator()
                    if self.actionShowLog:
                        menu.addAction(self.actionShowLog)

            menu.addSeparator()
            if self.actionEditDBEntry:
                menu.addAction(self.actionEditDBEntry)

        else: # Multiple jobs selected
            selected_jobs = self.get_selected_jobs()

            actionOpenFolders = QAction('Open folders', self.parent)
            actionOpenFolders.triggered.connect(self.on_queue_ctx_action_open_folders)
            menu.addAction(actionOpenFolders)

            menu.addSeparator()

            resettable_jobs = [j for j in selected_jobs if j.getState() in [1, 3, 6]]
            count_resettable = len(resettable_jobs)
            actionReset = QAction('Reset Jobs', self.parent)
            if count_resettable > 0:
                actionReset.setText(f'Reset {count_resettable} Jobs')
                actionReset.triggered.connect(lambda: self.on_queue_ctx_action_reset_jobs(resettable_jobs))
            else:
                actionReset.setEnabled(False)
            menu.addAction(actionReset)

            cancellable_jobs = [j for j in selected_jobs if j.getState() == 4]
            count_cancellable = len(cancellable_jobs)
            actionCancel = QAction('Cancel Jobs', self.parent)
            if count_cancellable > 0:
                actionCancel.setText(f'Cancel {count_cancellable} Jobs')
                actionCancel.triggered.connect(lambda: self.on_queue_ctx_action_cancel_jobs(cancellable_jobs))
            else:
                actionCancel.setEnabled(False)
            menu.addAction(actionCancel)

            resumable_jobs = [j for j in selected_jobs if j.getState() == 2]
            count_resumable = len(resumable_jobs)
            actionResume = QAction('Resume Jobs', self.parent)
            if count_resumable > 0:
                actionResume.setText(f'Resume {count_resumable} Jobs')
                actionResume.triggered.connect(lambda: self.on_queue_ctx_action_resume_jobs(resumable_jobs))
            else:
                actionResume.setEnabled(False)
            menu.addAction(actionResume)

            menu.addSeparator()

            actionMoveTop = QAction('Move to top', self.parent)
            actionMoveTop.triggered.connect(self.on_queue_ctx_action_move_top_multi)
            menu.addAction(actionMoveTop)

            actionMoveBottom = QAction('Move to bottom', self.parent)
            actionMoveBottom.triggered.connect(self.on_queue_ctx_action_move_bottom_multi)
            menu.addAction(actionMoveBottom)

        global_point = self.tableQueue.mapToGlobal(point)
        menu.popup(global_point)

    def on_queue_ctx_action_open_folders(self):
        selected_jobs = self.get_selected_jobs()
        unique_dirs = set(job.getTgtDirName() for job in selected_jobs if job.getTgtDirName())
        opener = Functions.getCurrentSysOpener()
        for folder in unique_dirs:
            if os.path.isdir(folder):
                subprocess.call([opener, folder])

    def on_queue_ctx_action_reset_jobs(self, jobs_to_reset):
        for job in jobs_to_reset:
            self.queue_set_state_by_job(job, 0)

    def on_queue_ctx_action_cancel_jobs(self, jobs_to_cancel):
        if any(job.getState() == 4 for job in jobs_to_cancel):
            self.cancel_current_job()

    def on_queue_ctx_action_resume_jobs(self, jobs_to_resume):
        for job in jobs_to_resume:
            self.queue_set_state_by_job(job, 0)

    def on_queue_ctx_action_play_file(self):
        jobID = self.queue_get_job_id_from_row()[0]
        job = self.jobs.get_job(jobID)
        if job:
            filePathLong = job.getTgtFilePathLong()
            opener = Functions.getCurrentSysOpener()
            subprocess.call([opener, filePathLong])

    def on_queue_ctx_action_open_folder(self):
        jobID = self.queue_get_job_id_from_row()[0]
        job = self.jobs.get_job(jobID)
        if job and job.getTgtDirName():
            opener = Functions.getCurrentSysOpener()
            subprocess.call([opener, job.getTgtDirName()])

    def on_queue_ctx_action_state_postpone(self):
        jobID, _ = self.queue_get_job_id_from_row()
        job = self.jobs.get_job(jobID)
        if job:
            self.queue_set_state_by_job(job, 2)

    def on_queue_ctx_action_state_resume(self):
        jobID, _ = self.queue_get_job_id_from_row()
        job = self.jobs.get_job(jobID)
        if job:
            self.queue_set_state_by_job(job, 0)

    def on_queue_ctx_action_state_reset(self):
        jobID, _ = self.queue_get_job_id_from_row()
        job = self.jobs.get_job(jobID)
        if job:
            self.queue_set_state_by_job(job, 0)

    def on_queue_ctx_action_cancel_job(self):
        if self.queue_get_current_state() == 4:
            self.cancel_current_job()
        else:
            self.log(1, "Cancel Job action triggered, but job is no longer rendering.")

    def on_queue_ctx_action_show_log(self):
        jobID, _ = self.queue_get_job_id_from_row()
        job = self.jobs.get_job(jobID)
        if not job:
            return
        log_text = job.getLog()
        if not log_text:
            if self.showMsgBox:
                self.showMsgBox('There is nothing logged.')
            return
        if self.logUi:
            self.logUi.setTitle('Log for Job %s' % jobID)
            self.logUi.setLogText(log_text.replace('\\n', '\n'))
            self.logUi.show()

    def on_queue_ctx_action_move_top_multi(self):
        all_jobs_sorted = self.jobs.get_sorted_jobs()
        selected_jobs = sorted(self.get_selected_jobs(), key=lambda j: j.getPosition())

        selected_ids = {job.getID() for job in selected_jobs}
        unselected_jobs = [job for job in all_jobs_sorted if job.getID() not in selected_ids]

        new_order_jobs = selected_jobs + unselected_jobs
        new_order_ids = [job.getID() for job in new_order_jobs]

        self.jobs.reorder_jobs(new_order_ids)
        self.refresh_queue_table()

    def on_queue_ctx_action_move_bottom_multi(self):
        all_jobs_sorted = self.jobs.get_sorted_jobs()
        selected_jobs = sorted(self.get_selected_jobs(), key=lambda j: j.getPosition())

        selected_ids = {job.getID() for job in selected_jobs}
        unselected_jobs = [job for job in all_jobs_sorted if job.getID() not in selected_ids]

        new_order_jobs = unselected_jobs + selected_jobs
        new_order_ids = [job.getID() for job in new_order_jobs]

        self.jobs.reorder_jobs(new_order_ids)
        self.refresh_queue_table()
