import sys
import ffmpeg
import time

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

    @staticmethod
    def appendTrailingSlash(text):
        if not text[:-1] == '/': text = '%s/' % text
        return text

    # H:M:S.f to seconds (int)
    @staticmethod
    def HMSToTimestamp(timeStr, asFloat=False):
        '''Converts a timestamp like 0:00:12.323 to a timestamp like 12.3234'''
        h, m, s = timeStr.split(':')
        s, ms = s.split('.')
        if asFloat: return float(h) * 3600 + float(m) * 60 + float(s) + (float(ms) / 1000)
        else: return float(h) * 3600 + float(m) * 60 + float(s)

    @staticmethod
    def timestampToHMS(timestamp):
        '''Converts a timestamp like 12.3234 to HMLS like 0:00:12.323'''
        timeSplit = str(timestamp).split('.', 1)
        timeMs = timeSplit[1]
        if len(timeMs) == 1: timeMs = '%s0' % timeSplit[1]
        timeMs = '{:03d}'.format(int(timeSplit[1][:3]))
        time = "%s.%s" % (Functions.convertSecondsToHMFS(int(timeSplit[0])), timeMs)
        return time

    # Get the system opener name for the current OS / system
    @staticmethod
    def getCurrentSysOpener():
        # Todo: use os.startfile() on windows
        return "open" if sys.platform == "darwin" else "xdg-open"

    # Check if two strings are the same
    @staticmethod
    def isSameString(string1, string2):
        return string1 == string2

    # Get video properties from ffprobe
    @staticmethod
    def getVideoProperties(videoFilePath):
        props = {}
        videoInfo = ffmpeg.probe(videoFilePath, cmd='ffprobe')
        videoStream = next((stream for stream in videoInfo['streams'] if stream['codec_type'] == 'video'), None)
        format = videoInfo['format']
        try:
            # Get dimensions
            width = int(videoStream['width'])
            height = int(videoStream['height'])
            if width and height:
                props.update({'width' : width})
                props.update({'height' : height})
            # Get duration
            duration = False
            if 'duration' in format: duration = format['duration']
            elif 'duration' in videoStream: duration = videoStream['duration']
            elif 'tags' in videoStream and 'DURATION' in videoStream['tags']: duration = videoStream['tags']['DURATION']
            if duration and not ':' in duration:
                try:
                    float(duration)
                    duration = '%s.%s' % (time.strftime('%H:%M:%S', time.gmtime(float(duration))), duration[-6:][:3]) # ms to h:m:s.ms
                except: pass
            props.update({'durationHMS': duration})
        except:
            props = {}
        return props
