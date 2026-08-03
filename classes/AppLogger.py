import datetime

class AppLogger:
    """
    Handles application-wide logging across different log tabs (App, FFmpeg, Database).
    Prints messages to stdout/stderr and appends formatted HTML text to designated Qt widgets.
    """

    def __init__(self, log_app_widget, log_ffmpeg_widget, log_db_widget):
        self.logApp = log_app_widget
        self.logFFmpeg = log_ffmpeg_widget
        self.logDB = log_db_widget

    def log(self, id: int, line: str, msgType: int = 0, timestamp: bool = True, traceback: str = False):
        """
        Adds a line to a log text widget and stdout.

        :param id: Log destination (1 = App, 2 = FFmpeg, 3 = DB)
        :param line: String message to add to the log
        :param msgType: 0 = Normal, 1 = Error (red text)
        :param timestamp: Adds a timestamp with H:M:S as prefix if True
        :param traceback: Error traceback string to print to console
        """
        print(line)
        if traceback:
            print(traceback)

        if timestamp:
            line = '%s %s' % (datetime.datetime.now().strftime('%H:%M:%S'), line)

        if msgType == 1:
            line = '<font color="red">%s</font>' % line

        line = '%s<br>' % line

        textEdit = self.logApp
        if id == 2:
            textEdit = self.logFFmpeg
        elif id == 3:
            textEdit = self.logDB

        if textEdit:
            textEdit.insertHtml(line)
            self.scroll_widget_to_end(textEdit)

    def __call__(self, id: int, line: str, msgType: int = 0, timestamp: bool = True, traceback: str = False):
        """Allows the AppLogger instance to be passed directly as a logging callable."""
        self.log(id, line, msgType=msgType, timestamp=timestamp, traceback=traceback)

    @staticmethod
    def scroll_widget_to_end(element, forceScrolling: bool = False):
        """
        Scrolls a text widget to the end.

        :param element: QTextEdit element to scroll
        :param forceScrolling: If True, the widget gets scrolled down even if it has focus.
        """
        scroll = True
        if not forceScrolling:
            if element.hasFocus():
                scroll = False
        if scroll and element:
            element.verticalScrollBar().setValue(element.verticalScrollBar().maximum() + 1000)
