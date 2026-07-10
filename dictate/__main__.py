from __future__ import annotations

import argparse
import logging
import signal
import subprocess
import threading
import time
from collections.abc import Callable

from .config import AppConfig, load_config
from .engines import TranscriptionEngine, build_engine
from .history import TranscriptHistory
from .hotkey import HotkeyCallbacks, RightOptionHoldListener
from .injector import InjectionError, TextInjector, build_injector
from .latency import LatencyHistory, LatencySample
from .postprocess import clean_transcript
from .recorder import AudioCaptureError, Recorder, Recording
from .transcriber import ModelUnavailableError
from .vad import SileroVadAutoStop

START_SOUND = "/System/Library/Sounds/Tink.aiff"
STOP_SOUND = "/System/Library/Sounds/Pop.aiff"
StatusCallback = Callable[[str], None]


def main() -> int:
    parser = argparse.ArgumentParser(description="Local macOS push-to-talk dictation")
    parser.add_argument(
        "--no-menubar",
        action="store_true",
        help="run as a foreground CLI service without the rumps menu bar",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="run local dependency and macOS permission diagnostics",
    )
    parser.add_argument(
        "--download-model",
        action="store_true",
        help="explicitly download and warm the configured model",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    if args.self_test:
        from . import menubar, settings

        del menubar, settings
        print("Vox Terminal app bundle self-test: OK")
        return 0

    from .logging_config import configure_logging

    configure_logging(foreground=args.no_menubar or args.doctor)

    if args.doctor:
        from .doctor import main as doctor_main

        return doctor_main()

    try:
        config = load_config()
    except Exception as exc:
        logging.error("Configuration error: %s", exc)
        return 2

    if args.download_model:
        from .model_manager import ModelManager

        ModelManager(config.model, config.language).download()
        print("Model is available in the local cache.")
        return 0

    if args.no_menubar:
        service = DictateService(config)
        return service.run_forever()

    from .controller import AppController
    from .menubar import DictateMenuBar

    try:
        controller = AppController()
    except Exception as exc:
        logging.error("Configuration error: %s", exc)
        return 2
    DictateMenuBar(controller).run()
    return 0


class DictateService:
    def __init__(
        self,
        config: AppConfig,
        *,
        status_callback: StatusCallback | None = None,
        recorder: Recorder | None = None,
        transcriber: TranscriptionEngine | None = None,
        injector: TextInjector | None = None,
        history: TranscriptHistory | None = None,
        vad_auto_stop: SileroVadAutoStop | None = None,
        latency_history: LatencyHistory | None = None,
    ) -> None:
        self.config = config
        self.recorder = recorder or Recorder(max_seconds=config.max_recording_seconds)
        self.transcriber = transcriber or build_engine(config)
        self.injector = injector or build_injector(
            paste_mode=config.paste_mode,
            restore_clipboard=config.restore_clipboard,
        )
        self.history = history or TranscriptHistory(config.history_size)
        self.latency_history = latency_history or LatencyHistory()
        self.vad_auto_stop = vad_auto_stop or SileroVadAutoStop(
            silence_seconds=config.vad_silence_seconds,
            min_speech_seconds=config.vad_min_speech_seconds,
        )
        self._status_callback = status_callback
        self._status = "stopped"
        self._recording_lock = threading.Lock()
        self._transcribing = threading.Lock()
        self._shutdown = threading.Event()
        self._listener: RightOptionHoldListener | None = None
        self._max_timer: threading.Timer | None = None
        self._vad_stop_event = threading.Event()
        self._vad_thread: threading.Thread | None = None
        self.last_error: str | None = None

    @property
    def status(self) -> str:
        return self._status

    def set_status_callback(self, callback: StatusCallback | None) -> None:
        self._status_callback = callback
        if callback is not None:
            callback(self._status)

    def start(self) -> bool:
        self.last_error = None
        self._set_status("loading")
        try:
            logging.info(
                "Loading %s model once at startup: %s",
                self.config.engine,
                self.config.selected_model,
            )
            self.transcriber.load()
        except ModelUnavailableError as exc:
            logging.error("%s", exc)
            self.last_error = str(exc)
            self._set_status("error")
            return False
        except Exception as exc:
            logging.exception("Model startup failed: %s", exc)
            self.last_error = f"Model startup failed: {exc}"
            self._set_status("error")
            return False

        self._listener = RightOptionHoldListener(
            HotkeyCallbacks(
                on_press=self._on_hotkey_press,
                on_release=self._on_hotkey_release,
                on_no_events=self._warn_input_monitoring,
            )
        )
        try:
            self._listener.start()
        except Exception as exc:
            logging.exception("Could not start global hotkey listener: %s", exc)
            self.last_error = f"Could not start the global hotkey: {exc}"
            self._set_status("error")
            return False

        self._set_status("idle")
        logging.info("Vox Terminal is ready. Hotkey mode: %s.", self.config.mode)
        return True

    def run_forever(self) -> int:
        self._install_signal_handlers()
        if not self.start():
            return 1
        try:
            while not self._shutdown.is_set():
                time.sleep(0.25)
        except KeyboardInterrupt:
            self._shutdown.set()
        finally:
            self.stop()
        return 0

    def stop(self) -> None:
        self._shutdown.set()
        self._cancel_max_timer()
        self._stop_vad_monitor()
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        with self._recording_lock:
            if self.recorder.is_recording:
                self.recorder.stop()
        self._set_status("stopped")

    def history_text(self) -> str:
        return self.history.render()

    def clear_history(self) -> None:
        self.history.clear()

    def performance_text(self) -> str:
        return self.latency_history.render()

    def _install_signal_handlers(self) -> None:
        def handle_signal(signum: int, frame: object) -> None:
            del signum, frame
            self._shutdown.set()

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

    def _on_hotkey_press(self) -> None:
        if self.config.mode == "toggle" and self.recorder.is_recording:
            self._finish_recording("toggle stop")
            return
        self._begin_recording()

    def _on_hotkey_release(self) -> None:
        if self.config.mode == "hold":
            self._finish_recording("hotkey release")

    def _begin_recording(self) -> None:
        if self._transcribing.locked():
            logging.info("Ignoring hotkey press while transcription is in flight.")
            return
        with self._recording_lock:
            if self.recorder.is_recording:
                return
            try:
                self.recorder.start()
            except AudioCaptureError as exc:
                logging.error("%s", exc)
                self.last_error = str(exc)
                self._set_status("error")
                return
            except Exception as exc:
                logging.exception("Could not start recording: %s", exc)
                self.last_error = f"Could not start recording: {exc}"
                self._set_status("error")
                return
            self._start_max_timer()
            self._start_vad_monitor()

        self._set_status("recording")
        self._play_sound(START_SOUND)
        logging.info("Recording...")

    def _finish_recording(self, reason: str) -> None:
        release_started_ns = time.perf_counter_ns()
        with self._recording_lock:
            if not self.recorder.is_recording:
                return
            try:
                recording = self.recorder.stop()
            except Exception as exc:
                logging.exception("Could not stop recording: %s", exc)
                self._set_status("error")
                return
            finally:
                self._cancel_max_timer()
                self._stop_vad_monitor()

        finalized_ns = time.perf_counter_ns()

        self._play_sound(STOP_SOUND)
        logging.info("Stopped recording: %s.", reason)

        minimum = self.config.min_recording_ms / 1000.0
        if recording.duration_seconds < minimum:
            logging.info("Ignoring %.0f ms recording.", recording.duration_seconds * 1000)
            self._set_status("idle")
            return

        worker = threading.Thread(
            target=self._transcribe_and_inject,
            args=(recording, release_started_ns, finalized_ns),
            daemon=True,
        )
        worker.start()

    def _start_max_timer(self) -> None:
        self._cancel_max_timer()
        self._max_timer = threading.Timer(
            self.config.max_recording_seconds,
            self._on_max_recording_time,
        )
        self._max_timer.daemon = True
        self._max_timer.start()

    def _cancel_max_timer(self) -> None:
        if self._max_timer is not None:
            self._max_timer.cancel()
            self._max_timer = None

    def _on_max_recording_time(self) -> None:
        logging.info("Recording reached %ss cap.", self.config.max_recording_seconds)
        self._finish_recording("maximum duration")

    def _start_vad_monitor(self) -> None:
        self._stop_vad_monitor()
        if self.config.mode != "toggle" or not self.config.vad_auto_stop:
            return
        self._vad_stop_event.clear()
        self._vad_thread = threading.Thread(target=self._vad_monitor_loop, daemon=True)
        self._vad_thread.start()

    def _stop_vad_monitor(self) -> None:
        self._vad_stop_event.set()
        if (
            self._vad_thread is not None
            and self._vad_thread.is_alive()
            and threading.current_thread() is not self._vad_thread
        ):
            self._vad_thread.join(timeout=1.0)
        self._vad_thread = None

    def _vad_monitor_loop(self) -> None:
        logging.info("VAD auto-stop monitor started.")
        while not self._vad_stop_event.wait(self.config.vad_poll_seconds):
            if not self.recorder.is_recording:
                return
            try:
                recording = self.recorder.snapshot()
                decision = self.vad_auto_stop.decide(
                    recording.audio,
                    sample_rate=recording.sample_rate,
                )
            except Exception as exc:
                logging.warning("VAD auto-stop failed; continuing recording: %s", exc)
                return
            if decision.should_stop:
                logging.info(
                    "VAD auto-stop after %.2fs trailing silence.",
                    decision.trailing_silence_seconds,
                )
                self._finish_recording("VAD auto-stop")
                return

    def _transcribe_and_inject(
        self,
        recording: Recording,
        release_started_ns: int | None = None,
        finalized_ns: int | None = None,
    ) -> None:
        release_started_ns = release_started_ns or time.perf_counter_ns()
        finalized_ns = finalized_ns or release_started_ns
        if not self._transcribing.acquire(blocking=False):
            logging.info("Ignoring recording while transcription is in flight.")
            self._set_status("idle")
            return
        self._set_status("transcribing")
        try:
            logging.info("Transcribing %.2fs of audio...", recording.duration_seconds)
            inference_started_ns = time.perf_counter_ns()
            transcript = self.transcriber.transcribe(recording.audio)
            inference_finished_ns = time.perf_counter_ns()
            cleaned = clean_transcript(
                transcript,
                rms=recording.rms,
                silence_rms_threshold=self.config.silence_rms_threshold,
            )
            if not cleaned:
                logging.info("No speech detected; nothing pasted.")
                return
            postprocess_finished_ns = time.perf_counter_ns()
            self.injector.inject(cleaned)
            paste_finished_ns = time.perf_counter_ns()
            self.history.add(cleaned)
            sample = LatencySample(
                engine=getattr(self.transcriber, "name", self.config.engine),
                audio_ms=recording.duration_seconds * 1_000,
                finalize_ms=(finalized_ns - release_started_ns) / 1_000_000,
                inference_ms=(inference_finished_ns - inference_started_ns) / 1_000_000,
                postprocess_ms=(postprocess_finished_ns - inference_finished_ns) / 1_000_000,
                paste_ms=(paste_finished_ns - postprocess_finished_ns) / 1_000_000,
                total_ms=(paste_finished_ns - release_started_ns) / 1_000_000,
            )
            self.latency_history.add(sample)
            logging.info(
                "Latency engine=%s audio_ms=%.0f finalize_ms=%.1f inference_ms=%.1f "
                "postprocess_ms=%.1f paste_ms=%.1f total_ms=%.1f",
                sample.engine,
                sample.audio_ms,
                sample.finalize_ms,
                sample.inference_ms,
                sample.postprocess_ms,
                sample.paste_ms,
                sample.total_ms,
            )
            logging.info("Pasted transcript (%d chars).", len(cleaned))
        except InjectionError as exc:
            logging.error("%s", exc)
            self.last_error = str(exc)
            self._set_status("error")
            return
        except Exception as exc:
            logging.exception("Transcription failed: %s", exc)
            self.last_error = f"Transcription failed: {exc}"
            self._set_status("error")
            return
        finally:
            self._transcribing.release()
            if self._status != "error":
                self._set_status("idle")

    def _play_sound(self, sound_path: str) -> None:
        if not self.config.sounds:
            return
        try:
            subprocess.Popen(
                ["afplay", sound_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            logging.debug("afplay is unavailable; skipping sound.")

    def _warn_input_monitoring(self) -> None:
        logging.warning(
            "No keyboard events observed. If Right Option does not work, grant "
            "Input Monitoring to the launching terminal app and venv Python."
        )

    def _set_status(self, status: str) -> None:
        self._status = status
        if self._status_callback is not None:
            self._status_callback(status)


if __name__ == "__main__":
    raise SystemExit(main())
