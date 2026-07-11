from __future__ import annotations

import ipaddress
import os
import socket
import sys
from collections.abc import Mapping, Sequence
from typing import Any

PROVISIONING_ENV = "VOX_TERMINAL_ALLOW_MODEL_DOWNLOAD"
PROVISIONING_FLAG = "--provision-model"
OFFLINE_ENV_VARS = (
    "HF_HUB_OFFLINE",
    "TRANSFORMERS_OFFLINE",
    "HF_DATASETS_OFFLINE",
)


class OutboundNetworkBlockedError(PermissionError):
    """Raised when normal Vox Terminal runtime attempts outbound networking."""


_guard_installed = False


def is_provisioning_process(
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Return whether this fresh process was explicitly authorized to download a model."""

    arguments = sys.argv if argv is None else argv
    environment = os.environ if environ is None else environ
    return (
        environment.get(PROVISIONING_ENV) == "1"
        and PROVISIONING_FLAG in arguments
    )


def install_runtime_network_policy() -> bool:
    """Install the permanent offline policy unless this is the provisioning child."""

    if is_provisioning_process():
        _set_huggingface_offline(False)
        return False
    install_offline_guard()
    return True


def install_offline_guard() -> None:
    """Permanently reject outbound internet sockets in the current process."""

    global _guard_installed
    _set_huggingface_offline(True)
    if _guard_installed:
        return
    sys.addaudithook(_offline_socket_audit_hook)
    _guard_installed = True


def offline_guard_installed() -> bool:
    return _guard_installed


def provisioning_environment(
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the environment for the single-use online provisioning child."""

    child_environment = dict(os.environ if environ is None else environ)
    child_environment[PROVISIONING_ENV] = "1"
    for key in OFFLINE_ENV_VARS:
        child_environment.pop(key, None)
    return child_environment


def _set_huggingface_offline(offline: bool) -> None:
    if offline:
        for key in OFFLINE_ENV_VARS:
            os.environ[key] = "1"
    else:
        for key in OFFLINE_ENV_VARS:
            os.environ.pop(key, None)

    hub_constants = sys.modules.get("huggingface_hub.constants")
    if hub_constants is not None:
        hub_constants.HF_HUB_OFFLINE = offline


def _offline_socket_audit_hook(event: str, args: tuple[Any, ...]) -> None:
    if event == "socket.connect" and args and _is_internet_socket(args[0]):
        raise _blocked_error()
    if event in {"socket.sendmsg", "socket.sendto"} and args and _is_internet_socket(args[0]):
        raise _blocked_error()
    if event in {"socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyname_ex"}:
        host = args[0] if args else None
        if not _is_local_or_numeric_host(host):
            raise _blocked_error()
    if event == "socket.gethostbyaddr":
        host = args[0] if args else None
        if not _is_loopback_host(host):
            raise _blocked_error()


def _is_internet_socket(candidate: object) -> bool:
    return getattr(candidate, "family", None) in {socket.AF_INET, socket.AF_INET6}


def _is_local_or_numeric_host(host: object) -> bool:
    if host is None:
        return True
    if isinstance(host, bytes):
        try:
            host = host.decode("ascii")
        except UnicodeDecodeError:
            return False
    if not isinstance(host, str):
        return False
    if host.casefold().rstrip(".") in {"localhost", "ip6-localhost"}:
        return True
    try:
        ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return False
    return True


def _is_loopback_host(host: object) -> bool:
    if isinstance(host, bytes):
        try:
            host = host.decode("ascii")
        except UnicodeDecodeError:
            return False
    if not isinstance(host, str):
        return False
    try:
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        return host.casefold().rstrip(".") in {"localhost", "ip6-localhost"}


def _blocked_error() -> OutboundNetworkBlockedError:
    return OutboundNetworkBlockedError(
        "Outbound networking is disabled during Vox Terminal runtime. "
        "Use --download-model for the explicit model provisioning operation."
    )
