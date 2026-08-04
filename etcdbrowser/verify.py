# Copyright (c) 2026
#
# Decode adherence analysis: scan a snapshot and report how well the bundled
# field-number schemas match the actual protobuf wire data. Run it on any
# snapshot to check that the schemas still hold (the OpenShift serialization
# is canonical k8s.io/apimachinery; if a different apiserver renumbers fields,
# this report will flag it).

from __future__ import annotations

from collections import Counter, defaultdict

from . import decode, schemas

WT_VARINT, WT_64BIT, WT_LEN, WT_32BIT = decode.WT_VARINT, decode.WT_64BIT, decode.WT_LEN, decode.WT_32BIT


def expected_wire_types(type_) -> set[int] | None:
    """Wire types a schema type tuple may legally be encoded as."""
    kind = type_[0]
    if kind in ("str", "bytes", "json", "msg", "map"):
        return {WT_LEN}
    if kind == "rep":
        return expected_wire_types(type_[1])
    if kind in ("bool", "int", "int32", "int64", "uint", "uint32", "uint64", "sint"):
        return {WT_VARINT}
    if kind == "float":
        return {WT_64BIT, WT_32BIT}
    if kind == "any":
        return {WT_VARINT, WT_64BIT, WT_LEN, WT_32BIT}
    return None


def analyze_message(raw: bytes, schema) -> dict:
    """Compare raw protobuf fields against a schema; count coverage."""
    res = {"fields": 0, "known": 0, "unknown": 0, "mismatched": 0, "unknown_nums": Counter()}
    if schema is None:
        return res
    try:
        fields = decode.parse_fields(raw)
    except decode.DecodeError:
        res["mismatched"] += 1
        return res
    for fnum, wt, _val in fields:
        res["fields"] += 1
        spec = schema.get(fnum)
        if spec is None:
            res["unknown"] += 1
            res["unknown_nums"][fnum] += 1
            continue
        res["known"] += 1
        _name, type_ = spec
        expected = expected_wire_types(type_)
        if expected is not None and wt not in expected:
            res["mismatched"] += 1
    return res


def _inner_raw(value: bytes) -> bytes | None:
    """Extract the ``runtime.Unknown.raw`` payload from a k8s\\x00 value."""
    if not value.startswith(b"k8s\x00"):
        return None
    try:
        for fnum, wt, val in decode.parse_fields(value[4:]):
            if fnum == 2 and wt == WT_LEN:
                return val
    except decode.DecodeError:
        return None
    return None


def _metadata_raw(raw: bytes) -> bytes | None:
    try:
        for fnum, wt, val in decode.parse_fields(raw):
            if fnum == 1 and wt == WT_LEN:
                return val
    except decode.DecodeError:
        return None
    return None


def analyze(client) -> dict:
    """Scan the whole snapshot; return an adherence report dict."""
    report = {
        "values": 0,
        "json": 0,
        "k8s": 0,
        "raw": 0,
        "k8s_with_metadata": 0,
        "k8s_without_metadata": 0,
        "top_level": {"fields": 0, "known": 0, "unknown": 0, "mismatched": 0},
        "metadata": {"fields": 0, "known": 0, "unknown": 0, "mismatched": 0},
        "kinds": defaultdict(dict),
    }

    for _key, value in client.iter_range(b"/", keys_only=False):
        report["values"] += 1
        dec = decode.decode_value(value)
        fmt = dec.get("format")
        if fmt == "json":
            report["json"] += 1
            continue
        if fmt != "k8s":
            report["raw"] += 1
            continue
        report["k8s"] += 1
        kind = dec.get("kind") or "Unknown"
        obj = dec.get("object") or {}
        has_meta = isinstance(obj, dict) and "metadata" in obj
        if has_meta:
            report["k8s_with_metadata"] += 1
        else:
            report["k8s_without_metadata"] += 1

        kinfo = report["kinds"][kind]
        kinfo["count"] = kinfo.get("count", 0) + 1
        kinfo["with_metadata"] = kinfo.get("with_metadata", 0) + int(has_meta)
        tl = kinfo.setdefault("top", {"fields": 0, "known": 0, "unknown": 0, "mismatched": 0})
        md = kinfo.setdefault("metadata", {"fields": 0, "known": 0, "unknown": 0, "mismatched": 0})

        raw = _inner_raw(value)
        if raw is None:
            continue
        schema = schemas.for_kind(kind, dec.get("apiVersion") or "")
        a = analyze_message(raw, schema)
        for k in ("fields", "known", "unknown", "mismatched"):
            tl[k] += a[k]
            report["top_level"][k] += a[k]
        if a["unknown_nums"]:
            kinfo.setdefault("unknown_nums", Counter()).update(a["unknown_nums"])

        meta_raw = _metadata_raw(raw)
        if meta_raw is not None:
            b = analyze_message(meta_raw, schemas.META)
            for k in ("fields", "known", "unknown", "mismatched"):
                md[k] += b[k]
                report["metadata"][k] += b[k]
            if b["unknown_nums"]:
                kinfo.setdefault("meta_unknown_nums", Counter()).update(b["unknown_nums"])

    for kinfo in report["kinds"].values():
        for section in ("top", "metadata"):
            s = kinfo[section]
            s["known_pct"] = (100.0 * s["known"] / s["fields"]) if s["fields"] else 100.0
            s["unknown_pct"] = (100.0 * s["unknown"] / s["fields"]) if s["fields"] else 0.0
    report["top_level"]["known_pct"] = (100.0 * report["top_level"]["known"] /
                                        report["top_level"]["fields"]) if report["top_level"]["fields"] else 100.0
    report["metadata"]["known_pct"] = (100.0 * report["metadata"]["known"] /
                                       report["metadata"]["fields"]) if report["metadata"]["fields"] else 100.0
    return report


