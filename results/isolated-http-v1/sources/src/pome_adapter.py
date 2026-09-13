"""Pinned Pome foreground twin and authenticated loopback evidence endpoints."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request as HttpRequest, build_opener, ProxyHandler, HTTPRedirectHandler

from src.effect_bound import ToolServer


ROOT = Path(__file__).resolve().parents[1]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args):
        raise ValueError("Pome request redirect rejected")


class PomeClient:
    def __init__(self, url: str, token: str, timeout: float = 5):
        parsed = urlsplit(url)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username:
            raise ValueError("Only an explicit loopback Pome endpoint is permitted")
        self.url, self.token, self.timeout = url.rstrip("/"), token, timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, method: str, path: str, body=None, correlation: str | None = None):
        if not path.startswith("/") or ".." in path or "?" in path or "#" in path:
            raise ValueError("Invalid twin path")
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        if correlation:
            headers["x-pome-correlation-id"] = correlation
        request = HttpRequest(self.url + path, method=method, headers=headers,
                              data=None if body is None else json.dumps(body).encode())
        try:
            response = self.opener.open(request, timeout=self.timeout)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def evidence(self):
        status, events = self.request("GET", "/_pome/events")
        if status != 200 or not isinstance(events, list):
            raise ValueError("Pome tape missing or malformed")
        status, state = self.request("GET", "/_pome/state")
        if status != 200 or not isinstance(state, dict):
            raise ValueError("Pome state missing or malformed")
        return {"events": events, "state": state}


class LocalPome:
    """Own a temporary CLI process, credential directory, and guaranteed cleanup."""

    def __enter__(self):
        self.directory = tempfile.TemporaryDirectory(prefix="effect-bound-pome-")
        self.process = None
        started = time.perf_counter()
        try:
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            node = ROOT / "node_modules/node/bin/node"
            cli = ROOT / "node_modules/@pome-sh/cli/dist/src/cli/main.js"
            env = {"PATH": str(node.parent) + os.pathsep + "/usr/bin:/bin",
                   "TWIN_AUTH_SECRET": secrets.token_hex(32), "TWIN_ADMIN_TOKEN": secrets.token_hex(32),
                   "NO_COLOR": "1"}
            self.process = subprocess.Popen(
                [str(node), str(cli), "twin", "start", "github", "--port", str(port)],
                cwd=self.directory.name, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            status_path = Path(self.directory.name) / ".pome/twin-status.json"
            deadline = time.monotonic() + 20
            while True:
                if self.process.poll() is not None:
                    raise RuntimeError("Pinned Pome process exited during startup")
                if time.monotonic() >= deadline:
                    raise TimeoutError("Pome startup exceeded 20 seconds")
                try:
                    status = json.loads(status_path.read_text())
                    if {"rest_url", "auth_token"} <= status.keys():
                        break
                except (FileNotFoundError, json.JSONDecodeError):
                    pass
                time.sleep(0.02)
            self.client = PomeClient(status["rest_url"], status["auth_token"])
            self.startup_ms = (time.perf_counter() - started) * 1000
            return self
        except BaseException:
            self.__exit__()
            raise

    def __exit__(self, *_):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.directory.cleanup()


def wire_request(request):
    """Explicit supported route mapping; no arbitrary URL or query forwarding."""
    if request.tool == "get_repository_metadata" and set(request.args) == {"repo"}:
        repo = request.args["repo"]
        if isinstance(repo, str) and re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", repo):
            return "GET", f"/repos/{repo}", None
    if request.tool == "create_repository" and set(request.args) == {"repo"}:
        repo = request.args["repo"]
        if isinstance(repo, str) and re.fullmatch(r"[A-Za-z0-9_-]+", repo):
            return "POST", "/user/repos", {"name": repo, "private": True}
    raise ValueError("Unsupported tool or arguments for this Pome experiment")


class PomeToolServer(ToolServer):
    """Capability gate before Pome's REST boundary; Pome itself does not validate our tokens."""

    def __init__(self, client, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = client
        self.repositories = self._repository_names()

    def _repository_names(self):
        status, state = self.client.request("GET", "/_pome/state")
        if status != 200:
            raise ValueError("Cannot establish Pome state")
        return {repo["full_name"] for repo in state["repositories"]}

    def _execute(self, request, capability=None):
        self.repositories = self._repository_names()
        before = sorted(self.repositories)
        reason = self.authorize(request, capability)
        if reason is not None:
            return self._record(request, False, reason, before)
        method, path, body = wire_request(request)
        status, _ = self.client.request(method, path, body, request.request_id)
        self.repositories = self._repository_names()
        return self._record(request, status < 400, f"Pome HTTP {status}", before)

    def clone(self):
        raise NotImplementedError("Pome quarantine needs a separately seeded twin; local clone forbidden")
