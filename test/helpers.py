# Copyright (c) 2026
# Test-only helpers to build a synthetic in-memory etcd snapshot, including
# real ``k8s\x00`` runtime.Unknown protobuf values, so export-tree and the
# decode pipeline can be tested without spinning up etcd.

from __future__ import annotations

import json


# ------------------------------------------------------------------ proto --

def _varint(value: int) -> bytes:
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def field_varint(num: int, value: int) -> bytes:
    return _varint((num << 3) | 0) + _varint(value)


def field_bytes(num: int, data: bytes) -> bytes:
    return _varint((num << 3) | 2) + _varint(len(data)) + data


def field_str(num: int, value: str) -> bytes:
    return field_bytes(num, value.encode("utf-8"))


def message(*parts: bytes) -> bytes:
    return b"".join(parts)


# ------------------------------------------------------------ ObjectMeta ---
# ObjectMeta field numbers (canonical, see schemas.META):
#   1=name 3=namespace 11=labels 12=annotations

def metadata(name: str, namespace: str = "") -> bytes:
    parts = [field_str(1, name)]
    if namespace:
        parts.append(field_str(3, namespace))
    return message(*parts)


def _unknown(api_version: str, kind: str, raw: bytes) -> bytes:
    typemeta = field_str(1, api_version) + field_str(2, kind)
    envelope = field_bytes(1, typemeta) + field_bytes(2, raw)
    return b"k8s\x00" + envelope


# -------------------------------------------------------------- built-ins ---

def k8s_pod(name: str, namespace: str = "default") -> bytes:
    """A ``k8s\x00`` envelope for a Pod (field 1 = spec, with metadata)."""
    meta = metadata(name, namespace)
    spec = field_bytes(1, meta)      # PodSpec.metadata (field 1)
    raw = message(spec)              # Pod field 1 = spec
    return _unknown("v1", "Pod", raw)


def k8s_namespace(name: str) -> bytes:
    """A ``k8s\x00`` envelope for a Namespace (field 1 = metadata)."""
    raw = message(field_bytes(1, metadata(name)))
    return _unknown("v1", "Namespace", raw)


# -------------------------------------------------------------- plain JSON --

def json_object(api_version: str, kind: str, name: str,
                namespace: str = ""):
    """A plain JSON value (the CRD/unstructured storage format)."""
    obj = {"apiVersion": api_version, "kind": kind,
           "metadata": {"name": name}}
    if namespace:
        obj["metadata"]["namespace"] = namespace
    return json.dumps(obj).encode("utf-8")


# ------------------------------------------------------------------ client --

class FakeKVClient:
    """In-memory stand-in for backend.KVClient over a dict of key->bytes."""

    def __init__(self, data: dict[bytes, bytes]):
        self.data = data

    def get(self, key: bytes) -> dict | None:
        if key not in self.data:
            return None
        return {"key": key, "value": self.data[key],
                "create_revision": 1, "mod_revision": 1,
                "version": 1, "lease": 0}

    def iter_range(self, prefix: bytes, keys_only: bool = False, chunk: int = 500):
        start = prefix
        end = prefix + b"\xff"
        for k in sorted(k for k in self.data if start <= k < end):
            yield k, (None if keys_only else self.data[k])

    def count(self, prefix: bytes) -> int:
        return sum(1 for _ in self.iter_range(prefix, keys_only=True))


def sample_snapshot() -> FakeKVClient:
    """A tiny but realistic snapshot: pods, a namespace, CRDs, raw bytes.

    Layout chosen so the objects tree has:
      - a namespaced object (Pod under default/)
      - a cluster-scoped object (Namespace under (cluster-scoped)/)
      - a plain-JSON object (Channel CRD)
      - a value that does not decode as an object (raw bytes -> (raw)/)
    """
    data: dict[bytes, bytes] = {
        b"/kubernetes.io/pods/default/web-0": k8s_pod("web-0", "default"),
        b"/kubernetes.io/pods/default/db-0": k8s_pod("db-0", "default"),
        b"/kubernetes.io/namespaces/openshift": k8s_namespace("openshift"),
        b"/kubernetes.io/config/config.network/channels": json_object(
            "config.network/v1", "Channel", "chan-1", "default"),
        b"/openshift.io/cluster/rawblob": b"\x00\x01\x02raw\xff",
    }
    return FakeKVClient(data)
