from .Job import Job

import ffmpeg
import threading

class FFmpegControl:

    def __init__(self):
        self.isBusy = False

    def runFFmpeg(self, onExit, atts):
        srcPath = atts.get('srcFilePathLong')
        tgtPath = atts.get('tgtFilePathLong')
        if(self.isSamePath(srcPath, tgtPath)):
            print('Errror: Input and Output Path are the same')
            return False

        print('stream ...')

        in_file = ffmpeg.input(srcPath)

        video1 = (
            in_file.video
            .trim(start="0:01:00.0", end="0:01:02.0")
            .setpts('PTS-STARTPTS')
        )
        video2 = (
            in_file.video
            .trim(start="0:02:00.0", end="0:02:02.0")
            .setpts('PTS-STARTPTS')
        )
        audio1 = (
            in_file.audio
            .filter_('atrim', start="0:01:00.0", end="0:01:02.0")
            .filter_('asetpts', 'PTS-STARTPTS')
        )
        audio2 = (
            in_file.audio
            .filter_('atrim', start="0:02:00.0", end="0:02:02.0")
            .filter_('asetpts', 'PTS-STARTPTS')
        )
        joined = ffmpeg.concat(video1, audio1, video2, audio2, v=1, a=1).node
        output = ffmpeg.output(joined[0], joined[1], tgtPath)

        process = output.run_async(overwrite_output=True, pipe_stderr=True)
        err = process.communicate()
        code = process.returncode
        onExit(err, code)
        return

    # Start ffmpeg in a thread so it's asynchron, use onExit() as callback function
    def render(self, atts):
        self.busy(True)
        thread = threading.Thread(target=self.runFFmpeg, args=(self.onExit, atts))
        thread.start()
        return thread

    # Callback function for ffmpeg process finished
    def onExit(self, err, code):
        self.busy(False)
        print('FFMPEG EXIT')
        print(err)
        pass

    def renderJob(self, job):
        print('renderJob')
        atts = {}
        atts.update({'srcFilePathLong': job.getSrcFilePathLong()})
        atts.update({'tgtFilePathLong': job.getTgtFilePathLong()})
        self.render(atts)

    def isSamePath(self, path1, path2):
        return path1 == path2

    def busy(self, activate = False):
        if(activate):
            self.isBusy = True
        return self.isBusy
