import av
import av.filter
import av.logging
import os
import time
import traceback
import locale
import platform
import sys
import logging
import gc
import subprocess
from fractions import Fraction
from PyQt6.QtCore import pyqtSignal, QThread

av.logging.set_level(av.logging.TRACE)

class DirectFFmpegHandler(logging.Handler):
    def emit(self, record):
        msg = self.format(record)
        print(f"[FFMPEG] {msg}")
        sys.stdout.flush()

libav_logger = logging.getLogger('libav')
libav_logger.setLevel(logging.DEBUG)
libav_logger.handlers.clear()
direct_handler = DirectFFmpegHandler()
direct_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
libav_logger.addHandler(direct_handler)

class FFmpegThread(QThread):
    ffmpegStart = pyqtSignal('PyQt_PyObject')
    ffmpegProcess = pyqtSignal('PyQt_PyObject')
    ffmpegExit = pyqtSignal('PyQt_PyObject')

    def __init__(self, job, configPath):
        self.job = job
        self.configPath = configPath
        self._is_canceled = False
        self._is_paused = False
        self._debug_logs =[]
        QThread.__init__(self)

    def _log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        log_msg = f"[DEBUG PyCut FFmpegThread {timestamp}] {msg}"
        print(log_msg)
        sys.stdout.flush()
        self._debug_logs.append(log_msg)

    def cancel(self):
        self._is_canceled = True
        self._log("Render process canceled by user.")

    def pause(self, state: bool):
        self._is_paused = state
        self._log(f"Render process paused: {state}")

    def __del__(self):
        try:
            self.wait()
        except:
            pass

    def get_safe_ffmpeg_path(self, filepath):
        p = str(filepath)
        p = p.replace('\\', '/')
        return p

    def _force_c_locale(self):
        try:
            locale.setlocale(locale.LC_NUMERIC, 'C')
            os.environ["LC_NUMERIC"] = "C"
            self._log("Successfully enforced 'C' locale for safe float parsing.")
        except Exception as e:
            self._log(f"Warning: Could not enforce 'C' locale: {e}")

    def _check_vidstab_availability(self):
        try:
            result = subprocess.run(["ffmpeg", "-filters"], capture_output=True, text=True)
            if "vidstab" not in result.stdout:
                self._log("System FFmpeg is NOT compiled with libvidstab! Check installation.")
                return False

            g = av.filter.Graph()
            g.add('vidstabdetect', result='dummy.trf')
            g.add('vidstabtransform', input='dummy.trf')
            self._log("vid.stab filters are natively available in PyAV.")
            return True
        except Exception as e:
            self._log(f"vid.stab filter check failed: {e}")
            return False

    def run(self):
        self._force_c_locale()

        self._log("=== SYSTEM INFO DUMP ===")
        self._log(f"OS: {platform.system()} {platform.release()} {platform.version()} {platform.machine()}")
        self._log(f"Python: {sys.version.replace(chr(10), ' ')}")
        self._log(f"PyAV Version: {av.__version__}")
        try:
            self._log(f"PyAV Library Versions: {av.library_versions}")
        except Exception as e:
            self._log(f"PyAV Library Versions: unavailable ({e})")
        self._log("========================")

        job = self.job
        deshakeFile = False
        srcPath = job.getSrcFilePathLong()
        tgtPath = job.getTgtFilePathLong()
        self._log(f"Starting Job ID {job.getID()} | Source: {srcPath} | Target: {tgtPath}")

        if not os.path.isfile(srcPath):
            err = f'Input file "{srcPath}" does not exist.'
            self._log(err)
            self.ffmpegExit.emit([job, 1, b'', err.encode('utf-8'), deshakeFile])
            return

        try:
            from classes.Functions import Functions
            videoProps = Functions.getVideoProperties(srcPath)
            if not videoProps:
                raise Exception("Probing the target file failed. File might be corrupted.")

            deshake_state = job.getFilterDeshakeState()
            if deshake_state and not self._check_vidstab_availability():
                raise Exception("vidstab filters missing! Please disable Deshake.")

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

            for render_pass in range(1, render_passes + 1):
                if self._is_canceled: break

                if render_pass == 1 and deshake_state and os.path.exists(deshakeFile):
                    self._log("Removing old TRF file before Pass 1.")
                    os.remove(deshakeFile)

                self.ffmpegProcess.emit([['pass_info', f'Pass {render_pass}/{render_passes}'], self.job, overall_total_seconds])
                self._run_pass(srcPath, tgtPath, sections, render_pass, render_passes, deshake_state, deshakeFile, videoProps, totalSeconds, overall_total_seconds)

            if self._is_canceled:
                if os.path.exists(tgtPath):
                    os.remove(tgtPath)
                self.ffmpegExit.emit([job, 1, b'', b'Render process canceled by user.', deshakeFile])
            else:
                self.ffmpegExit.emit([job, 0, b'Render complete', b'', deshakeFile])

        except Exception as e:
            full_traceback = traceback.format_exc()
            self._log(f"Critical error in FFmpegThread:\n{full_traceback}")
            debug_info = "\n".join(self._debug_logs)
            err_msg = f"Error:\n{full_traceback}\n\n--- DEBUG LOGS ---\n{debug_info}".encode('utf-8')
            self.ffmpegExit.emit([job, 1, b'', err_msg, deshakeFile])

    def _build_video_graph(self, attempt_config, v_in_stream, is_final_pass, deshake_state, current_pass, deshakeFile):
        self._log(f"Building video filter graph (Pass {current_pass}, Final: {is_final_pass}) with Config: {attempt_config['name']}")
        v_graph = av.filter.Graph()

        fps = v_in_stream.average_rate
        if not fps or fps.numerator == 0 or fps.denominator == 0:
            fps_str = "25/1"
        else:
            fps_str = f"{fps.numerator}/{fps.denominator}"

        tb = v_in_stream.time_base
        if not tb or tb.numerator == 0 or tb.denominator == 0:
            tb_str = "1/25"
        else:
            tb_str = f"{tb.numerator}/{tb.denominator}"

        sar = v_in_stream.sample_aspect_ratio
        if not sar or sar.numerator == 0 or sar.denominator == 0:
            sar_str = "1/1"
        else:
            sar_str = f"{sar.numerator}/{sar.denominator}"

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
            node = None

            if f_type == 'deshake' and deshake_state:
                if current_pass == 1:
                    kwargs = {'result': str(deshakeFile)}
                    if attempt_config['vidstab_args_type'] == 'full':
                        kwargs.update({'stepsize': '16', 'shakiness': '7', 'accuracy': '10'})
                    elif attempt_config['vidstab_args_type'] == 'safe':
                        kwargs.update({'stepsize': '32', 'shakiness': '5'})
                    self._log(f"Adding vidstabdetect with kwargs: {kwargs}")
                    node = v_graph.add('vidstabdetect', **kwargs)
                    last_node.link_to(node)
                    last_node = node
                    break

                elif current_pass == 2:
                    kwargs = {'input': str(deshakeFile)}
                    if attempt_config['vidstab_args_type'] == 'full':
                        kwargs.update({'smoothing': '15', 'optzoom': '1', 'interpol': 'bicubic'})
                    elif attempt_config['vidstab_args_type'] == 'safe':
                        kwargs.update({'smoothing': '10', 'optzoom': '1', 'interpol': 'bilinear'})
                    self._log(f"Adding vidstabtransform with kwargs: {kwargs}")
                    node = v_graph.add('vidstabtransform', **kwargs)
                    last_node.link_to(node)
                    last_node = node

                    if attempt_config.get('use_unsharp', False):
                        sharp_kwargs = {'luma_msize_x': '5', 'luma_msize_y': '5', 'luma_amount': '0.5'}
                        sharp_node = v_graph.add('unsharp', **sharp_kwargs)
                        last_node.link_to(sharp_node)
                        last_node = sharp_node
                    node = None

            elif f_type == 'deinterlace' and self.job.getFilterDeinterlaceState():
                node = v_graph.add(self.job.getFilterDeinterlaceDeinterlacer())
            elif f_type == 'resize' and self.job.getFilterResizeState():
                w = self.job.getFilterResizeWidth() or -1
                h = self.job.getFilterResizeHeight() or -1
                node = v_graph.add('scale', width=str(w), height=str(h))
                last_node.link_to(node)
                last_node = node
                node = v_graph.add('setsar', sar='1/1')
            elif f_type == 'rotate':
                rotate = self.job.getFilterRotate()
                if rotate == 90:
                    node = v_graph.add('transpose', dir='1')
                elif rotate == -90:
                    node = v_graph.add('transpose', dir='2')
                elif rotate == 180:
                    node1 = v_graph.add('transpose', dir='2')
                    last_node.link_to(node1)
                    last_node = node1
                    node = v_graph.add('transpose', dir='2')
            elif f_type == 'crop' and self.job.getFilterCropState():
                t = self.job.getFilterCropT() or 0
                b = self.job.getFilterCropB() or 0
                l = self.job.getFilterCropL() or 0
                r = self.job.getFilterCropR() or 0
                node = v_graph.add('crop', out_w=f"iw-{l}-{r}", out_h=f"ih-{t}-{b}", x=str(l), y=str(t))

            if node:
                last_node.link_to(node)
                last_node = node

        if is_final_pass:
            format_node = v_graph.add('format', pix_fmts='yuv420p')
            last_node.link_to(format_node)
            last_node = format_node

        v_sink = v_graph.add('buffersink')
        last_node.link_to(v_sink)
        self._log("Configuring video graph...")
        v_graph.configure()
        self._log("Video graph configured successfully.")
        return v_graph, v_src, v_sink

    def _run_pass(self, srcPath, tgtPath, sections, current_pass, total_passes, deshake_state, deshakeFile, videoProps, totalSeconds, overall_total_seconds):
        from classes.Functions import Functions
        container = None
        out_container = None
        v_graph, v_src, v_sink = None, None, None
        a_graph, a_src, a_fmt_node, a_sink = None, None, None, None

        packet_queue =[]
        frame = None
        out_frame = None
        packet = None
        enc_packet = None
        out_a_frame = None
        frames_processed_pass = 0

        try:
            self._log(f"--- Starting Loop for Pass {current_pass} of {total_passes} ---")
            container = av.open(srcPath)
            v_in_stream = next((s for s in container.streams if s.type == 'video'), None)
            a_in_stream = next((s for s in container.streams if s.type == 'audio'), None)

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

                try:
                    with open(deshakeFile, 'rb') as f:
                        head = f.read(64)
                        self._log(f"TRF HEX DUMP (first 64 bytes): {head.hex().upper()}")
                        ascii_text = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in head)
                        self._log(f"TRF ASCII DUMP: {ascii_text}")
                except Exception as e:
                    self._log(f"Failed to read TRF file for debug: {e}")

            out_v_stream = None
            out_a_stream = None
            if is_final_pass:
                out_container = av.open(tgtPath, 'w')
                out_v_stream = out_container.add_stream(self.job.getRenderSettingVideoCodec(), rate=fps)
                out_v_stream.options = {
                    'crf': str(self.job.getRenderSettingCRF()),
                    'preset': str(self.job.getRenderSettingPreset())
                }
                if has_audio:
                    a_rate = a_in_stream.codec_context.sample_rate if a_in_stream.codec_context else 44100
                    out_a_stream = out_container.add_stream(self.job.getRenderSettingAudioCodec(), rate=a_rate)
                    out_a_stream.bit_rate = int(self.job.getRenderSettingAudioBitrate()) * 1000

            attempts =[
                {'name': '1. Standard Escaping + Tuning', 'vidstab_args_type': 'full', 'use_unsharp': True},
                {'name': '2. Safe Fallback', 'vidstab_args_type': 'safe', 'use_unsharp': False},
                {'name': '3. Minimal Fallback', 'vidstab_args_type': 'minimal', 'use_unsharp': False},
            ]
            last_graph_error = None

            for idx, attempt in enumerate(attempts):
                try:
                    self._log(f"Attempting graph config {idx+1}...")
                    v_graph, v_src, v_sink = self._build_video_graph(attempt, v_in_stream, is_final_pass, deshake_state, current_pass, deshakeFile)
                    self._log(f"Graph configuration {idx+1}/3 SUCCESS.")
                    break
                except Exception as e:
                    self._log(f"Graph configuration {idx+1}/3 failed: {e}")
                    last_graph_error = e

                    del v_graph, v_src, v_sink
                    v_graph, v_src, v_sink = None, None, None
                    gc.collect()

            if not v_graph:
                raise Exception(f"Video filter graph could not be initialized in pass {current_pass}!\nLast internal error:\n{last_graph_error}")

            if has_audio and is_final_pass:
                a_graph = av.filter.Graph()
                a_ctx = a_in_stream.codec_context
                a_rate = a_ctx.sample_rate or 44100
                a_fmt = a_ctx.format.name if a_ctx.format else 's16'
                try:
                    a_channels = a_ctx.channels or 2
                except AttributeError:
                    a_channels = len(a_ctx.layout.channels) if hasattr(a_ctx, 'layout') and a_ctx.layout else 2

                try:
                    layout = a_ctx.layout.name if (hasattr(a_ctx, 'layout') and a_ctx.layout and a_ctx.layout.name) else f"{a_channels}c"
                except AttributeError:
                    layout = f"{a_channels}c"
                abuffer_args = f"time_base=1/{a_rate}:sample_rate={a_rate}:sample_fmt={a_fmt}:channel_layout={layout}"
                a_src = a_graph.add('abuffer', abuffer_args)
                a_fmt_node = a_graph.add('aformat', 'sample_fmts=fltp')
                a_sink = a_graph.add('abuffersink')
                a_src.link_to(a_fmt_node)
                a_fmt_node.link_to(a_sink)
                a_graph.configure()

            out_v_configured = False
            out_a_configured = False
            v_time_base = Fraction(fps.denominator, fps.numerator)
            a_time_base = None
            v_pts_offset = 0
            a_pts_offset = 0
            rendered_seconds = 0.0
            header_written = False
            fps_float = float(fps) if fps else 25.0

            for sec_idx, section in enumerate(sections):
                if self._is_canceled: break

                start_s = Functions.HMSToTimestamp(section[0], True) + stream_start_s
                end_s = Functions.HMSToTimestamp(section[1], True) + stream_start_s

                self._log(f"Processing section {sec_idx+1}/{len(sections)}: {start_s}s to {end_s}s (Absolute)")
                target_pts = int(start_s / float(v_in_stream.time_base))
                container.seek(target_pts, backward=True, any_frame=False, stream=v_in_stream)
                streams_to_read = [v_in_stream]
                if has_audio and is_final_pass:
                    streams_to_read.append(a_in_stream)

                for packet in container.demux(streams_to_read):
                    if self._is_canceled: break
                    while self._is_paused: time.sleep(0.1)

                    packet_time_s = None
                    if packet.dts is not None:
                        packet_time_s = float(packet.dts * packet.time_base)
                        if packet_time_s > end_s + 5.0:
                            break

                    for frame in packet.decode():
                        current_time = frame.time
                        if current_time is None:
                            if frame.pts is not None and v_in_stream.time_base is not None:
                                current_time = float(frame.pts * v_in_stream.time_base)
                            elif packet_time_s is not None:
                                current_time = packet_time_s
                            else:
                                current_time = start_s

                        if current_time < start_s: continue
                        if current_time > end_s: break

                        if isinstance(frame, av.VideoFrame):
                            v_graph.push(frame)
                            try:
                                while True:
                                    out_frame = v_graph.pull()
                                    frames_processed_pass += 1
                                    rendered_seconds += (1.0 / fps_float)
                                    if frames_processed_pass % 10 == 0:
                                        pass_offset = totalSeconds if current_pass == 2 else 0
                                        current_progress = pass_offset + rendered_seconds
                                        self.ffmpegProcess.emit([['out_time_ms', str(int(current_progress * 1000000))], self.job, overall_total_seconds])
                                    if not is_final_pass:
                                        continue
                                    if not out_v_configured:
                                        out_v_stream.width = out_frame.width
                                        out_v_stream.height = out_frame.height
                                        out_v_stream.pix_fmt = out_frame.format.name
                                        out_v_configured = True
                                    out_frame.pict_type = av.video.frame.PictureType.NONE
                                    out_frame.time_base = v_time_base
                                    out_frame.pts = v_pts_offset
                                    v_pts_offset += 1
                                    for enc_packet in out_v_stream.encode(out_frame):
                                        if not header_written:
                                            if has_audio and not out_a_configured:
                                                packet_queue.append(enc_packet)
                                            else:
                                                for p in packet_queue:
                                                    out_container.mux(p)
                                                packet_queue.clear()
                                                header_written = True
                                                out_container.mux(enc_packet)
                                        else:
                                            out_container.mux(enc_packet)
                            except av.error.BlockingIOError:
                                pass
                            except av.error.EOFError:
                                pass
                        elif isinstance(frame, av.AudioFrame) and is_final_pass:
                            a_graph.push(frame)
                            try:
                                while True:
                                    out_a_frame = a_graph.pull()
                                    if not out_a_configured:
                                        out_a_stream.format = out_a_frame.format.name
                                        try:
                                            out_a_stream.channels = out_a_frame.channels
                                        except AttributeError:
                                            if hasattr(out_a_frame, 'layout') and out_a_frame.layout is not None:
                                                try:
                                                    out_a_stream.layout = out_a_frame.layout.name
                                                except Exception:
                                                    try:
                                                        out_a_stream.channels = len(out_a_frame.layout.channels)
                                                    except Exception:
                                                        pass
                                        a_time_base = Fraction(1, out_a_frame.sample_rate)
                                        out_a_configured = True
                                    out_a_frame.time_base = a_time_base
                                    out_a_frame.pts = a_pts_offset
                                    a_pts_offset += out_a_frame.samples
                                    for enc_packet in out_a_stream.encode(out_a_frame):
                                        if not header_written:
                                            if not out_v_configured:
                                                packet_queue.append(enc_packet)
                                            else:
                                                for p in packet_queue:
                                                    out_container.mux(p)
                                                packet_queue.clear()
                                                header_written = True
                                                out_container.mux(enc_packet)
                                        else:
                                            out_container.mux(enc_packet)
                            except av.error.BlockingIOError:
                                pass
                            except av.error.EOFError:
                                pass

            self._log(f"Pass {current_pass} normal extraction loop finished. Total frames processed so far: {frames_processed_pass}")

            if current_pass == 1 and deshake_state and frames_processed_pass == 0:
                raise Exception("Pass 1 finished but ZERO frames were pushed to the filter! Check the video timestamps/duration. The TRF file is empty.")

            if not self._is_canceled:
                self._log(f"Sending EOF signal to video filter in Pass {current_pass} for flushing...")
                v_graph.push(None)
                try:
                    while True:
                        out_frame = v_graph.pull()
                        frames_processed_pass += 1
                        if is_final_pass:
                            out_frame.pict_type = av.video.frame.PictureType.NONE
                            out_frame.time_base = v_time_base
                            out_frame.pts = v_pts_offset
                            v_pts_offset += 1
                            for enc_packet in out_v_stream.encode(out_frame):
                                if not header_written:
                                    for p in packet_queue: out_container.mux(p)
                                    packet_queue.clear()
                                    header_written = True
                                out_container.mux(enc_packet)
                except (av.error.BlockingIOError, av.error.EOFError):
                    self._log(f"Video filter flush successfully completed in pass {current_pass}. Final frames count: {frames_processed_pass}")

                if is_final_pass and out_v_stream:
                    self._log("Flushing video encoder...")
                    for enc_packet in out_v_stream.encode(None):
                        if not header_written:
                            for p in packet_queue: out_container.mux(p)
                            packet_queue.clear()
                            header_written = True
                        out_container.mux(enc_packet)

                if is_final_pass and has_audio:
                    self._log("Flushing audio filter...")
                    a_graph.push(None)
                    try:
                        while True:
                            out_a_frame = a_graph.pull()
                            out_a_frame.time_base = a_time_base
                            out_a_frame.pts = a_pts_offset
                            a_pts_offset += out_a_frame.samples
                            for enc_packet in out_a_stream.encode(out_a_frame):
                                if not header_written:
                                    for p in packet_queue: out_container.mux(p)
                                    packet_queue.clear()
                                    header_written = True
                                out_container.mux(enc_packet)
                    except (av.error.BlockingIOError, av.error.EOFError):
                        pass
                    if out_a_stream:
                        self._log("Flushing audio encoder...")
                        for enc_packet in out_a_stream.encode(None):
                            if not header_written:
                                for p in packet_queue: out_container.mux(p)
                                packet_queue.clear()
                                header_written = True
                            out_container.mux(enc_packet)
        finally:
            self._log(f"Cleaning up memory references for Pass {current_pass}...")

            frame = None
            out_frame = None
            packet = None
            enc_packet = None
            out_a_frame = None
            packet_queue.clear()

            if container:
                container.close()
            if out_container:
                try:
                    out_container.close()
                except Exception as e:
                    self._log(f"Cleanup error on out_container.close(): {e}")

            del v_graph
            del v_src
            del v_sink
            del a_graph
            del a_src
            del a_fmt_node
            del a_sink
            gc.collect()

            if current_pass == 1 and deshake_state:
                self._log("Giving OS 3 seconds to fully close the C-level file handles...")
                time.sleep(3.0)
