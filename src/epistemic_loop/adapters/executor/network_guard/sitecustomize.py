"""Fail-closed network guard injected into local Python experiment processes."""

from __future__ import annotations

import os
import socket


def _blocked(*_args: object, **_kwargs: object) -> None:
    raise PermissionError("network access is disabled by the experiment execution policy")


if os.environ.get("ERL_NETWORK_POLICY") == "disabled":
    for attribute in ("create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex"):
        setattr(socket, attribute, _blocked)
    for attribute in ("connect", "connect_ex"):
        setattr(socket.socket, attribute, _blocked)
