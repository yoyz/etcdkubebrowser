# Copyright (c) 2026
#
# Decode etcd snapshot values into readable Python structures.
#
# Values stored by the kube-apiserver in etcd come in two forms:
#
#   1. Plain JSON for CRDs / unstructured objects.
#   2. ``k8s\x00`` + a protobuf ``runtime.Unknown`` envelope for built-in types:
#
#        message Unknown {
#          TypeMeta type_meta       = 1;   // {1: apiVersion, 2: kind}
#          bytes    raw             = 2;   // object serialized with k8s protobuf
#          string   content_encoding = 3;
#          string   content_type     = 4;
#        }
#
#   The inner ``raw`` is a kubernetes protobuf object whose field numbers are
#   defined by the k8s API schemas (see schemas.py). Unknown nested messages
#   are decoded generically so no data is ever lost.

from __future__ import annotations

import base64
import json

from . import schemas

WT_VARINT, WT_64BIT, WT_LEN, WT_32BIT = 0, 1, 2, 5


class DecodeError(ValueError):
    pass


def read_varint(buf: bytes, i: int) -> tuple[int, int]:
    shift = 0
    value = 0
    while True:
        if i >= len(buf):
            raise DecodeError("truncated varint")
        b = buf[i]
        i += 1
        value |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
        if shift > 70:
            raise DecodeError("varint too long")
    return value, i


def parse_fields(buf: bytes) -> list[tuple[int, int, object]]:
    """Parse raw protobuf into [(field_number, wire_type, value), ...]."""
    out = []
    i = 0
    n = len(buf)
    while i < n:
        tag, i = read_varint(buf, i)
        fnum, wt = tag >> 3, tag & 7
        if fnum == 0:
            raise DecodeError("invalid field number 0")
        if wt == WT_VARINT:
            value, i = read_varint(buf, i)
            out.append((fnum, wt, value))
        elif wt == WT_64BIT:
            if i + 8 > n:
                raise DecodeError("truncated 64-bit field")
            out.append((fnum, wt, buf[i:i + 8]))
            i += 8
        elif wt == WT_LEN:
            ln, i = read_varint(buf, i)
            if i + ln > n:
                raise DecodeError("truncated length-delimited field")
            out.append((fnum, wt, buf[i:i + ln]))
            i += ln
        elif wt == WT_32BIT:
            if i + 4 > n:
                raise DecodeError("truncated 32-bit field")
            out.append((fnum, wt, buf[i:i + 4]))
            i += 4
        else:
            raise DecodeError("unsupported wire type %d (field %d)" % (wt, fnum))
    return out


def _to_str(val: bytes) -> str:
    return val.decode("utf-8", errors="replace")


def _looks_printable(val: bytes) -> bool:
    if not val:
        return True
    try:
        val.decode("ascii")
    except UnicodeDecodeError:
        return False
    return not any(ord(c) < 32 and c not in "\t\n\r" for c in val.decode("ascii"))


