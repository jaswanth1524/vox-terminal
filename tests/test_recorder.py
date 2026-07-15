from __future__ import annotations

import time
import unittest
from unittest import mock

import numpy as np
import sounddevice as sd

from dictate.recorder import Recorder


class RecorderTests(unittest.TestCase):
    def test_read_new_audio_returns_each_sample_once(self) -> None:
        recorder = Recorder(sample_rate=10, max_seconds=2)
        first = np.arange(4, dtype=np.float32).reshape(-1, 1)
        second = np.arange(4, 7, dtype=np.float32).reshape(-1, 1)

        recorder._callback(first, 4, None, sd.CallbackFlags())
        first_read = recorder.read_new_audio()
        recorder._callback(second, 3, None, sd.CallbackFlags())
        second_read = recorder.read_new_audio()

        np.testing.assert_array_equal(first_read, first[:, 0])
        np.testing.assert_array_equal(second_read, second[:, 0])
        self.assertEqual(recorder.read_new_audio().size, 0)
        np.testing.assert_array_equal(
            recorder.snapshot().audio,
            np.arange(7, dtype=np.float32),
        )

    def test_stop_copies_only_recorded_region_and_resets_read_cursor(self) -> None:
        recorder = Recorder(sample_rate=10, max_seconds=2)
        recorder._started_at = time.monotonic() - 0.5
        audio = np.arange(6, dtype=np.float32).reshape(-1, 1)
        recorder._callback(audio, 6, None, sd.CallbackFlags())
        recorder.read_new_audio()

        recording = recorder.stop()
        recorder._buffer[0] = 99.0

        np.testing.assert_array_equal(recording.audio, audio[:, 0])
        self.assertEqual(recorder.read_new_audio().size, 0)
        self.assertEqual(recorder.snapshot().audio.size, 0)

    def test_capture_storage_is_preallocated_and_capped(self) -> None:
        recorder = Recorder(sample_rate=10, max_seconds=1)
        buffer_id = id(recorder._buffer)
        oversized = np.arange(15, dtype=np.float32).reshape(-1, 1)

        with self.assertRaises(sd.CallbackStop):
            recorder._callback(oversized, 15, None, sd.CallbackFlags())

        self.assertEqual(id(recorder._buffer), buffer_id)
        self.assertEqual(recorder._buffer.size, 10)
        np.testing.assert_array_equal(
            recorder.snapshot().audio,
            np.arange(10, dtype=np.float32),
        )

    @mock.patch("dictate.recorder.sd.InputStream")
    @mock.patch("dictate.recorder.sd.query_devices")
    def test_start_reuses_fixed_buffer_and_resets_incremental_reads(
        self,
        query_devices: mock.Mock,
        input_stream: mock.Mock,
    ) -> None:
        del query_devices
        stream = input_stream.return_value
        recorder = Recorder(sample_rate=10, max_seconds=1)
        buffer_id = id(recorder._buffer)

        recorder.start()
        recorder._callback(np.ones((3, 1), dtype=np.float32), 3, None, sd.CallbackFlags())
        recorder.read_new_audio()
        recorder.stop()
        recorder.start()
        recorder._callback(np.full((2, 1), 2.0, dtype=np.float32), 2, None, sd.CallbackFlags())

        self.assertEqual(id(recorder._buffer), buffer_id)
        np.testing.assert_array_equal(
            recorder.read_new_audio(),
            np.full(2, 2.0, dtype=np.float32),
        )
        stream.abort.assert_called_once_with()
        stream.stop.assert_not_called()
        stream.start.assert_called()


if __name__ == "__main__":
    unittest.main()
