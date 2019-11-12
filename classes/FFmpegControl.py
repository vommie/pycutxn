from .Job import Job
from .Functions import Functions

import ffmpeg
import threading

class FFmpegControl:

    def __init__(self):
        self.isBusy = False
        self._progressObservers = []
        self._exitObservers = []
        self._startObservers = []

    # Add callback function to ffmpeg progress observer
    def bindToProgress(self, callback):
        self._progressObservers.append(callback)

    # Add callback function to ffmpeg exit observer
    def bindToExit(self, callback):
        self._exitObservers.append(callback)

    # Add callback function to ffmpeg start observer
    def bindToStart(self, callback):
        self._startObservers.append(callback)

    def renderJob(self, job):
        atts = {'job': job}
        self.setBusy(True)
        self.render(atts)

    # Start ffmpeg in a thread so it's asynchron, use onExit() as callback function
    def render(self, atts):
        thread = threading.Thread(target=self.runFFmpeg, args=(self.onExit, atts))
        thread.start()
        return thread

    def runFFmpeg(self, onExit, atts):
        job = atts.get('job')
        srcPath = job.getSrcFilePathLong()
        tgtPath = job.getTgtFilePathLong()
        if(self.isSamePath(srcPath, tgtPath)):
            print('Error: Input and Output Path are the same')
            self.onExit(job, -100, 'Input and Output Path are the same', 'Input and Output Path are the same')
            return False
        # Set FFmpeg options
        in_file = ffmpeg.input(srcPath)
        # Build sections
        sections = job.getSections()
        mapping = []
        totalSeconds = 0
        for section in sections:
            # ffmpeg
            video = (
                in_file.video
                .trim(start=section[0], end=section[1])
                .setpts('PTS-STARTPTS')
            )
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
        process = output.run_async(overwrite_output=True, pipe_stdout=True, pipe_stderr=True)
        for callback in self._startObservers:
            callback(job, totalSeconds)
        # Handle stdout (progress information), by passing it to callback functions
        for line in process.stdout:
            line = line.decode('ascii').rstrip()
            line = line.split('=')
            for callback in self._progressObservers:
                callback(line, job, totalSeconds)
        # Get stdout and stderror for logging purposes etc.
        out, err = process.communicate()
        code = process.returncode
        self.onExit(job, code, out, err)
        return True

    # Callback function for ffmpeg process finished
    def onExit(self, job, code, output, error):
        self.setBusy(False)
        for callback in self._exitObservers:
            callback(job, code, output, error)

    def isSamePath(self, path1, path2):
        return path1 == path2

    def setBusy(self, state):
        self.isBusy = state

    def busy(self):
        return self.isBusy
