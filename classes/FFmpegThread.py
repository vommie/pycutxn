import av
import av.filter
import av.logging
import os
import time
import traceback
from fractions import Fraction
from PyQt6.QtCore import pyqtSignal, QThread
import gc
import subprocess  # Neu: Für externe FFmpeg-Prüfung

# Verhindert, dass FFmpeg den Terminal mit Info-Spam füllt, lässt aber kritische Fehler durch.
av.logging.set_level(av.logging.ERROR)

class FFmpegThread(QThread):
    ffmpegStart = pyqtSignal('PyQt_PyObject')
    ffmpegProcess = pyqtSignal('PyQt_PyObject')
    ffmpegExit = pyqtSignal('PyQt_PyObject')

    def __init__(self, job, configPath):
        self.job = job
        self.configPath = configPath
        self._is_canceled = False
        self._is_paused = False
        self._debug_logs = []
        QThread.__init__(self)

    def _log(self, msg):
        """Hilfsfunktion für exzessives Debug-Logging"""
        timestamp = time.strftime("%H:%M:%S")
        log_msg = f"[DEBUG PyCut FFmpegThread {timestamp}] {msg}"
        print(log_msg)
        self._debug_logs.append(log_msg)

    def cancel(self):
        """Bricht den Render-Vorgang sicher ab"""
        self._is_canceled = True
        self._log("Render-Vorgang wurde durch User abgebrochen.")

    def pause(self, state: bool):
        """Pausiert den Render-Vorgang"""
        self._is_paused = state
        self._log(f"Render-Vorgang pausiert: {state}")

    def __del__(self):
        try:
            self.wait()
        except:
            pass

    def get_safe_ffmpeg_path(self, filepath):
        """
        Korrektes und robustes Escaping von Dateipfaden für FFmpeg Filtergraphen.
        Verhindert "Invalid argument" (Errno 22) Fehler sicher über alle Betriebssysteme.
        """
        p = str(filepath)
        # Backslashes in Forward-Slashes umwandeln (FFmpeg versteht das auch unter Windows einwandfrei)
        p = p.replace('\\', '/')
        # WICHTIG: Doppelpunkte (Laufwerksbuchstaben wie C:) maskieren, da FFmpeg ':' als Trenner sieht!
        p = p.replace(':', r'\:')
        # Kommas maskieren (werden teils als Trenner in Filterketten gewertet)
        p = p.replace(',', r'\,')
        return p

    def _check_vidstab_availability(self):
        """Prüft im Vorfeld, ob die FFmpeg-Installation vid.stab überhaupt unterstützt."""
        try:
            # Externe Kommandozeilen-Prüfung (optional, für Bestätigung)
            result = subprocess.run(["ffmpeg", "-filters"], capture_output=True, text=True)
            if "vidstab" not in result.stdout:
                self._log("FFmpeg ist NICHT mit libvidstab kompiliert! Überprüfe Installation.")
                return False

            g = av.filter.Graph()
            # Teste Initialisierung von Detect
            g.add('vidstabdetect', 'result=dummy.trf')
            # Teste Initialisierung von Transform
            g.add('vidstabtransform', 'input=dummy.trf')
            self._log("vid.stab Filter sind in dieser PyAV/FFmpeg-Version nativ verfügbar.")
            return True
        except av.error.ValueError as e:
            self._log(f"vid.stab Filter Check fehlgeschlagen (Filter fehlt): {e}")
            return False
        except Exception as e:
            self._log(f"Unbekannter Fehler beim vid.stab Check: {e}")
            return False

    def run(self):
        job = self.job
        deshakeFile = False
        srcPath = job.getSrcFilePathLong()
        tgtPath = job.getTgtFilePathLong()
        self._log(f"Starte Job ID {job.getID()} | Source: {srcPath} | Target: {tgtPath}")
        if not os.path.isfile(srcPath):
            err = f'Input file "{srcPath}" does not exist.'
            self._log(err)
            self.ffmpegExit.emit([job, 1, b'', err.encode('utf-8'), deshakeFile])
            return
        try:
            from classes.Functions import Functions
            videoProps = Functions.getVideoProperties(srcPath)
            if not videoProps:
                raise Exception("Probing the target file failed. Datei eventuell defekt.")
            deshake_state = job.getFilterDeshakeState()
            # Guard-Clause: Verhindere Absturz tief im Pipeline-Loop
            if deshake_state and not self._check_vidstab_availability():
                raise Exception("Die Filter 'vidstabdetect' oder 'vidstabtransform' sind nicht verfügbar!\n"
                                "Deine FFmpeg/PyAV Version wurde ohne libvidstab kompiliert. "
                                "Bitte deaktiviere Deshake oder installiere eine kompatible FFmpeg-Version.")
            render_passes = 2 if deshake_state else 1
            sections = job.getSections()
            if not sections:
                raise Exception("No sections to render.")
            # Gesamtzeit für Progressbar berechnen
            totalSeconds = sum([Functions.HMSToTimestamp(s[1], True) - Functions.HMSToTimestamp(s[0], True) for s in sections])
            overall_total_seconds = totalSeconds * render_passes
            self.ffmpegStart.emit([job, overall_total_seconds, self])
            if deshake_state:
                if not os.path.isdir(self.configPath):
                    os.makedirs(self.configPath, exist_ok=True)
                # Dateiname sicher benennen
                deshakeFile = os.path.abspath(os.path.join(self.configPath, f'job_{job.getID()}_transforms.trf'))
                self._log(f"Deshake TRF Datei wird gespeichert unter: {deshakeFile}")
            for render_pass in range(1, render_passes + 1):
                if self._is_canceled: break
                # Vor Pass 1 alte Deshake-Dateien löschen, um Dateisperren (File-Locks) zu vermeiden
                if render_pass == 1 and deshake_state and os.path.exists(deshakeFile):
                    self._log("Entferne alte TRF Datei vor Pass 1.")
                    os.remove(deshakeFile)
                # UI Feedback senden: Welcher Pass läuft gerade?
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
            self._log(f"Kritischer Fehler im FFmpegThread:\n{full_traceback}")
            # Packe alle Debug-Logs in den Error-String, damit der User sie beim Doppelklick im UI-Logfenster sieht!
            debug_info = "\n".join(self._debug_logs)
            err_msg = f"Fehler:\n{full_traceback}\n\n--- DEBUG LOGS ---\n{debug_info}".encode('utf-8')
            self.ffmpegExit.emit([job, 1, b'', err_msg, deshakeFile])

    def _build_video_graph(self, attempt_config, v_in_stream, is_final_pass, deshake_state, current_pass, deshakeFile):
        """
        Baut den Video-Filtergraphen auf. Nutzt robustes String-Parsing, um FFmpeg-Bugs zu umgehen.
        """
        self._log(f"Erstelle Video-Filtergraph (Pass {current_pass}, Final: {is_final_pass}) mit Config: {attempt_config['name']}")
        v_graph = av.filter.Graph()
        v_src = v_graph.add_buffer(template=v_in_stream)
        last_node = v_src
        filterPositions = self.job.getFilterPositions()
        sorted_positions = sorted(filterPositions.keys(), key=lambda x: int(x))
        for position in sorted_positions:
            f_type = filterPositions.get(position)
            node = None
            if f_type == 'deshake' and deshake_state:
                safe_path = self.get_safe_ffmpeg_path(deshakeFile)
                self._log(f"Verwende maskierten TRF Pfad: {safe_path}")
                # Neu: Für Pass 2 in Config-Verzeichnis wechseln und relativen Pfad verwenden als Fallback
                if current_pass == 2:
                    original_cwd = os.getcwd()
                    os.chdir(self.configPath)
                    relative_path = os.path.basename(deshakeFile)
                    safe_path = self.get_safe_ffmpeg_path(relative_path)  # Relativer Pfad
                    self._log(f"Wechsle zu relativem Pfad für Pass 2: {safe_path}")
                if current_pass == 1:
                    # PASS 1: Analyse
                    if attempt_config['vidstab_args_type'] == 'full':
                        args = f'result={safe_path}:stepsize=16:shakiness=7:accuracy=10'  # Entfernt: Keine Quotes
                    elif attempt_config['vidstab_args_type'] == 'safe':
                        args = f'result={safe_path}:stepsize=32:shakiness=5'
                    else:
                        args = f'result={safe_path}'
                    self._log(f"Füge vidstabdetect hinzu mit Argumenten: {args}")
                    node = v_graph.add('vidstabdetect', args)
                    last_node.link_to(node)
                    last_node = node
                    self._log("Trunkiere Filtergraph nach vidstabdetect für schnellen Pass 1.")
                    break  # In Pass 1 brauchen wir nach Analyse keine Skalierung oder Cropping!
                elif current_pass == 2:
                    # PASS 2: Transformation
                    if attempt_config['vidstab_args_type'] == 'full':
                        args = f'input={safe_path}:smoothing=15:optzoom=1:interpol=bicubic'  # Entfernt: Keine Quotes
                    elif attempt_config['vidstab_args_type'] == 'safe':
                        args = f'input={safe_path}:smoothing=10:optzoom=1:interpol=bilinear'
                    else:
                        args = f'input={safe_path}'
                    self._log(f"Füge vidstabtransform hinzu mit Argumenten: {args}")
                    node = v_graph.add('vidstabtransform', args)
                    last_node.link_to(node)
                    last_node = node
                    if attempt_config.get('use_unsharp', False):
                        self._log("Füge Unsharp-Filter zur Kompensation der Glättungs-Unschärfe hinzu.")
                        sharp_node = v_graph.add('unsharp', "luma_msize_x=5:luma_msize_y=5:luma_amount=0.5")
                        last_node.link_to(sharp_node)
                        last_node = sharp_node
                    node = None  # Verhindert doppeltes Linken am Ende des Loops
                    # Neu: Zurück zum Original-Verzeichnis
                    if current_pass == 2:
                        os.chdir(original_cwd)
            elif f_type == 'deinterlace' and self.job.getFilterDeinterlaceState():
                deint_filter = self.job.getFilterDeinterlaceDeinterlacer()
                self._log(f"Füge Deinterlace hinzu: {deint_filter}")
                node = v_graph.add(deint_filter)
            elif f_type == 'resize' and self.job.getFilterResizeState():
                w = self.job.getFilterResizeWidth() or -1
                h = self.job.getFilterResizeHeight() or -1
                self._log(f"Füge Resize hinzu: {w}x{h}")
                node = v_graph.add('scale', f'{w}:{h}')
                last_node.link_to(node)
                last_node = node
                node = v_graph.add('setsar', '1/1')
            elif f_type == 'rotate':
                rotate = self.job.getFilterRotate()
                self._log(f"Füge Rotate hinzu: {rotate}")
                if rotate == 90:
                    node = v_graph.add('transpose', '1')
                elif rotate == -90:
                    node = v_graph.add('transpose', '2')
                elif rotate == 180:
                    node1 = v_graph.add('transpose', '2')
                    last_node.link_to(node1)
                    last_node = node1
                    node = v_graph.add('transpose', '2')
            elif f_type == 'crop' and self.job.getFilterCropState():
                t = self.job.getFilterCropT() or 0
                b = self.job.getFilterCropB() or 0
                l = self.job.getFilterCropL() or 0
                r = self.job.getFilterCropR() or 0
                crop_arg = f"iw-{l}-{r}:ih-{t}-{b}:{l}:{t}"
                self._log(f"Füge Crop hinzu: {crop_arg}")
                node = v_graph.add('crop', crop_arg)
            if node:
                last_node.link_to(node)
                last_node = node
        if is_final_pass:
            self._log("Füge Format-Filter (yuv420p) als Vorbereitung für Encoder hinzu.")
            format_node = v_graph.add('format', 'yuv420p')
            last_node.link_to(format_node)
            last_node = format_node
        v_sink = v_graph.add('buffersink')
        last_node.link_to(v_sink)
        self._log("Konfiguriere Video-Graph...")
        v_graph.configure()
        self._log("Video-Graph erfolgreich konfiguriert.")
        return v_graph, v_src, v_sink

    def _run_pass(self, srcPath, tgtPath, sections, current_pass, total_passes, deshake_state, deshakeFile, videoProps, totalSeconds, overall_total_seconds):
        from classes.Functions import Functions
        container = None
        out_container = None
        # Referenzen explizit festhalten für sauberen Garbage Collection Abbau am Ende
        v_graph, v_src, v_sink = None, None, None
        a_graph, a_src, a_fmt_node, a_sink = None, None, None, None
        try:
            self._log(f"--- Starte Loop für Pass {current_pass} von {total_passes} ---")
            container = av.open(srcPath)
            v_in_stream = next((s for s in container.streams if s.type == 'video'), None)
            a_in_stream = next((s for s in container.streams if s.type == 'audio'), None)
            has_audio = a_in_stream is not None
            v_in_stream.thread_type = 'AUTO'
            if has_audio:
                a_in_stream.thread_type = 'AUTO'
            fps = v_in_stream.average_rate
            if not fps or fps.numerator == 0:
                fps = Fraction(25, 1)
            is_final_pass = (current_pass == total_passes)
            # Prüfe VOR Pass 2 zwingend, ob Pass 1 die TRF-Datei erfolgreich geschrieben hat
            if current_pass == 2 and deshake_state:
                if not os.path.exists(deshakeFile):
                    raise Exception(f"Kritisch: TRF Datei fehlt nach Pass 1! Pfad: {deshakeFile}")
                size = os.path.getsize(deshakeFile)
                self._log(f"TRF Datei für Pass 2 gefunden. Groesse: {size} Bytes")
                if size == 0:
                    raise Exception(f"TRF Datei ist leer (0 Bytes)! Pass 1 hat keine Bewegungsdaten geschrieben. Video ist möglicherweise ein Standbild.")
            out_v_stream = None
            out_a_stream = None
            if is_final_pass:
                self._log(f"Öffne Output Container für finales Muxing: {tgtPath}")
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
            # --- FALLBACK ARCHITEKTUR FÜR VIDEO FILTERGRAPH ---
            # Testet 3 verschiedene Konfigurationen für Deshake/Filter Aufbau (Quality-Degradation-Fallback)
            attempts =[
                {'name': '1. Manuelles String-Escaping mit Tuning', 'vidstab_args_type': 'full', 'use_unsharp': True},
                {'name': '2. Sicheres Fallback ohne Tuning', 'vidstab_args_type': 'safe', 'use_unsharp': False},
                {'name': '3. Minimales Fallback ohne Parameter', 'vidstab_args_type': 'minimal', 'use_unsharp': False},
            ]
            last_graph_error = None
            for idx, attempt in enumerate(attempts):
                try:
                    v_graph, v_src, v_sink = self._build_video_graph(attempt, v_in_stream, is_final_pass, deshake_state, current_pass, deshakeFile)
                    break # Erfolgreich, Schleife abbrechen!
                except Exception as e:
                    self._log(f"Graph Konfiguration {idx+1}/3 fehlgeschlagen: {e}")
                    last_graph_error = e
                    # Speicher zwingend aufräumen, damit defekte Graphen sofort gekillt werden
                    v_graph, v_src, v_sink = None, None, None
                    gc.collect()
            if not v_graph:
                raise Exception(f"Video-Filtergraph konnte in Pass {current_pass} nicht initialisiert werden!\nLetzter interner Fehler:\n{last_graph_error}")
            # --- AUDIO FILTER GRAPH SETUP ---
            if has_audio and is_final_pass:
                self._log("Erstelle Audio-Filtergraph")
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
            frame_counter = 0
            packet_queue =[]
            header_written = False
            fps_float = float(fps) if fps else 25.0
            for sec_idx, section in enumerate(sections):
                if self._is_canceled: break
                start_s = Functions.HMSToTimestamp(section[0], True)
                end_s = Functions.HMSToTimestamp(section[1], True)
                self._log(f"Verarbeite Sektion {sec_idx+1}/{len(sections)}: {start_s}s bis {end_s}s")
                target_pts = int(start_s / float(v_in_stream.time_base))
                container.seek(target_pts, backward=True, any_frame=False, stream=v_in_stream)
                streams_to_read =[v_in_stream]
                if has_audio and is_final_pass:
                    streams_to_read.append(a_in_stream)
                for packet in container.demux(streams_to_read):
                    if self._is_canceled: break
                    while self._is_paused: time.sleep(0.1)
                    if packet.dts is None:
                        continue
                    packet_time_s = float(packet.dts * packet.time_base)
                    if packet_time_s > end_s + 1.0: # Puffer einberechnen (1s Overflow ist normal)
                        break
                    for frame in packet.decode():
                        if frame.time is None: continue
                        if frame.time < start_s: continue
                        if frame.time > end_s: break
                        if isinstance(frame, av.VideoFrame):
                            v_graph.push(frame)
                            try:
                                while True:
                                    out_frame = v_graph.pull()
                                    # Fortschritt UI benachrichtigen (Auch in Pass 1 aktiv!)
                                    rendered_seconds += (1.0 / fps_float)
                                    if frame_counter % 10 == 0:
                                        pass_offset = totalSeconds if current_pass == 2 else 0
                                        current_progress = pass_offset + rendered_seconds
                                        self.ffmpegProcess.emit([['out_time_ms', str(int(current_progress * 1000000))], self.job, overall_total_seconds])
                                    frame_counter += 1
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
            # --- ZWINGENDES FLUSHING ---
            # Dieser Block ist absolut essenziell, damit vidstabdetect in Pass 1 den Puffer leert
            # und die Transformationsdatei tatsächlich fertig auf die Festplatte schreibt!
            if not self._is_canceled:
                self._log(f"Sende EOF Signal an Video Filter in Pass {current_pass} zum Flushen...")
                v_graph.push(None)
                try:
                    while True:
                        out_frame = v_graph.pull()
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
                    self._log(f"Video Filter flush erfolgreich abgeschlossen in Pass {current_pass}.")
                # Encoder flushen
                if is_final_pass and out_v_stream:
                    self._log("Flushe Video Encoder...")
                    for enc_packet in out_v_stream.encode(None):
                        if not header_written:
                            for p in packet_queue: out_container.mux(p)
                            packet_queue.clear()
                            header_written = True
                        out_container.mux(enc_packet)
                if is_final_pass and has_audio:
                    self._log("Flushe Audio Filter...")
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
                        self._log("Flushe Audio Encoder...")
                        for enc_packet in out_a_stream.encode(None):
                            if not header_written:
                                for p in packet_queue: out_container.mux(p)
                                packet_queue.clear()
                                header_written = True
                            out_container.mux(enc_packet)
        finally:
            self._log(f"Räume Speicher-Referenzen fuer Pass {current_pass} auf...")
            if container:
                container.close()
            if out_container:
                try:
                    out_container.close()
                except Exception as e:
                    self._log(f"Cleanup error on out_container.close(): {e}")
            # EXTREM WICHTIG FÜR VID.STAB & PYAV MEMORY LEAKS!
            # Explizites Löschen von Referenzen und forcieren des Garbage Collectors.
            # Stellt sicher, dass das C-Backend die .trf Datei entsperrt, bevor Pass 2 versucht darauf zuzugreifen!
            del v_graph
            del v_src
            del v_sink
            del a_graph
            del a_src
            del a_fmt_node
            del a_sink
            gc.collect()
            # Warte dem OS zuliebe kurz, um das File Handle aus dem Memory Mapping von Pass 1 freizugeben
            if current_pass == 1 and deshake_state:
                time.sleep(2.0)  # Neu: Erhöht auf 2 Sekunden für sichere Freigabe
