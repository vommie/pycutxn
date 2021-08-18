from .Job import Job
from .Functions import Functions

import ffmpeg
import os
from PyQt5.QtCore import pyqtSignal, QThread

# TODO:
# Deshaker file per job, remove file after successful 2nd pass

class FFmpegThread(QThread):

    ffmpegStart = pyqtSignal('PyQt_PyObject')
    ffmpegProcess = pyqtSignal('PyQt_PyObject')
    ffmpegExit = pyqtSignal('PyQt_PyObject')

    def __init__(self, job, configPath):
        self.job = job
        self.configPath = configPath
        QThread.__init__(self)

    def __del__(self):
        self.wait()

    def run(self):
        job = self.job
        deshakeFile = False
        srcPath = job.getSrcFilePathLong()
        tgtPath = job.getTgtFilePathLong()
        # Probe file
        out = ''
        code = 0
        err = ''
        videoProps = Functions.getVideoProperties(srcPath)
        if not videoProps:
            out = ''
            code = 1
            err = 'Probing the target file had no positive results'
        else:
            # Set FFmpeg options
            in_file = ffmpeg.input(srcPath)
            # Build sections
            deshake_state = job.getFilterDeshakeState()
            render_passes = 1
            sections = job.getSections()
            if deshake_state: render_passes = 2
            for render_pass in range(1,render_passes+1):
                if code == 1: continue
                mapping = []
                totalSeconds = 0
                for section in sections:
                    # Trimming
                    video = (
                        in_file.video
                        .trim(start=section[0], end=section[1])
                        .setpts('PTS-STARTPTS')
                    )
                    filterPositions = job.getFilterPositions()
                    width = False
                    height = False
                    for position in sorted(filterPositions.keys()):
                        filter = filterPositions.get(position)
                        print('Applying filter nr. %s: %s' % (position, filter))
                        if filter == 'deshake' and deshake_state:
                            print(self.configPath)
                            if not os.path.isdir(self.configPath): os.makedirs(self.configPath)
                            deshakeFile = '%s/job_%s.trf' % (self.configPath, job.getID())
                            if render_pass == 1:
                                video = ( video .filter('vidstabdetect', stepsize=32, shakiness=10, accuracy=10, result=deshakeFile) )
                            elif render_pass == 2:
                                video = ( video .filter('vidstabtransform', input=deshakeFile, crop='black', optzoom=0, zoom=0, smoothing=10,interpol='bicubic') )
                                video = ( video .filter('unsharp', 5,5,0.8,3,3,0.4) )
                        elif filter == 'deinterlace' and job.getFilterDeinterlaceState():
                            deinterlacer = job.getFilterDeinterlaceDeinterlacer()
                            video = ( video .filter(deinterlacer))
                        elif filter == 'resize' and job.getFilterResizeState():
                            width = job.getFilterResizeWidth()
                            height = job.getFilterResizeHeight()
                            if width and not height:
                                video = (video .filter('scale', width, -1))
                            elif height and not width:
                                video = ( video .filter('scale', -1, height))
                            elif width and height:
                                video = (video .filter('scale', width, height))
                                video = (video .filter('setsar', 1, 1))
                        elif filter == 'rotate':
                            rotate = job.getFilterRotate()
                            if rotate:
                                if rotate == 90: rotate = 1
                                elif rotate == -90: rotate = 2
                                if rotate == 1 or rotate == 2: video = (video .filter('transpose', rotate))
                                else: video = (video .filter('transpose', 2) .filter('transpose', 2))
                        elif filter == 'crop' and job.getFilterCropState():
                            t = job.getFilterCropT()
                            r = job.getFilterCropR()
                            b = job.getFilterCropB()
                            l = job.getFilterCropL()
                            if not width: width = videoProps.get('width')
                            if not height: height = videoProps.get('height')
                            w = width - l - r
                            h = height - t - b
                            video = ( video .crop(x=l, y=t, width=w, height=h) ) # Todo: If video first gets rotated, this calculation has to be rotated too
                    # Finalization
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
                    # Handle stdout (progress information), by passing it to callback functions
                    for line in process.stdout:
                        print(line)
                        line = line.decode('ascii').rstrip()
                        line = line.split('=')
                        self.ffmpegProcess.emit([line, job, totalSeconds])
                    # Get stdout and stderror for logging purposes etc.
                    out, err = process.communicate()
                    code = process.returncode
                except Exception as e:
                    code = 1
                    err = str(e)
        # self.ffmpegExit.emit([job, code, out, err])
        self.ffmpegExit.emit([job, code, out, err, deshakeFile])
