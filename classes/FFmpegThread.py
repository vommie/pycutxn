import av
import av.filter
import av.logging
import os
import time
import traceback
import locale
import platform
import sys
import gc
import ctypes
from fractions import Fraction
from PyQt6.QtCore import pyqtSignal, QThread

os.environ["PYAV_LOGGING"] = "off"
try:
    av.logging.set_level(None)
    av.logging.restore_default_callback()
except Exception:
    pass


class AudioCodecHelper:
    """
    Helper utility for resolving audio codec sample rates and sample formats.
    """
    @staticmethod
    def get_sample_rate(codec_name: str, input_sample_rate: int) -> int:
        return 48000 if codec_name == 'libopus' else (input_sample_rate or 44100)

    @staticmethod
    def get_sample_format(codec_name: str) -> str:
        try:
            codec_obj = av.Codec(codec_name, 'w')
            if codec_obj.sample_formats:
                return codec_obj.sample_formats[0].name
        except Exception:
            pass
        return 'flt' if codec_name == 'libopus' else 'fltp'


class PacketMuxer:
    """
    Encapsulates container packet multiplexing and header queue management.
    Prevents header writing until required streams are fully initialized.
    """
    def __init__(self, out_container, has_audio: bool):
        self.container = out_container
        self.has_audio = has_audio
        self.packet_queue = []
        self.header_written = False
        self.total_bytes = 0

    def mux_video_packet(self, packet, is_audio_configured: bool):
        is_ready = not self.has_audio or is_audio_configured
        self._write_packet(packet, is_ready)

    def mux_audio_packet(self, packet, is_video_configured: bool):
        self._write_packet(packet, is_ready=is_video_configured)

    def _write_packet(self, packet, is_ready: bool):
        if hasattr(packet, 'size') and packet.size:
            self.total_bytes += packet.size

        if not self.header_written:
            if not is_ready:
                self.packet_queue.append(packet)
            else:
                for queued_pkt in self.packet_queue:
                    self.container.mux(queued_pkt)
                self.packet_queue.clear()
                self.header_written = True
                self.container.mux(packet)
        else:
            self.container.mux(packet)


class PassState:
    """
    Encapsulates timebase, PTS offsets, and frame counters for a single rendering pass.
    """
    def __init__(self, fps: Fraction):
        self.v_configured = False
        self.a_configured = False
        self.v_time_base = Fraction(fps.denominator, fps.numerator) if fps and fps.numerator else Fraction(1, 25)
        self.a_time_base = None
        self.v_pts_offset = 0
        self.a_pts_offset = 0
        self.rendered_seconds = 0.0
        self.fps_float = float(fps) if fps and fps.numerator else 25.0
        self.frames_processed_pass = 0
        self.start_time = time.time()