def render(report: dict, kind_limit: int = 12) -> str:
    out: list[str] = []
    out.append("Decode adherence report")
    out.append("=======================")
    out.append("values scanned   : %d" % report["values"])
    out.append("  json           : %d" % report["json"])
    out.append("  k8s protobuf   : %d" % report["k8s"])
    out.append("  raw bytes      : %d" % report["raw"])
    out.append("")
    k8s = report["k8s"]
    with_m = report["k8s_with_metadata"]
    pct = (100.0 * with_m / k8s) if k8s else 100.0
    out.append("k8s objects      : %d" % k8s)
    out.append("  with metadata  : %d (%.1f%%)" % (with_m, pct))
    out.append("  without        : %d" % report["k8s_without_metadata"])
    out.append("")

    for label, section in (("top-level fields", report["top_level"]),
                           ("metadata fields", report["metadata"])):
        f_ = section["fields"]
        out.append("%-17s : %4d fields, %3d known (%.1f%%), %3d unknown, %3d wire-mismatch" % (
            label, f_, section["known"], section["known_pct"],
            section["unknown"], section["mismatched"]))

    bad = []
    for kind, kinfo in report["kinds"].items():
        for section_name, label in (("top", "top"), ("metadata", "meta")):
            s = kinfo[section_name]
            if s["unknown"] or s["mismatched"]:
                bad.append((kind, label, s["unknown"] + s["mismatched"], s))
    bad.sort(key=lambda t: -t[2])

    if bad:
        out.append("")
        out.append("Kinds with unknown fields / wire mismatches (top %d):" % kind_limit)
        out.append("  %-32s %7s %10s %10s %10s" % ("kind", "objects", "section", "unknown", "mismatch"))
        for kind, label, score, s in bad[:kind_limit]:
            out.append("  %-32s %7d %10s %10d %10d" % (
                kind[:32], report["kinds"][kind]["count"], label,
                s["unknown"], s["mismatched"]))
        out.append("")
        out.append("  Unknown top-level field numbers (across all kinds):")
        top_unknown = Counter()
        for kinfo in report["kinds"].values():
            top_unknown.update(kinfo.get("unknown_nums", Counter()))
        for fnum, count in sorted(top_unknown.items()):
            out.append("    field %d : %d occurrences" % (fnum, count))
        out.append("")
        out.append("  Unknown metadata field numbers:")
        meta_unknown = Counter()
        for kinfo in report["kinds"].values():
            meta_unknown.update(kinfo.get("meta_unknown_nums", Counter()))
        for fnum, count in sorted(meta_unknown.items()):
            out.append("    field %d : %d occurrences" % (fnum, count))
    else:
        out.append("")
        out.append("All decoded fields are covered by the schemas.")
    return "\n".join(out) + "\n"
