import sys

class Functions:

    @staticmethod
    def convertSecondsToHMFS(seconds):
        seconds = seconds % (24 * 3600)
        hour = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60

        return "%d:%02d:%02d" % (hour, minutes, seconds)

    # Move an table item up (+1) or down (-1)
    @staticmethod
    def moveTableRow(control, directionValue):
        rowCount = control.rowCount()
        colCount = control.columnCount()
        rowIndex = control.currentRow()
        to = rowIndex
        if rowIndex + directionValue >= 0 and rowIndex + directionValue <= rowCount - 1:
            to = rowIndex + directionValue
            for colIndex in range(colCount):
                item = control.takeItem(rowIndex, colIndex)
                prevItem = control.takeItem(rowIndex + directionValue, colIndex)
                control.setItem(rowIndex, colIndex, prevItem)
                control.setItem(rowIndex + directionValue, colIndex, item)
            control.setCurrentItem(item)
        return {
            'from': rowIndex,
            'to': to
        }

    @staticmethod
    def removeTrailingSlash(text):
        text = text.rstrip('\\')
        text = text.rstrip('/')
        return text

    # H:M:S.f to seconds (int)
    @staticmethod
    def timeStrToSeconds(timeStr, asFloat=False):
        h, m, s = timeStr.split(':')
        s, ms = s.split('.')
        if asFloat: return float(h) * 3600 + float(m) * 60 + float(s) + (float(ms) / 1000)
        else: return float(h) * 3600 + float(m) * 60 + float(s)

    # Get the system opener name for the current OS / system
    @staticmethod
    def getCurrentSysOpener():
        # Todo: use os.startfile() on windows
        return "open" if sys.platform == "darwin" else "xdg-open"

    # Check if two strings are the same
    @staticmethod
    def isSameString(string1, string2):
        return string1 == string2