def generic_value(val: object, wt: int) -> object:
    """Render an unschematized field value to a Python primitive."""
    if wt == WT_VARINT:
        return val
    if wt in (WT_32BIT, WT_64BIT):
        return val.hex()
    assert isinstance(val, bytes)
    if _looks_printable(val):
        return _to_str(val)
    try:
        return json.loads(val.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    try:
        fields = parse_fields(val)
        if fields:
            return generic_message(val)
    except DecodeError:
        pass
    return base64.b64encode(val).decode("ascii")


def generic_message(buf: bytes) -> dict[str, object]:
    out: dict[str, object] = {}
    for fnum, wt, val in parse_fields(buf):
        out["f%d" % fnum] = generic_value(val, wt)
    return out


def _decode_map(entry_bytes: bytes, value_type: tuple) -> dict:
    result: dict = {}
    try:
        for fnum, wt, val in parse_fields(entry_bytes):
            if fnum == 1:
                key = _to_str(val)
            elif fnum == 2:
                result.setdefault(key, generic_value(val, wt))
    except DecodeError:
        result["<unparseable>"] = base64.b64encode(entry_bytes).decode("ascii")
    return result


def _schema(name):
    if name is None:
        return None
    return schemas.SCHEMAS.get(name)


def _conv(type_, val, wt):
    """Convert a wire value using a schema type tuple."""
    if wt == WT_LEN:
        if type_ == ("str",):
            return _to_str(val)
        if type_ == ("bytes",):
            return base64.b64encode(val).decode("ascii")
        if type_ == ("any",):
            return generic_value(val, wt)
        if type_[0] == "map":
            return _decode_map(val, type_[1])
        if type_[0] == "msg":
            return decode_message(val, _schema(type_[1]))
        if type_[0] == "rep":
            return _conv(type_[1], val, wt)
        if type_[0] == "json":
            try:
                return json.loads(val.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return _to_str(val)
        raise DecodeError("bad schema type %r for length field" % (type_,))
    if wt == WT_VARINT:
        if type_ == ("bool",):
            return bool(val)
        if type_[0] in ("int", "uint", "int32", "int64", "uint32", "uint64", "sint"):
            return val
        if type_ == ("float",):
            return val
        if type_ == ("str",):
            return str(val)
        if type_ == ("any",):
            return val
        raise DecodeError("bad schema type %r for varint field" % (type_,))
    # fixed 32/64 bit
    if type_ == ("float",):
        import struct

        if wt == WT_64BIT:
            return struct.unpack("<d", val)[0]
        return struct.unpack("<f", val)[0]
    return val.hex()


def decode_message(buf: bytes, schema) -> dict[str, object]:
    """Decode a protobuf message using a field-number schema (or generically)."""
    if schema is None:
        return generic_message(buf)
    out: dict[str, object] = {}
    for fnum, wt, val in parse_fields(buf):
        spec = schema.get(fnum)
        if spec is None:
            name = "f%d" % fnum
            out[name] = generic_value(val, wt)
            continue
        name, type_ = spec
        try:
            if type_[0] == "rep":
                items = out.setdefault(name, [])
                if not isinstance(items, list):
                    items = out[name] = [items]
                items.append(_conv(type_[1], val, wt))
            elif type_[0] == "map":
                merged = out.setdefault(name, {})
                if not isinstance(merged, dict):
                    merged = out[name] = {}
                merged.update(_conv(type_, val, wt))
            else:
                out[name] = _conv(type_, val, wt)
        except DecodeError:
            out[name] = generic_value(val, wt)
    return out


def decode_k8s(payload: bytes) -> dict[str, object]:
    """Decode the body of a value whose first 4 bytes are ``k8s\\x00``."""
    unknown = {}
    for fnum, wt, val in parse_fields(payload):
        if wt != WT_LEN:
            continue
        if fnum == 1:
            tm = {}
            for f2, _w2, v2 in parse_fields(val):
                if f2 == 1:
                    tm["apiVersion"] = _to_str(v2)
                elif f2 == 2:
                    tm["kind"] = _to_str(v2)
            unknown["typeMeta"] = tm
        elif fnum == 2:
            unknown["raw"] = val
        elif fnum == 3:
            unknown["contentEncoding"] = _to_str(val)
        elif fnum == 4:
            unknown["contentType"] = _to_str(val)
    typemeta = unknown.get("typeMeta", {})
    kind = typemeta.get("kind") or "Unknown"
    api_version = typemeta.get("apiVersion") or ""
    raw = unknown.get("raw", b"")
    schema = schemas.for_kind(kind, api_version)
    try:
        obj = decode_message(raw, schema)
    except DecodeError:
        obj = generic_message(raw) if raw else {}
    return {
        "apiVersion": api_version,
        "kind": kind,
        "object": obj,
    }


def decode_value(value: bytes) -> dict[str, object]:
    """Decode a raw etcd value into a dict with a stable shape.

    Returns one of:
      {"format": "json",  "data": <parsed json>}
      {"format": "k8s",   "apiVersion": ..., "kind": ..., "object": {...}}
      {"format": "raw",   "data": <base64>, "size": <int>}
    """
    if value.startswith(b"{") or value.startswith(b"["):
        try:
            return {"format": "json", "data": json.loads(value.decode("utf-8"))}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"format": "raw", "data": base64.b64encode(value).decode("ascii"), "size": len(value)}
    if value.startswith(b"k8s\x00"):
        try:
            decoded = decode_k8s(value[4:])
            decoded["format"] = "k8s"
            return decoded
        except DecodeError as exc:
            return {"format": "raw", "data": base64.b64encode(value).decode("ascii"), "size": len(value),
                    "note": str(exc)}
    if _looks_printable(value):
        return {"format": "json", "data": _to_str(value)}
    return {"format": "raw", "data": base64.b64encode(value).decode("ascii"), "size": len(value)}
