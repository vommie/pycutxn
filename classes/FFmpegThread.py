from .Job import Job
from .Functions import Functions

import ffmpeg
from PyQt5.QtCore import pyqtSignal, QThread

class FFmpegThread(QThread):

    ffmpegStart = pyqtSignal('PyQt_PyObject')
    ffmpegProcess = pyqtSignal('PyQt_PyObject')
    ffmpegExit = pyqtSignal('PyQt_PyObject')

    def __init__(self, job):
        self.job = job
        QThread.__init__(self)

    def __del__(self):
        self.wait()

    def run(self):
        job = self.job
        srcPath = job.getSrcFilePathLong()
        tgtPath = job.getTgtFilePathLong()
        # Set FFmpeg options
        in_file = ffmpeg.input(srcPath)
        # Build sections
        sections = job.getSections()
        mapping = []
        totalSeconds = 0
        # Todo: Add Crop, Resize, Deshake, Rotate (90, -90, 180)
        for section in sections:
            video = (
                in_file.video
                .trim(start=section[0], end=section[1])
                .setpts('PTS-STARTPTS')
            )
            rotate = job.getFilterRotate()
            if rotate:
                if rotate == 90: rotate = 1
                elif rotate == -90: rotate = 2
                if rotate == 1 or rotate == 2: video = ( video .filter('transpose', rotate) )
                else: video = ( video .filter('transpose', 2) .filter('transpose', 2) )
            if job.getFilterCropState():
                w = job.getFilterCropWidth()
                h = job.getFilterCropHeight()
                x = job.getFilterCropX()
                y = job.getFilterCropY()
                if x and y and w and h: print('x: %s, y: %s, w: %s, h: %s' % (x, y, w, h))
                if x and y and w and h: video = ( video .crop(x=x, y=y, width=w, height=h) )

            mapping.append(video)
            audio = (
                in_file.audio
                .filter_('atrim', start=section[0], end=section[1])
                .filter_('asetpts', 'PTS-STARTPTS')
            )
            mapping.append(audio)
            # Calc total seconds (use in progress bar)
            fromSecond = Functions.timeStrToSeconds(section[0], False)
            toSecond = Functions.timeStrToSeconds(section[1], False)
            totalSeconds += (toSecond - fromSecond)
        # Concatenate sections
        joined = ffmpeg.concat(*mapping, v=1, a=1).node
        output = ffmpeg.output(joined[0], joined[1], tgtPath, progress="pipe:")
        # Run ffmpeg
        try:
            process = output.run_async(overwrite_output=True, pipe_stdout=True, pipe_stderr=True)
            self.ffmpegStart.emit([job, totalSeconds, process])
            print('async runned')
            # Handle stdout (progress information), by passing it to callback functions
            for line in process.stdout:
                line = line.decode('ascii').rstrip()
                line = line.split('=')
                self.ffmpegProcess.emit([line, job, totalSeconds])
            # Get stdout and stderror for logging purposes etc.
            out, err = process.communicate()
            code = process.returncode
        except Exception as e:
            out = ''
            code = 1
            err = str(e)
        self.ffmpegExit.emit([job, code, out, err])
