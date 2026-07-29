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
        try:
            val = Functions._parse_time_to_seconds(timeStr)
            return val if asFloat else int(round(val))
        except Exception:
            return 0.0 if asFloat else 0

    @staticmethod
    def timestampToHMS(timestamp):
        '''Converts a timestamp like 12.3234 to HMLS like 0:00:12.323'''
        timeSplit = str(timestamp).split('.', 1)
        timeMs = timeSplit[1] if len(timeSplit) > 1 else '0'
        if len(timeMs) == 1: timeMs = '%s00' % timeMs
        elif len(timeMs) == 2: timeMs = '%s0' % timeMs
        else: timeMs = '{:03d}'.format(int(timeMs[:3]))
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
    def getVideoPropertiesAndCodecInfo(videoFilePath):
        props = {}
        output = "Video properties:\n"
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

                output += str(props) + "\n\nPyAV Stream Info:\n"
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
        return props, output

    @staticmethod
    def getVideoCodecInfo(videoFilePath, props=None):
        if props is not None:
            output = "Video properties:\n" + str(props) + "\n\nPyAV Stream Info:\n"
            try:
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
        else:
            _, codec_info = Functions.getVideoPropertiesAndCodecInfo(videoFilePath)
            return codec_info

    @staticmethod
    def calculateJobImagesInfo(job, videoProps=None):
        if not videoProps:
            videoProps = {}

        w, h = Functions._calculate_target_dimensions(job, videoProps)
        fmt = Functions._extract_target_format(job)
        duration = Functions._calculate_target_duration(job, videoProps)

        return {
            'width': w,
            'height': h,
            'orient': 1,
            'format': '',
            'depth': 0,
            'duration': duration,
            'bits': 0,
            'ratio': 0,
            'colorProfile': ''
        }

    @staticmethod
    def _calculate_target_dimensions(job, videoProps):
        w = videoProps.get('width', 0) or 0
        h = videoProps.get('height', 0) or 0

        if job.getFilterCropState():
            crop_t = job.getFilterCropT() or 0
            crop_r = job.getFilterCropR() or 0
            crop_b = job.getFilterCropB() or 0
            crop_l = job.getFilterCropL() or 0
            w = max(0, w - crop_l - crop_r)
            h = max(0, h - crop_t - crop_b)

        if job.getFilterResizeState():
            res_w = job.getFilterResizeWidth() or 0
            res_h = job.getFilterResizeHeight() or 0
            if res_w > 0:
                w = res_w
            if res_h > 0:
                h = res_h

        rotate = job.getFilterRotate()
        if rotate in (90, -90):
            w, h = h, w

        return int(w), int(h)

    @staticmethod
    def _extract_target_format(job):
        container = job.getRenderSettingContainer() or job.getTgtFileExt().lstrip('.')
        if container:
            return str(container).lower()
        return ''

    @staticmethod
    def _calculate_target_duration(job, videoProps):
        sections = job.getSections()
        total_duration = 0.0

        if sections:
            for sec in sections:
                try:
                    start_s = Functions._parse_time_to_seconds(sec[0])
                    end_s = Functions._parse_time_to_seconds(sec[1])
                    if end_s > start_s:
                        total_duration += (end_s - start_s)
                except Exception:
                    pass

        if total_duration == 0.0 and videoProps:
            dur = videoProps.get('durationHMS') or videoProps.get('durationMs')
            if dur:
                total_duration = Functions._parse_time_to_seconds(dur)

        return int(round(total_duration * 1000))

    @staticmethod
    def _parse_time_to_seconds(time_val):
        if time_val is None:
            return 0.0
        if isinstance(time_val, (int, float)):
            return float(time_val)
        time_str = str(time_val).strip()
        if not time_str:
            return 0.0
        try:
            parts = time_str.split(':')
            if len(parts) == 3:
                h = float(parts[0])
                m = float(parts[1])
                s = float(parts[2])
                return h * 3600 + m * 60 + s
            elif len(parts) == 2:
                m = float(parts[0])
                s = float(parts[1])
                return m * 60 + s
            elif len(parts) == 1:
                return float(parts[0])
        except Exception:
            pass
        return 0.0