class VideoFilterRegistry:
    """
    Registry and builder for video filter nodes conforming to the Open-Closed Principle (OCP).
    """
    @classmethod
    def apply_filter(cls, graph, last_node, f_type: str, job, deshake_state: bool,
                     current_pass: int, deshakeFile: str, log_fn):
        if f_type == 'deshake' and deshake_state:
            return cls._apply_deshake(graph, last_node, current_pass, deshakeFile, log_fn)
        elif f_type == 'deinterlace' and job.getFilterDeinterlaceState():
            node = graph.add(job.getFilterDeinterlaceDeinterlacer())
            last_node.link_to(node)
            return node, False
        elif f_type == 'resize' and job.getFilterResizeState():
            w = job.getFilterResizeWidth() or -1
            h = job.getFilterResizeHeight() or -1
            scale_node = graph.add('scale', width=str(w), height=str(h))
            last_node.link_to(scale_node)
            setsar_node = graph.add('setsar', sar='1/1')
            scale_node.link_to(setsar_node)
            return setsar_node, False
        elif f_type == 'rotate':
            return cls._apply_rotate(graph, last_node, job.getFilterRotate())
        elif f_type == 'crop' and job.getFilterCropState():
            t, b, l, r = job.getFilterCropT() or 0, job.getFilterCropB() or 0, job.getFilterCropL() or 0, job.getFilterCropR() or 0
            node = graph.add('crop', out_w=f"iw-{l}-{r}", out_h=f"ih-{t}-{b}", x=str(l), y=str(t))
            last_node.link_to(node)
            return node, False

        return last_node, False

    @classmethod
    def _apply_deshake(cls, graph, last_node, current_pass: int, deshakeFile: str, log_fn):
        if current_pass == 1:
            kwargs = {
                'result': str(deshakeFile),
                'fileformat': 'ascii',
                'stepsize': '12',
                'shakiness': '5',
                'accuracy': '10'
            }
            log_fn(f"Adding vidstabdetect with kwargs: {kwargs}")
            node = graph.add('vidstabdetect', **kwargs)
            last_node.link_to(node)
            return node, True

        elif current_pass == 2:
            fmt_in = graph.add('format', pix_fmts='yuv420p')
            last_node.link_to(fmt_in)
            last_node = fmt_in

            kwargs = {
                'input': str(deshakeFile),
                'smoothing': '10',
                'optzoom': '0',        # 0 = Completely disables zooming (native 1:1 scale)
                'zoom': '0',
                'crop': 'black',       # 'black' = Fills exposed movement borders with solid black instead of blurry smear
                'interpol': 'bicubic'
            }
            log_fn(f"Adding vidstabtransform with kwargs: {kwargs}")
            node = graph.add('vidstabtransform', **kwargs)
            last_node.link_to(node)
            last_node = node

            return last_node, False
        return last_node, False

    @classmethod
    def _apply_rotate(cls, graph, last_node, rotate_deg: int):
        if rotate_deg == 90:
            node = graph.add('transpose', dir='1')
            last_node.link_to(node)
            return node, False
        elif rotate_deg == -90:
            node = graph.add('transpose', dir='2')
            last_node.link_to(node)
            return node, False
        elif rotate_deg == 180:
            node1 = graph.add('transpose', dir='2')
            last_node.link_to(node1)
            node2 = graph.add('transpose', dir='2')
            node1.link_to(node2)
            return node2, False
        return last_node, False


