# Copyright (c) 2026
#
# Tree export: write the whole snapshot (or a subtree) out as a directory of
# files, one per leaf. Two layouts:
#
#   keys    - mirror the etcd storage key trie (kubernetes.io/..., openshift.io/...)
#   objects - OpenShift-style tree: namespace -> kind -> name
#             (cluster-scoped objects under "(cluster-scoped)", values that do
#              not decode as objects under "(raw)")
#
# Leaf files are JSON or YAML (yamlout.py, stdlib only). For k8s values each
# leaf is a clean manifest {apiVersion, kind, ...object} so an objects-layout
# export can be fed back to `oc apply -f`. Nothing is ever dropped: values that
# do not decode as objects are still written under "(raw)".

from __future__ import annotations

import json
import os
import re

from . import decode, objects, verify, yamlout

SAFE = re.compile(r"[^A-Za-z0-9._-]")


class ExportError(RuntimeError):
    pass


def json_safe(obj: object) -> object:
    """Recursively convert Counter/defaultdict objects into plain JSON."""
    if hasattr(obj, "items"):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    return obj


def sanitize_segment(seg: str) -> str:
    """Map one path segment to something safe for a single file-system entry.

    The objects-layout sentinels ``(cluster-scoped)`` / ``(raw)`` are kept
    verbatim so exports are recognisable; everything else is reduced to safe
    file-name characters.
    """
    if seg in (objects.CLUSTER, objects.RAW):
        return seg
    s = SAFE.sub("_", seg)
    if s in ("", ".", ".."):
        return "_"
    return s


def leaf_payload(decoded: dict) -> object:
    """The file payload for a decoded value (manifest form for k8s objects).

    k8s  -> {"apiVersion", "kind", ...object}  (clean, apply-able manifest)
    json -> the parsed document
    raw  -> the full decode envelope (format/data/size) so nothing is lost
    """
    fmt = decoded.get("format")
    if fmt == "k8s":
        out = {"apiVersion": decoded.get("apiVersion"), "kind": decoded.get("kind")}
        obj = decoded.get("object")
        if isinstance(obj, dict):
            out.update(obj)
        return out
    if fmt == "json":
        return decoded.get("data")
    return decoded


def collect(client, prefix: bytes) -> list[dict]:
    """Decode every value under ``prefix`` into ``{key, decoded}`` records."""
    records: list[dict] = []
    for key, value in client.iter_range(prefix, keys_only=False):
        records.append({"key": key, "decoded": decode.decode_value(value)})
    return records


def relative_parts(record: dict, layout: str, prefix: bytes) -> list[str]:
    """Map a record to its (un-sanitized) relative path segments."""
    key = record["key"]
    if layout == "keys":
        rest = key[len(prefix):] if key.startswith(prefix) else key
        return [s for s in rest.decode("utf-8", errors="replace").split("/") if s]
    segs = objects.segments_for(record["decoded"])
    if segs is None:
        key_str = key.decode("utf-8", errors="replace")
        segs = [objects.RAW] + [s for s in key_str.split("/") if s]
    return segs


def _init_stats(layout: str, fmt: str, values: int) -> dict:
    return {
        "layout": layout,
        "format": fmt,
        "values": values,
        "formats": {"json": 0, "k8s": 0, "raw": 0},
        "k8s": {"total": 0, "with_metadata": 0, "without_metadata": 0},
        "objects": {"total": 0, "with_metadata": 0},
        "raw": 0,
        "by_kind": {},
        "files": 0,
    }


def _kind_of(decoded: dict) -> str:
    fmt = decoded.get("format")
    if fmt == "k8s":
        return decoded.get("kind") or "Unknown"
    if fmt == "json":
        data = decoded.get("data")
        if isinstance(data, dict) and isinstance(data.get("kind"), str):
            return data["kind"]
        return objects.RAW
    return objects.RAW


def _has_metadata(decoded: dict) -> bool:
    if decoded.get("format") == "k8s":
        obj = decoded.get("object")
        return isinstance(obj, dict) and isinstance(obj.get("metadata"), dict)
    if decoded.get("format") == "json":
        data = decoded.get("data")
        return isinstance(data, dict) and isinstance(data.get("metadata"), dict)
    return False


