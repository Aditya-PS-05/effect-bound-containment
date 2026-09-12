"""Hash-chain observer kept in a separate process from the tool server."""

from __future__ import annotations

import hashlib
import hmac
import json
import multiprocessing as mp
from typing import Any


def _digest(previous: str, payload: str) -> str:
    return hashlib.sha256(f"{previous}|{payload}".encode()).hexdigest()


def _worker(conn: Any) -> None:
    entries: list[dict[str, str]] = []
    try:
        while True:
            message = conn.recv()
            if message["op"] == "append":
                previous = entries[-1]["hash"] if entries else "0" * 64
                payload = message["payload"]
                entries.append({"previous": previous, "payload": payload, "hash": _digest(previous, payload)})
                conn.send(True)
            elif message["op"] == "verify":
                previous = "0" * 64
                valid = True
                for entry in entries:
                    valid = valid and entry["previous"] == previous
                    valid = valid and hmac.compare_digest(_digest(previous, entry["payload"]), entry["hash"])
                    previous = entry["hash"]
                conn.send(valid)
            elif message["op"] == "close":
                conn.send(True)
                return
    finally:
        conn.close()


class ProcessObservationLog:
    """Separate-process integrity check; a separate host is still required for stronger claims."""

    def __init__(self) -> None:
        # ponytail: fork is the smallest local process boundary; use a dedicated host for hostile code.
        context = mp.get_context("fork")
        self._parent, child = context.Pipe()
        self._process = context.Process(target=_worker, args=(child,))
        self._process.start()

    def append(self, event: Any) -> None:
        payload = json.dumps(event.__dict__, sort_keys=True, separators=(",", ":"), default=str)
        self._parent.send({"op": "append", "payload": payload})
        self._parent.recv()

    def verify(self) -> bool:
        self._parent.send({"op": "verify"})
        return bool(self._parent.recv())

    def close(self) -> None:
        if self._process.is_alive():
            self._parent.send({"op": "close"})
            self._parent.recv()
            self._process.join(timeout=1)
        self._parent.close()

    def __enter__(self) -> "ProcessObservationLog":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
