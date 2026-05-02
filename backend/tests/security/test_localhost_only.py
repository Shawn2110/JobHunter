"""Per Agent.md § Critical Do-Not-Break Tests:

The backend binds to localhost by default. Public binding requires the
explicit BIND_PUBLIC=1 env var (intended for VPS deployments behind
Cloudflare Tunnel + Access). This test asserts the default behavior.
"""

from __future__ import annotations

import pytest

from app.config import Settings


def test_default_binds_to_localhost() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.bind_public is False
    # When bind_public=False, host_for_uvicorn() returns the user-configured
    # backend_host (default 127.0.0.1), NOT 0.0.0.0.
    assert s.host_for_uvicorn() != "0.0.0.0"
    assert s.host_for_uvicorn().startswith(("127.", "localhost"))


def test_explicit_bind_public_listens_on_all_interfaces() -> None:
    """Only when the user opts in via BIND_PUBLIC=1 does the app
    listen on 0.0.0.0. Cloudflare Tunnel handles ingress on the
    intended deployment path."""
    s = Settings(_env_file=None, bind_public=True)  # type: ignore[call-arg]
    assert s.host_for_uvicorn() == "0.0.0.0"


def test_cors_default_origin_is_localhost() -> None:
    """CORS origin defaults to localhost:3000 — the local Next.js
    dev server. Production deployments must override explicitly."""
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.frontend_origin.startswith("http://localhost:")