def _is_object_shaped(decoded: dict) -> bool:
    """True when the value represents a Kubernetes object candidate.

    Plain raw bytes are excluded (they are internal markers, not objects), so
    they do not count against the decode ratio.
    """
    if decoded.get("format") == "k8s":
        return True
    if decoded.get("format") == "json":
        data = decoded.get("data")
        return isinstance(data, dict) and isinstance(data.get("kind"), str)
    return False


def _update_stats(stats: dict, decoded: dict) -> None:
    fmt = decoded.get("format")
    stats["formats"][fmt if fmt in stats["formats"] else "raw"] += 1
    if fmt == "k8s":
        stats["k8s"]["total"] += 1
        if _has_metadata(decoded):
            stats["k8s"]["with_metadata"] += 1
        else:
            stats["k8s"]["without_metadata"] += 1
    if fmt == "raw":
        stats["raw"] += 1
    if _is_object_shaped(decoded):
        stats["objects"]["total"] += 1
        if _has_metadata(decoded):
            stats["objects"]["with_metadata"] += 1
            kind = _kind_of(decoded)
            stats["by_kind"][kind] = stats["by_kind"].get(kind, 0) + 1


def _resolve_path(outdir: str, rel_parts: list[str], fmt: str, used: set) -> str:
    rel = "/".join(sanitize_segment(s) for s in rel_parts)
    base = os.path.join(outdir, rel + "." + fmt)
    if base not in used:
        used.add(base)
        return base
    i = 2
    while True:
        cand = os.path.join(outdir, "%s-%d.%s" % (rel, i, fmt))
        if cand not in used:
            used.add(cand)
            return cand
        i += 1


def _write(payload: object, path: str, fmt: str) -> None:
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)
    if os.path.exists(parent) and not os.path.isdir(parent):
        raise ExportError("cannot create directory over file: %s" % parent)
    with open(path, "w", encoding="utf-8") as fh:
        if fmt == "yaml":
            fh.write(yamlout.dumps(payload))
        else:
            json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)


def export_tree(client, outdir: str, layout: str = "objects", fmt: str = "json",
                prefix: str = "/") -> dict:
    """Export every leaf under ``prefix`` into ``outdir``; return stats."""
    prefix_bytes = prefix.encode("utf-8")
    records = collect(client, prefix_bytes)
    stats = _init_stats(layout, fmt, len(records))
    used: set[str] = set()
    for record in records:
        parts = relative_parts(record, layout, prefix_bytes)
        path = _resolve_path(outdir, parts, fmt, used)
        _write(leaf_payload(record["decoded"]), path, fmt)
        _update_stats(stats, record["decoded"])
    stats["files"] = len(used)

    k8s_total = stats["k8s"]["total"]
    stats["decoded_ratio"] = (
        (100.0 * stats["k8s"]["with_metadata"] / k8s_total) if k8s_total else 100.0)
    obj_total = stats["objects"]["total"]
    stats["object_ratio"] = (
        (100.0 * stats["objects"]["with_metadata"] / obj_total) if obj_total else 100.0)
    stats["outdir"] = os.path.abspath(outdir)

    try:
        stats["adherence"] = verify.analyze(client)
    except Exception as exc:  # verification is best-effort for the summary
        stats["adherence"] = {"error": str(exc)}
    stats["adherence"] = json_safe(stats["adherence"])
    return stats


def render_summary(stats: dict) -> str:
    out: list[str] = []
    out.append("tree export: layout=%s format=%s outdir=%s" % (
        stats["layout"], stats["format"], stats.get("outdir")))
    out.append("  values scanned     : %d" % stats["values"])
    out.append("  files written      : %d" % stats["files"])
    out.append("  formats            : %s" % ", ".join(
        "%s=%d" % (k, v) for k, v in stats["formats"].items() if v))
    k8s = stats["k8s"]
    out.append("  k8s objects        : %d (%d with metadata = %.1f%%)" % (
        k8s["total"], k8s["with_metadata"], stats["decoded_ratio"]))
    if stats["objects"]["total"]:
        out.append("  usable objects     : %d/%d with metadata = %.1f%%" % (
            stats["objects"]["with_metadata"], stats["objects"]["total"],
            stats["object_ratio"]))
    if stats["raw"]:
        out.append("  raw (non-object)   : %d" % stats["raw"])
    kinds = stats.get("by_kind") or {}
    if kinds:
        out.append("  kinds              : %d distinct" % len(kinds))
    return "\n".join(out) + "\n"
