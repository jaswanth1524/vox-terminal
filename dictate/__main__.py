from __future__ import annotations

import argparse
import logging
import signal
import subprocess
import threading
import time
from typing import Callable

from .config import AppConfig, load_config
from .hotkey import HotkeyCallbacks, RightOptionHoldListener
from .injector import InjectionError, TextInjector, build_injector
from .postprocess import clean_transcript
from .recorder import AudioCaptureError, Recorder, Recording
from .transcriber import ModelUnavailableError, Transcriber


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
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        config = load_config()
    except Exception as exc:
        logging.error("Configuration error: %s", exc)
        return 2

    service = DictateService(config)
    if args.no_menubar:
        return service.run_forever()

    from .menubar import DictateMenuBar

    DictateMenuBar(service).run()
    return 0


class DictateService:
    def __init__(
        self,
        config: AppConfig,
        *,
        status_callback: StatusCallback | None = None,
        recorder: Recorder | None = None,
        transcriber: Transcriber | None = None,
        injector: TextInjector | None = None,
    ) -> None:
        self.config = config
        self.recorder = recorder or Recorder(max_seconds=config.max_recording_seconds)
        self.transcriber = transcriber or Transcriber(
            model=config.model,
            language=config.language,
            initial_prompt=config.initial_prompt,
            offline=True,
        )
        self.injector = injector or build_injector(
            paste_mode=config.paste_mode,
            restore_clipboard=config.restore_clipboard,
        )
        self._status_callback = status_callback
        self._status = "stopped"
        self._recording_lock = threading.Lock()
        self._transcribing = threading.Lock()
        self._shutdown = threading.Event()
        self._listener: RightOptionHoldListener | None = None
        self._max_timer: threading.Timer | None = None

    @property
    def status(self) -> str:
        return self._status

    def set_status_callback(self, callback: StatusCallback | None) -> None:
        self._status_callback = callback
        if callback is not None:
            callback(self._status)

    def start(self) -> bool:
        self._set_status("loading")
        try:
            logging.info("Loading model once at startup: %s", self.config.model)
            self.transcriber.load()
        except ModelUnavailableError as exc:
            logging.error("%s", exc)
            self._set_status("error")
            return False
        except Exception as exc:
            logging.exception("Model startup failed: %s", exc)
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
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        with self._recording_lock:
            if self.recorder.is_recording:
                self.recorder.stop()
        self._set_status("stopped")

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
                self._set_status("error")
                return
            except Exception as exc:
                logging.exception("Could not start recording: %s", exc)
                self._set_status("error")
                return
            self._start_max_timer()

        self._set_status("recording")
        self._play_sound(START_SOUND)
        logging.info("Recording...")

    def _finish_recording(self, reason: str) -> None:
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

        self._play_sound(STOP_SOUND)
        logging.info("Stopped recording: %s.", reason)

        minimum = self.config.min_recording_ms / 1000.0
        if recording.duration_seconds < minimum:
            logging.info("Ignoring %.0f ms recording.", recording.duration_seconds * 1000)
            self._set_status("idle")
            return

        worker = threading.Thread(
            target=self._transcribe_and_inject,
            args=(recording,),
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

    def _transcribe_and_inject(self, recording: Recording) -> None:
        if not self._transcribing.acquire(blocking=False):
            logging.info("Ignoring recording while transcription is in flight.")
            self._set_status("idle")
            return
        self._set_status("transcribing")
        try:
            logging.info("Transcribing %.2fs of audio...", recording.duration_seconds)
            transcript = self.transcriber.transcribe(recording.audio)
            cleaned = clean_transcript(
                transcript,
                rms=recording.rms,
                silence_rms_threshold=self.config.silence_rms_threshold,
            )
            if not cleaned:
                logging.info("No speech detected; nothing pasted.")
                return
            self.injector.inject(cleaned)
            logging.info("Pasted transcript (%d chars).", len(cleaned))
        except InjectionError as exc:
            logging.error("%s", exc)
            self._set_status("error")
            return
        except Exception as exc:
            logging.exception("Transcription failed: %s", exc)
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
