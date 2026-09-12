"""Separate-process Pome evidence acquisition with durable, anchored snapshots.

Trusts the Pome endpoint and OS. A receipt detects later archive changes only
while the caller retains its original receipt outside the mutable archive.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import resource
import time

from src.pome_adapter import PomeClient


def validate_tape(events, expected_ids, previous=()):
    if not isinstance(events, list) or len(events) < len(previous) or events[:len(previous)] != list(previous):
        raise ValueError("Tape truncated or previously observed events modified")
    identifiers = []
    for event in events:
        if not isinstance(event, dict) or not {
            "request_id", "correlation_id", "method", "path", "request_body", "status",
            "state_mutation", "state_delta", "response_body",
        } <= event.keys():
            raise ValueError("Missing event evidence")
        if not isinstance(event["request_id"], str) or not isinstance(event["correlation_id"], str):
            raise ValueError("Malformed event identity")
        if type(event["status"]) is not int or not 100 <= event["status"] <= 599:
            raise ValueError("Malformed event status")
        identifiers.append(event["request_id"])
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate event identity")
    if Counter(e["correlation_id"] for e in events) != Counter(expected_ids):
        raise ValueError("Missing or unexpected requests in tape")


def persist_snapshot(directory: Path, payload: dict) -> dict:
    directory.mkdir(parents=True, exist_ok=False)
    receipt = {}
    for name, value in payload.items():
        data = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
        path = directory / f"{name}.json"
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        receipt[path.name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return receipt


def verify_snapshot(directory: Path, receipt: dict):
    if set(receipt) != {"events.json", "state.json"}:
        raise ValueError("Incomplete snapshot receipt")
    result = {}
    for name, expected in receipt.items():
        data = (directory / name).read_bytes()
        if len(data) != expected["bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
            raise ValueError("Snapshot differs from retained receipt")
        result[name.removesuffix(".json")] = json.loads(data)
    return result


def _worker(conn, url, token, destination, timeout):
    client = PomeClient(url, token, timeout)
    previous = []
    index = 0
    try:
        while True:
            message = conn.recv()
            if message is None:
                return
            started = time.perf_counter()
            try:
                payload = client.evidence()
                validate_tape(payload["events"], message, previous)
                name = f"snapshot-{index:03d}"
                receipt = persist_snapshot(Path(destination) / name, payload)
                previous = payload["events"]
                index += 1
                conn.send({"snapshot": name, "receipt": receipt, "pid": os.getpid(),
                           "capture_ms": (time.perf_counter() - started) * 1000,
                           "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
            except Exception as error:
                conn.send({"error": f"{type(error).__name__}: {error}"})
    except EOFError:
        pass
    finally:
        conn.close()


class EvidenceObserver:
    """Only fetch instructions cross the pipe; caller-supplied event payloads are unsupported."""

    def __init__(self, client, destination: Path, timeout: float = 12):
        self.timeout = timeout
        self.destination = destination
        context = mp.get_context("spawn")
        self._parent, child = context.Pipe()
        self._process = context.Process(target=_worker,
            args=(child, client.url, client.token, str(destination), min(client.timeout, timeout / 3)))
        self._process.start()
        child.close()

    def capture(self, expected_ids):
        if not self._process.is_alive():
            raise RuntimeError("Observer process unavailable")
        self._parent.send(list(expected_ids))
        if not self._parent.poll(self.timeout):
            self.close()
            raise TimeoutError("Observer deadline exceeded")
        try:
            result = self._parent.recv()
        except EOFError as error:
            raise RuntimeError("Observer exited without evidence") from error
        if "error" in result:
            raise ValueError(result["error"])
        return result

    def close(self):
        if self._process.is_alive():
            try:
                self._parent.send(None)
            except (BrokenPipeError, OSError):
                pass
            self._process.join(timeout=0.5)
            if self._process.is_alive():
                self._process.terminate()
                self._process.join(timeout=1)
            if self._process.is_alive():
                self._process.kill()
                self._process.join(timeout=1)
        self._parent.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
