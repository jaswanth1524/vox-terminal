from __future__ import annotations

import os
import socket
import unittest

import numpy as np

from dictate.network import (
    OFFLINE_ENV_VARS,
    PROVISIONING_ENV,
    OutboundNetworkBlockedError,
    install_offline_guard,
    is_provisioning_process,
    offline_guard_installed,
    provisioning_environment,
)
from dictate.transcriber import Transcriber


class NoNetworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        install_offline_guard()

    def test_guard_sets_offline_environment_and_is_idempotent(self) -> None:
        install_offline_guard()

        self.assertTrue(offline_guard_installed())
        for key in OFFLINE_ENV_VARS:
            self.assertEqual(os.environ[key], "1")

    def test_guard_blocks_internet_socket_connect(self) -> None:
        candidate = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(candidate.close)

        with self.assertRaises(OutboundNetworkBlockedError):
            candidate.connect(("203.0.113.1", 443))

    def test_guard_blocks_udp_send(self) -> None:
        candidate = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(candidate.close)

        with self.assertRaises(OutboundNetworkBlockedError):
            candidate.sendto(b"offline", ("203.0.113.1", 443))

    @unittest.skipUnless(hasattr(socket.socket, "sendmsg"), "sendmsg is unavailable")
    def test_guard_blocks_udp_sendmsg(self) -> None:
        candidate = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(candidate.close)

        with self.assertRaises(OutboundNetworkBlockedError):
            candidate.sendmsg([b"offline"], [], 0, ("203.0.113.1", 443))

    def test_guard_blocks_external_dns_resolution(self) -> None:
        with self.assertRaises(OutboundNetworkBlockedError):
            socket.getaddrinfo("models.example.invalid", 443)

    def test_guard_leaves_local_unix_sockets_available(self) -> None:
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)

        left.sendall(b"local")

        self.assertEqual(right.recv(5), b"local")

    def test_provisioning_requires_marker_and_hidden_flag(self) -> None:
        marked = {PROVISIONING_ENV: "1"}

        self.assertFalse(is_provisioning_process(["vox-terminal"], marked))
        self.assertFalse(
            is_provisioning_process(
                ["vox-terminal", "--provision-model"],
                {},
            )
        )
        self.assertTrue(
            is_provisioning_process(
                ["vox-terminal", "--provision-model"],
                marked,
            )
        )

    def test_provisioning_child_environment_removes_offline_flags(self) -> None:
        environment = provisioning_environment(
            {
                "PATH": "/usr/bin",
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "HF_DATASETS_OFFLINE": "1",
            }
        )

        self.assertEqual(environment["PATH"], "/usr/bin")
        self.assertEqual(environment[PROVISIONING_ENV], "1")
        for key in OFFLINE_ENV_VARS:
            self.assertNotIn(key, environment)

    def test_transcription_path_opens_no_sockets(self) -> None:
        calls: list[str] = []

        def fake_transcribe(audio: np.ndarray, **kwargs: object) -> dict[str, str]:
            calls.append(str(kwargs["path_or_hf_repo"]))
            self.assertIsInstance(audio, np.ndarray)
            return {"text": "hello local world"}

        transcriber = Transcriber(
            model="local-test-model",
            transcribe_impl=fake_transcribe,
        )
        text = transcriber.transcribe(np.zeros(160, dtype=np.float32))

        self.assertEqual(text, "hello local world")
        self.assertEqual(calls, ["local-test-model", "local-test-model"])
        self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")
        self.assertEqual(os.environ["TRANSFORMERS_OFFLINE"], "1")


if __name__ == "__main__":
    unittest.main()
