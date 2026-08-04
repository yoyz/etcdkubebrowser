# Copyright (c) 2026
#
# Object-centric view of an etcd snapshot: build a Kubernetes-object tree
# (namespace -> kind -> name) from decoded values, instead of the raw storage
# key trie. Values that do not look like Kubernetes objects (raw bytes, JSON
# without a kind/metadata.name shape) are kept in a "(raw)" bucket so they can
# still be examined.

from __future__ import annotations

from . import decode


class Node:
    __slots__ = ("name", "children", "parent", "key", "count")

    def __init__(self, name: str, parent: "Node | None" = None):
        self.name = name
        self.children: dict[str, Node] = {}
        self.parent = parent
        self.key: bytes | None = None
        self.count = 0

    def is_leaf(self) -> bool:
        return self.key is not None


CLUSTER = "(cluster-scoped)"
RAW = "(raw)"


def _object_segments(kind: object, meta: object) -> list[str] | None:
    """Turn a kind + metadata object into namespace -> kind -> name segments."""
    if not isinstance(kind, str) or not kind:
        return None
    if not isinstance(meta, dict):
        return None
    name = meta.get("name")
    if not isinstance(name, str) or not name:
        return None
    ns = meta.get("namespace")
    if isinstance(ns, str) and ns:
        return [ns, kind, name]
    return [CLUSTER, kind, name]


def segments_for(decoded: dict) -> list[str] | None:
    """Map a decoded value to its virtual browse-path segments.

    Returns None when the value does not look like a browsable object; the
    caller then falls back to the "(raw)" bucket.
    """
    fmt = decoded.get("format")
    if fmt == "k8s":
        obj = decoded.get("object")
        if isinstance(obj, dict):
            return _object_segments(decoded.get("kind"), obj.get("metadata"))
        return None
    if fmt == "json":
        data = decoded.get("data")
        if isinstance(data, dict):
            return _object_segments(data.get("kind"), data.get("metadata"))
        return None
    return None


def object_paths(client):
    """Yield (virtual_path_bytes, etcd_key) for every value under "/"."""
    for key, value in client.iter_range(b"/", keys_only=False):
        decoded = decode.decode_value(value)
        segs = segments_for(decoded)
        if segs is None:
            segs = [RAW] + [s for s in
                            key.decode("utf-8", errors="replace").split("/") if s]
        yield ("/" + "/".join(segs)).encode("utf-8"), key


def build_tree(entries: list[tuple[bytes, bytes | None]]) -> Node:
    """Build a Node trie from (path_bytes, etcd_key_or_None) entries.

    Internal nodes accumulate a ``count`` of entries below them; leaf nodes
    carry the original etcd ``key`` so the value pane / export can fetch it.
    """
    root = Node("/")
    for path, key in entries:
        node = root
        for seg in [s for s in path.decode("utf-8", errors="replace").split("/") if s]:
            child = node.children.get(seg)
            if child is None:
                child = Node(seg, parent=node)
                node.children[seg] = child
            node = child
            node.count += 1
        node.key = key
    return root