class FFmpegThread(QThread):
    ffmpegStart = pyqtSignal('PyQt_PyObject')
    ffmpegProcess = pyqtSignal('PyQt_PyObject')
    ffmpegExit = pyqtSignal('PyQt_PyObject')
    ffmpegLog = pyqtSignal('PyQt_PyObject')

    def __init__(self, job, configPath):
        super().__init__()
        self.job = job
        self.configPath = configPath
        self._is_canceled = False
        self._is_paused = False
        self._debug_logs = []

    def _log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {msg}"
        sys.stdout.flush()
        self._debug_logs.append(log_msg)
        self.ffmpegLog.emit(log_msg)

    def cancel(self):
        self._is_canceled = True
        self._log("Render process canceled by user.")

    def pause(self, state: bool):
        self._is_paused = state
        self._log(f"Render process paused: {state}")

    def __del__(self):
        try:
            self.wait()
        except Exception:
            pass

    def _force_c_locale(self):
        try:
            locale.setlocale(locale.LC_NUMERIC, 'C')
            os.environ["LC_NUMERIC"] = "C"
            try:
                libc = ctypes.CDLL(None)
                libc.setlocale(1, b"C")
            except Exception:
                pass
        except Exception as e:
            self._log(f"Warning: Could not enforce 'C' locale: {e}")

    def _log_system_info(self):
        self._log("=== SYSTEM INFO DUMP ===")
        self._log(f"OS: {platform.system()} {platform.release()} {platform.version()} {platform.machine()}")
        self._log(f"Python: {sys.version.replace(chr(10), ' ')}")
        self._log(f"PyAV Version: {av.__version__}")
        try:
            self._log(f"PyAV Library Versions: {av.library_versions}")
        except Exception as e:
            self._log(f"PyAV Library Versions: unavailable ({e})")
        self._log("========================")

    def run(self):
        self._force_c_locale()
        self._log_system_info()

        job = self.job
        deshakeFile = False
        srcPath = job.getSrcFilePathLong()
        tgtPath = job.getTgtFilePathLong()
        self._log(f"Starting Job ID {job.getID()} | Source: {srcPath} | Target: {tgtPath}")

        if not os.path.isfile(srcPath):
            err = f'Input file "{srcPath}" does not exist.'
            self._log(err)
            full_log = "\n".join(self._debug_logs)
            self.ffmpegExit.emit([job, 1, b'', err.encode('utf-8'), deshakeFile, full_log])
            return

        try:
            from classes.Functions import Functions
            videoProps = Functions.getVideoProperties(srcPath)
            if not videoProps:
                raise Exception("Probing the target file failed. File might be corrupted.")

            deshake_state = job.getFilterDeshakeState()
            render_passes = 2 if deshake_state else 1
            sections = job.getSections()
            if not sections:
                raise Exception("No sections to render.")

            totalSeconds = sum([Functions.HMSToTimestamp(s[1], True) - Functions.HMSToTimestamp(s[0], True) for s in sections])
            overall_total_seconds = totalSeconds * render_passes
            self.ffmpegStart.emit([job, overall_total_seconds, self])

            if deshake_state:
                if not os.path.isdir(self.configPath):
                    os.makedirs(self.configPath, exist_ok=True)
                deshakeFile = os.path.abspath(os.path.join(self.configPath, f'job_{job.getID()}_transforms.trf'))
                self._log(f"Deshake TRF file will be saved at: {deshakeFile}")

            start_time_render = time.time()

            for render_pass in range(1, render_passes + 1):
                if self._is_canceled:
                    break

                if render_pass == 1 and deshake_state and os.path.exists(deshakeFile):
                    self._log("Removing old TRF file before Pass 1.")
                    os.remove(deshakeFile)

                self.ffmpegProcess.emit([['pass_info', f'Pass {render_pass}/{render_passes}'], self.job, overall_total_seconds])
                self._run_pass(srcPath, tgtPath, sections, render_pass, render_passes, deshake_state, deshakeFile, videoProps, totalSeconds, overall_total_seconds)

            elapsed = time.time() - start_time_render
            self._log(f"Render completed in {elapsed:.2f} seconds.")

            full_log = "\n".join(self._debug_logs)

            if self._is_canceled:
                if os.path.exists(tgtPath):
                    try:
                        os.remove(tgtPath)
                    except Exception:
                        pass
                self.ffmpegExit.emit([job, 1, b'', b'Render process canceled by user.', deshakeFile, full_log])
            else:
                self.ffmpegExit.emit([job, 0, b'Render complete', b'', deshakeFile, full_log])

        except Exception as e:
            full_traceback = traceback.format_exc()
            self._log(f"Critical error in FFmpegThread:\n{full_traceback}")
            full_log = "\n".join(self._debug_logs)
            err_msg = f"Error:\n{full_traceback}\n\n--- DEBUG LOGS ---\n{full_log}".encode('utf-8')
            self.ffmpegExit.emit([job, 1, b'', err_msg, deshakeFile, full_log])

    @staticmethod
    def _format_fraction(frac, default_str: str) -> str:
        if not frac or frac.numerator == 0 or frac.denominator == 0:
            return default_str
        return f"{frac.numerator}/{frac.denominator}"

    @staticmethod
    def _format_out_time(seconds: float) -> str:
        if seconds < 0:
            seconds = 0.0
        s = int(seconds)
        ms = int(round((seconds - s) * 1000000))
        if ms >= 1000000:
            s += 1
            ms = 0
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:06d}"

    def _emit_render_progress(self, pass_state: PassState, current_pass: int, totalSeconds: float,
                              overall_total_seconds: float, is_final_pass: bool, muxer: PacketMuxer = None):
        pass_offset = totalSeconds if current_pass == 2 else 0
        current_progress = pass_offset + pass_state.rendered_seconds

        elapsed = time.time() - pass_state.start_time
        if elapsed > 0:
            calc_fps = pass_state.frames_processed_pass / elapsed
            calc_speed = pass_state.rendered_seconds / elapsed

            self.ffmpegProcess.emit([['fps', f"{calc_fps:.2f}"], self.job, overall_total_seconds])
            self.ffmpegProcess.emit([['speed', f"{calc_speed:.2f}x"], self.job, overall_total_seconds])

        if is_final_pass and muxer:
            self.ffmpegProcess.emit([['total_size', str(muxer.total_bytes)], self.job, overall_total_seconds])

        out_time_str = self._format_out_time(pass_state.rendered_seconds)
        self.ffmpegProcess.emit([['out_time', out_time_str], self.job, overall_total_seconds])

        self.ffmpegProcess.emit([
            ['out_time_ms', str(int(current_progress * 1000000))],
            self.job,
            overall_total_seconds
        ])

    def _build_video_graph(self, v_in_stream, is_final_pass, deshake_state, current_pass, deshakeFile):
        v_codec = self.job.getRenderSettingVideoCodec()
        self._log(f"Building video filter graph (Pass {current_pass}, Final: {is_final_pass})")
        v_graph = av.filter.Graph()

        fps_str = self._format_fraction(v_in_stream.average_rate, "25/1")
        tb_str = self._format_fraction(v_in_stream.time_base, "1/25")
        sar_str = self._format_fraction(v_in_stream.sample_aspect_ratio, "1/1")

        buffer_kwargs = {
            'video_size': f"{v_in_stream.width}x{v_in_stream.height}",
            'pix_fmt': v_in_stream.format.name,
            'time_base': tb_str,
            'pixel_aspect': sar_str,
            'frame_rate': fps_str
        }
        self._log(f"Creating 'buffer' node with explicit kwargs: {buffer_kwargs}")
        v_src = v_graph.add('buffer', **buffer_kwargs)

        last_node = v_src
        filterPositions = self.job.getFilterPositions()
        sorted_positions = sorted(filterPositions.keys(), key=lambda x: int(x))

        for position in sorted_positions:
            f_type = filterPositions.get(position)
            last_node, break_loop = VideoFilterRegistry.apply_filter(
                v_graph, last_node, f_type, self.job, deshake_state,
                current_pass, deshakeFile, self._log
            )
            if break_loop:
                break

        if is_final_pass:
            target_pix_fmt = 'yuv420p10le' if v_codec == 'libsvtav1' else 'yuv420p'
            format_node = v_graph.add('format', pix_fmts=target_pix_fmt)
            last_node.link_to(format_node)
            last_node = format_node

        v_sink = v_graph.add('buffersink')
        last_node.link_to(v_sink)
        self._log("Configuring video graph...")
        v_graph.configure()
        self._log("Video graph configured successfully.")
        return v_graph, v_src, v_sink

    def _setup_output_streams(self, tgtPath, fps, has_audio, a_in_stream):
        """
        Initializes output container and streams with specific codec properties.
        """
        v_codec = self.job.getRenderSettingVideoCodec()
        out_container = av.open(tgtPath, 'w')
        out_v_stream = out_container.add_stream(v_codec, rate=fps)

        encoder_options = {
            'crf': str(self.job.getRenderSettingCRF()),
            'preset': str(self.job.getRenderSettingPreset())
        }

        if v_codec == 'libsvtav1':
            encoder_options['svtav1-params'] = 'tune=0:enable-variance-boost=1:variance-boost-strength=2:film-grain=8'

        out_v_stream.options = encoder_options
        out_a_stream = None

        if has_audio:
            a_codec = self.job.getRenderSettingAudioCodec()
            in_rate = a_in_stream.codec_context.sample_rate if a_in_stream.codec_context else 44100
            a_rate = AudioCodecHelper.get_sample_rate(a_codec, in_rate)

            out_a_stream = out_container.add_stream(a_codec, rate=a_rate)
            out_a_stream.bit_rate = int(self.job.getRenderSettingAudioBitrate()) * 1000
            out_a_stream.format = AudioCodecHelper.get_sample_format(a_codec)

        return out_container, out_v_stream, out_a_stream

    def _build_audio_graph(self, a_in_stream):
        """
        Constructs and configures the PyAV audio filter graph.
        """
        a_graph = av.filter.Graph()
        a_ctx = a_in_stream.codec_context
        a_rate = a_ctx.sample_rate or 44100
        a_fmt = a_ctx.format.name if a_ctx.format else 's16'
        try:
            a_channels = a_ctx.channels or 2
        except AttributeError:
            a_channels = len(a_ctx.layout.channels) if hasattr(a_ctx, 'layout') and a_ctx.layout else 2

        abuffer_args = f"time_base=1/{a_rate}:sample_rate={a_rate}:sample_fmt={a_fmt}:channel_layout={a_channels}c"
        a_src = a_graph.add('abuffer', abuffer_args)

        a_codec = self.job.getRenderSettingAudioCodec()
        target_sample_rate = AudioCodecHelper.get_sample_rate(a_codec, a_rate)
        target_audio_fmt = AudioCodecHelper.get_sample_format(a_codec)

        a_fmt_node = a_graph.add('aformat', f'sample_fmts={target_audio_fmt}:sample_rates={target_sample_rate}')
        a_sink = a_graph.add('abuffersink')

        a_src.link_to(a_fmt_node)
        a_fmt_node.link_to(a_sink)
        a_graph.configure()
        return a_graph

    def _encode_and_mux_video_frame(self, out_frame, out_v_stream, muxer, pass_state: PassState):
        if not pass_state.v_configured:
            out_v_stream.width = out_frame.width
            out_v_stream.height = out_frame.height
            out_v_stream.pix_fmt = out_frame.format.name
            pass_state.v_configured = True

        out_frame.pict_type = av.video.frame.PictureType.NONE
        out_frame.time_base = pass_state.v_time_base
        out_frame.pts = pass_state.v_pts_offset
        pass_state.v_pts_offset += 1

        for enc_packet in out_v_stream.encode(out_frame):
            muxer.mux_video_packet(enc_packet, is_audio_configured=pass_state.a_configured)

    def _encode_and_mux_audio_frame(self, out_a_frame, out_a_stream, muxer, pass_state: PassState):
        if not pass_state.a_configured:
            out_a_stream.format = out_a_frame.format.name
            pass_state.a_time_base = Fraction(1, out_a_frame.sample_rate)
            pass_state.a_configured = True

        out_a_frame.time_base = pass_state.a_time_base
        out_a_frame.pts = pass_state.a_pts_offset
        pass_state.a_pts_offset += out_a_frame.samples

        for enc_packet in out_a_stream.encode(out_a_frame):
            muxer.mux_audio_packet(enc_packet, is_video_configured=pass_state.v_configured)

    def _pull_and_process_video_graph(self, v_graph, out_v_stream, muxer, pass_state: PassState,
                                      is_final_pass, overall_total_seconds, totalSeconds, current_pass):
        try:
            while True:
                out_frame = v_graph.pull()
                pass_state.frames_processed_pass += 1
                pass_state.rendered_seconds = pass_state.frames_processed_pass / pass_state.fps_float

                if pass_state.frames_processed_pass % 10 == 0:
                    self._emit_render_progress(pass_state, current_pass, totalSeconds, overall_total_seconds, is_final_pass, muxer)

                if is_final_pass:
                    self._encode_and_mux_video_frame(out_frame, out_v_stream, muxer, pass_state)
        except (av.error.BlockingIOError, av.error.EOFError):
            pass

    def _pull_and_process_audio_graph(self, a_graph, out_a_stream, muxer, pass_state: PassState):
        try:
            while True:
                out_a_frame = a_graph.pull()
                self._encode_and_mux_audio_frame(out_a_frame, out_a_stream, muxer, pass_state)
        except (av.error.BlockingIOError, av.error.EOFError):
            pass

    @staticmethod
    def _resolve_frame_time(frame, v_in_stream, packet_time_s, fallback_start_s):
        current_time = frame.time
        if current_time is None:
            if frame.pts is not None and v_in_stream.time_base is not None:
                current_time = float(frame.pts * v_in_stream.time_base)
            elif packet_time_s is not None:
                current_time = packet_time_s
            else:
                current_time = fallback_start_s
        return current_time

    def _flush_filters_and_encoders(self, v_graph, a_graph, out_v_stream, out_a_stream,
                                    muxer, pass_state: PassState, is_final_pass, has_audio,
                                    overall_total_seconds, totalSeconds, current_pass):
        """
        Handles filter graph flushing and encoder flushing cleanly.
        """
        self._log(f"Sending EOF signal to video filter in Pass {current_pass} for flushing...")
        v_graph.push(None)
        self._pull_and_process_video_graph(
            v_graph, out_v_stream, muxer, pass_state, is_final_pass,
            overall_total_seconds, totalSeconds, current_pass
        )
        self._log(f"Video filter flush successfully completed in pass {current_pass}. Final frames count: {pass_state.frames_processed_pass}")

        if is_final_pass and out_v_stream:
            self._log("Flushing video encoder...")
            for enc_packet in out_v_stream.encode(None):
                muxer.mux_video_packet(enc_packet, is_audio_configured=pass_state.a_configured)

        if is_final_pass and has_audio:
            self._log("Flushing audio filter...")
            a_graph.push(None)
            self._pull_and_process_audio_graph(a_graph, out_a_stream, muxer, pass_state)

            if out_a_stream:
                self._log("Flushing audio encoder...")
                for enc_packet in out_a_stream.encode(None):
                    muxer.mux_audio_packet(enc_packet, is_video_configured=pass_state.v_configured)

        self._emit_render_progress(pass_state, current_pass, totalSeconds, overall_total_seconds, is_final_pass, muxer)

    def _run_pass(self, srcPath, tgtPath, sections, current_pass, total_passes,
                  deshake_state, deshakeFile, videoProps, totalSeconds, overall_total_seconds):
        from classes.Functions import Functions
        container = None
        out_container = None
        v_graph, a_graph = None, None

        try:
            self._log(f"--- Starting Loop for Pass {current_pass} of {total_passes} ---")

            open_options = {
                'err_detect': 'ignore_err',
                'fflags': '+discardcorrupt+genpts'
            }
            container = av.open(srcPath, options=open_options)
            v_in_stream = next((s for s in container.streams if s.type == 'video'), None)
            a_in_stream = next((s for s in container.streams if s.type == 'audio'), None)

            if v_in_stream and v_in_stream.codec_context:
                v_in_stream.codec_context.options['err_detect'] = 'ignore_err'
            if a_in_stream and a_in_stream.codec_context:
                a_in_stream.codec_context.options['err_detect'] = 'ignore_err'

            self._log(f"Stream Properties - Width: {v_in_stream.width}, Height: {v_in_stream.height}, Format: {v_in_stream.format.name if v_in_stream.format else 'None'}")

            has_audio = a_in_stream is not None
            v_in_stream.thread_type = 'AUTO'
            if has_audio:
                a_in_stream.thread_type = 'AUTO'

            fps = v_in_stream.average_rate
            if not fps or fps.numerator == 0:
                fps = Fraction(25, 1)

            is_final_pass = (current_pass == total_passes)
            stream_start_s = float(v_in_stream.start_time * v_in_stream.time_base) if v_in_stream.start_time is not None else 0.0
            self._log(f"Video Stream absolute start_time offset: {stream_start_s}s")

            if current_pass == 2 and deshake_state:
                if not os.path.exists(deshakeFile):
                    raise Exception(f"Critical: TRF file missing after Pass 1! Path: {deshakeFile}")
                size = os.path.getsize(deshakeFile)
                self._log(f"TRF file found for Pass 2. Size: {size} bytes")

            out_v_stream, out_a_stream = None, None
            muxer = None

            if is_final_pass:
                out_container, out_v_stream, out_a_stream = self._setup_output_streams(
                    tgtPath, fps, has_audio, a_in_stream
                )
                muxer = PacketMuxer(out_container, has_audio)

            # Build video filter graph
            v_graph, _, _ = self._build_video_graph(
                v_in_stream, is_final_pass, deshake_state, current_pass, deshakeFile
            )

            if has_audio and is_final_pass:
                a_graph = self._build_audio_graph(a_in_stream)

            pass_state = PassState(fps)

            # --- MULTI-SECTION DEMUXING LOOP ---
            for sec_idx, section in enumerate(sections):
                if self._is_canceled:
                    break

                start_s = Functions.HMSToTimestamp(section[0], True) + stream_start_s
                end_s = Functions.HMSToTimestamp(section[1], True) + stream_start_s

                if start_s >= end_s:
                    self._log(f"Warning: Section {sec_idx+1}/{len(sections)} has 0 duration ({start_s}s to {end_s}s). Skipping.")
                    continue

                self._log(f"Processing section {sec_idx+1}/{len(sections)}: {start_s}s to {end_s}s (Absolute)")
                target_pts = int(start_s / float(v_in_stream.time_base))

                try:
                    container.seek(target_pts, backward=True, any_frame=False, stream=v_in_stream)
                except Exception as seek_err:
                    self._log(f"Warning: Seek error before section {sec_idx+1}: {seek_err}")

                if v_in_stream.codec_context:
                    try:
                        v_in_stream.codec_context.flush_buffers()
                    except Exception:
                        pass
                if has_audio and a_in_stream.codec_context:
                    try:
                        a_in_stream.codec_context.flush_buffers()
                    except Exception:
                        pass

                streams_to_read = [v_in_stream]
                if has_audio and is_final_pass:
                    streams_to_read.append(a_in_stream)

                section_v_done = False
                section_a_done = False if (has_audio and is_final_pass) else True

                demux_iter = container.demux(streams_to_read)
                while not self._is_canceled and not (section_v_done and section_a_done):
                    while self._is_paused:
                        time.sleep(0.1)

                    try:
                        packet = next(demux_iter)
                    except StopIteration:
                        break
                    except (av.FFmpegError, Exception) as demux_err:
                        self._log(f"Warning: Corrupted packet skipped in demuxer: {demux_err}")
                        continue

                    packet_time_s = None
                    if packet.dts is not None and packet.time_base is not None:
                        packet_time_s = float(packet.dts * packet.time_base)

                    try:
                        frames = packet.decode()
                    except (av.FFmpegError, Exception) as decode_err:
                        self._log(f"Warning: Skipping corrupted packet near timestamp {packet_time_s or 'unknown'}s: {decode_err}")
                        continue

                    for frame in frames:
                        current_time = self._resolve_frame_time(frame, v_in_stream, packet_time_s, start_s)

                        if current_time < start_s:
                            continue
                        if current_time > end_s:
                            if isinstance(frame, av.VideoFrame):
                                section_v_done = True
                            elif isinstance(frame, av.AudioFrame):
                                section_a_done = True
                            continue

                        if isinstance(frame, av.VideoFrame):
                            try:
                                v_graph.push(frame)
                                self._pull_and_process_video_graph(
                                    v_graph, out_v_stream, muxer, pass_state,
                                    is_final_pass, overall_total_seconds, totalSeconds, current_pass
                                )
                            except (av.FFmpegError, Exception) as filter_err:
                                self._log(f"Warning: Video filter graph error at {current_time}s: {filter_err}")

                        elif isinstance(frame, av.AudioFrame) and is_final_pass:
                            try:
                                a_graph.push(frame)
                                self._pull_and_process_audio_graph(a_graph, out_a_stream, muxer, pass_state)
                            except (av.FFmpegError, Exception) as filter_err:
                                self._log(f"Warning: Audio filter graph error at {current_time}s: {filter_err}")

            self._log(f"Pass {current_pass} normal extraction loop finished. Total frames processed so far: {pass_state.frames_processed_pass}")

            if current_pass == 1 and deshake_state and pass_state.frames_processed_pass == 0:
                raise Exception("Pass 1 finished but ZERO frames were pushed to the filter!")

            # --- FLUSHING ---
            if not self._is_canceled:
                self._flush_filters_and_encoders(
                    v_graph, a_graph, out_v_stream, out_a_stream, muxer,
                    pass_state, is_final_pass, has_audio,
                    overall_total_seconds, totalSeconds, current_pass
                )

        finally:
            self._log(f"Cleaning up memory references for Pass {current_pass}...")

            if container:
                container.close()
            if out_container:
                try:
                    out_container.close()
                except Exception as e:
                    self._log(f"Cleanup error on out_container.close(): {e}")

            if v_graph and hasattr(v_graph, 'nodes'):
                for node in v_graph.nodes:
                    try:
                        node.graph = None
                    except Exception:
                        pass

            del v_graph, a_graph
            gc.collect()

            if current_pass == 1 and deshake_state:
                time.sleep(0.5)
