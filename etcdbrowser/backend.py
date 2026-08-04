# Copyright (c) 2026
#
# Backend for opening etcd snapshots: verify, restore, serve and query.
#
# We talk to the running etcd through its built-in HTTP/JSON gateway (the
# gRPC-gateway endpoints under /v3/kv/...) using only the standard library,
# so no gRPC / protobuf client dependencies are required.

from __future__ import annotations

import base64
import json
import os
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.request

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK_DIR = os.path.join(PROJECT_DIR, "tmp")
STATE_FILE = os.path.join(WORK_DIR, "etcdbrowser.state")

DEFAULT_CLIENT_PORT = 22379
DEFAULT_PEER_PORT = 22380
CLUSTER_TOKEN = "etcd-cluster-1"


class BackendError(RuntimeError):
    pass


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def unb64(data: str) -> bytes:
    return base64.b64decode(data)


def _http_json(endpoint: str, path: str, body: dict, timeout: int = 30) -> dict:
    url = endpoint + path
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8"))
            message = detail.get("message") or detail.get("error") or str(exc)
        except Exception:
            message = str(exc)
        raise BackendError("etcd %s: %s" % (path, message)) from exc
    except urllib.error.URLError as exc:
        raise BackendError("cannot reach etcd at %s: %s" % (endpoint, exc.reason)) from exc


# ---------------------------------------------------------------- state ----

def read_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    state: dict = {}
    with open(STATE_FILE, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if "=" in line:
                k, _, v = line.partition("=")
                state[k.strip()] = v.strip()
    return state


def write_state(state: dict) -> None:
    os.makedirs(WORK_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        for key in ("pid", "client_url", "peer_url", "datadir", "snapshot", "logfile"):
            fh.write("%s=%s\n" % (key, state.get(key, "")))


def _pid_alive(pid) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


# ------------------------------------------------------------ snapshot ----

def snapshot_status(snapshot: str) -> str:
    proc = subprocess.run(["etcdctl", "snapshot", "status", snapshot],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise BackendError("invalid snapshot: %s" % proc.stderr.strip())
    return proc.stdout.strip()


def _health(endpoint: str, timeout: int = 2) -> bool:
    try:
        req = urllib.request.Request(endpoint + "/health", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")).get("health") == "true"
    except Exception:
        return False


def open_snapshot(snapshot: str, client_port: int = DEFAULT_CLIENT_PORT,
                  peer_port: int = DEFAULT_PEER_PORT) -> dict:
    """Verify, restore and serve ``snapshot``; returns the running state."""
    snapshot = os.path.abspath(snapshot)
    if not os.path.isfile(snapshot):
        raise BackendError("snapshot not found: %s" % snapshot)
    os.makedirs(WORK_DIR, exist_ok=True)

    state = read_state()
    if state and _pid_alive(state.get("pid")):
        raise BackendError(
            "etcd already running (pid %s at %s). Close it first." %
            (state["pid"], state["client_url"]))

    snapshot_status(snapshot)

    name = "default-%d" % client_port
    datadir = os.path.join(WORK_DIR, "restore-%d" % client_port)
    logfile = os.path.join(WORK_DIR, "etcd-%d.log" % client_port)
    client_url = "http://127.0.0.1:%d" % client_port
    peer_url = "http://127.0.0.1:%d" % peer_port

    shutil.rmtree(datadir, ignore_errors=True)
    proc = subprocess.run(
        ["etcdctl", "snapshot", "restore", snapshot,
         "--data-dir", datadir, "--name", name,
         "--initial-cluster", "%s=%s" % (name, peer_url),
         "--initial-advertise-peer-urls", peer_url,
         "--initial-cluster-token", CLUSTER_TOKEN],
        capture_output=True, text=True)
    if proc.returncode != 0:
        raise BackendError("restore failed: %s" % proc.stderr.strip())

    logfh = open(logfile, "ab")
    server = subprocess.Popen(
        ["etcd",
         "--name", name, "--data-dir", datadir,
         "--initial-cluster", "%s=%s" % (name, peer_url),
         "--initial-advertise-peer-urls", peer_url,
         "--initial-cluster-token", CLUSTER_TOKEN,
         "--listen-client-urls", client_url,
         "--advertise-client-urls", client_url,
         "--listen-peer-urls", peer_url],
        stdout=logfh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        start_new_session=True)

    for _ in range(120):
        if _health(client_url):
            break
        if server.poll() is not None:
            raise BackendError("etcd exited during startup; see %s" % logfile)
        time.sleep(0.5)
    if not _health(client_url):
        raise BackendError("etcd did not become healthy within 60s; see %s" % logfile)

    state = {"pid": str(server.pid), "client_url": client_url, "peer_url": peer_url,
             "datadir": datadir, "snapshot": snapshot, "logfile": logfile}
    write_state(state)
    return state


def close(keep_data: bool = False) -> None:
    """Stop the running etcd (and remove the restored data dir by default)."""
    state = read_state()
    if state:
        pid = state.get("pid")
        if _pid_alive(pid):
            try:
                os.kill(int(pid), signal.SIGTERM)
            except OSError:
                pass
            for _ in range(20):
                if not _pid_alive(pid):
                    break
                time.sleep(0.25)
            if _pid_alive(pid):
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except OSError:
                    pass
        if not keep_data:
            datadir = state.get("datadir")
            if datadir:
                shutil.rmtree(datadir, ignore_errors=True)
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)


# -------------------------------------------------------------- kv client --

class KVClient:
    """Thin client for the etcd v3 JSON gateway."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint.rstrip("/")

    def get(self, key: bytes) -> dict | None:
        resp = _http_json(self.endpoint, "/v3/kv/range", {"key": b64(key), "limit": 1})
        if not resp.get("kvs"):
            return None
        kv = resp["kvs"][0]
        return {"key": unb64(kv["key"]), "value": unb64(kv["value"]),
                "create_revision": kv.get("create_revision"),
                "mod_revision": kv.get("mod_revision"),
                "version": kv.get("version"), "lease": kv.get("lease")}

    def iter_range(self, prefix: bytes, keys_only: bool = False, chunk: int = 500):
        """Yield (key, value_or_None) for every key under ``prefix`` (paged)."""
        start = prefix
        end = prefix + b"\xff"
        while True:
            resp = _http_json(self.endpoint, "/v3/kv/range",
                              {"key": b64(start), "range_end": b64(end),
                               "limit": chunk, "keys_only": keys_only})
            kvs = resp.get("kvs", [])
            for kv in kvs:
                key = unb64(kv["key"])
                value = None if keys_only else unb64(kv["value"])
                yield key, value
            if not resp.get("more") or not kvs:
                break
            start = unb64(kvs[-1]["key"]) + b"\x00"

    def count(self, prefix: bytes) -> int:
        return sum(1 for _ in self.iter_range(prefix, keys_only=True))

    def list_prefixes(self, prefix: bytes) -> list[str]:
        """Distinct next-path-segment names under ``prefix``."""
        seen = {}
        base_len = len(prefix)
        for key, _ in self.iter_range(prefix, keys_only=True):
            rest = key[base_len:].lstrip(b"/")
            if not rest:
                continue
            seg = rest.split(b"/", 1)[0].decode("utf-8", errors="replace")
            seen[seg] = seen.get(seg, 0) + 1
        return sorted(seen.items())
