import sys
import av
import time
import json

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
        if len(timeMs) == 1: timeMs = '%s00' % timeSplit[1]
        elif len(timeMs) == 2: timeMs = '%s0' % timeSplit[1]
        else: timeMs = '{:03d}'.format(int(timeSplit[1][:3]))
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
        try:
            with av.open(videoFilePath) as container:
                video_stream = next((s for s in container.streams if s.type == 'video'), None)
                audio_stream = next((s for s in container.streams if s.type == 'audio'), None)

                if video_stream and video_stream.codec_context:
                    props['width'] = video_stream.codec_context.width
                    props['height'] = video_stream.codec_context.height

                duration = container.duration
                if duration is not None:
                    duration_sec = duration / av.time_base
                    ms = int((duration_sec % 1) * 1000)
                    time_hms = time.strftime('%H:%M:%S', time.gmtime(duration_sec))
                    props['durationHMS'] = f"{time_hms}.{ms:03d}"

                props['hasAudio'] = audio_stream is not None
        except Exception as e:
            props = {}
        return props


    @staticmethod
    def getVideoCodecInfo(videoFilePath):
        output = "Video properties:\n"
        try:
            props = Functions.getVideoProperties(videoFilePath)
            output += str(props) + "\n\nPyAV Stream Info:\n"
            with av.open(videoFilePath) as container:
                for i, stream in enumerate(container.streams):
                    output += f"Stream {i} ({stream.type}):\n"
                    if stream.codec_context:
                        output += f"  Codec: {stream.codec_context.name}\n"
                        if stream.type == 'video':
                            output += f"  Resolution: {stream.codec_context.width}x{stream.codec_context.height}\n"
                            output += f"  Framerate: {stream.average_rate}\n"
                            output += f"  Pixel Format: {stream.codec_context.pix_fmt}\n"
                        elif stream.type == 'audio':
                            output += f"  Sample Rate: {stream.codec_context.sample_rate} Hz\n"
                            output += f"  Channels: {stream.codec_context.channels}\n"
                    output += f"  Bitrate: {stream.bit_rate}\n\n"
        except Exception as e:
            output += "Error probing with PyAV:\n" + str(e)
        return output
