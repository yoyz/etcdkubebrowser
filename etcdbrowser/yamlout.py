# Copyright (c) 2026
#
# Minimal YAML emitter (subset) for the decoded etcd values, stdlib only.
# Handles dict / list / str / int / float / bool / None / bytes (base64).

from __future__ import annotations

import base64

_NUMBERS = {"null", "true", "false", "yes", "no", "on", "off", "~"}


_ESC = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t",
        "\r": "\\r", "\b": "\\b", "\f": "\\f"}


def _quote(s: str) -> str:
    out = []
    for c in s:
        if c in _ESC:
            out.append(_ESC[c])
        elif ord(c) < 0x20 or ord(c) == 0x7F:
            out.append("\\x%02x" % ord(c))
        else:
            out.append(c)
    return '"%s"' % "".join(out)


def _has_control(s: str) -> bool:
    return any(ord(c) < 0x20 or ord(c) == 0x7F for c in s)


def _string(s: str) -> str:
    if s == "":
        return '""'
    lowered = s.lower()
    if lowered in _NUMBERS:
        return _quote(s)
    try:
        float(s)
        return _quote(s)
    except ValueError:
        pass
    if _has_control(s) or "\n" in s or "\t" in s or ": " in s or s != s.strip():
        return _quote(s)
    if s[0] in "-?:,[]{}#&*!|>'\"%@`":
        return _quote(s)
    return s


def _scalar(v: object) -> str:
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, bytes):
        return _quote(base64.b64encode(v).decode("ascii"))
    return _string(str(v))


def _scalar_or_empty(v: object) -> str:
    if isinstance(v, dict) and not v:
        return "{}"
    if isinstance(v, list) and not v:
        return "[]"
    return _scalar(v)


def _emit(v: object, out: list[str], col: int, ind: int) -> None:
    if isinstance(v, dict):
        if not v:
            out.append(" " * col + "{}")
            return
        for k, val in v.items():
            key = _string(str(k))
            if isinstance(val, (dict, list)) and val:
                out.append(" " * col + "%s:" % key)
                _emit(val, out, col + ind, ind)
            else:
                out.append(" " * col + "%s: %s" % (key, _scalar_or_empty(val)))
    elif isinstance(v, list):
        if not v:
            out.append(" " * col + "[]")
            return
        for item in v:
            if isinstance(item, dict) and item:
                items = list(item.items())
                k0, val0 = items[0]
                key0 = _string(str(k0))
                if isinstance(val0, (dict, list)) and val0:
                    out.append(" " * col + "- %s:" % key0)
                    _emit(val0, out, col + ind + 2, ind)
                else:
                    out.append(" " * col + "- %s: %s" % (key0, _scalar_or_empty(val0)))
                for k, val in items[1:]:
                    key = _string(str(k))
                    if isinstance(val, (dict, list)) and val:
                        out.append(" " * (col + 2) + "%s:" % key)
                        _emit(val, out, col + 2 + ind, ind)
                    else:
                        out.append(" " * (col + 2) + "%s: %s" % (key, _scalar_or_empty(val)))
            elif isinstance(item, list):
                out.append(" " * col + "-")
                _emit(item, out, col + ind, ind)
            else:
                out.append(" " * col + "- %s" % _scalar(item))
    else:
        out.append(" " * col + _scalar(v))


def dumps(obj: object, indent: int = 2) -> str:
    """Serialize ``obj`` to a YAML document string."""
    out: list[str] = []
    _emit(obj, out, 0, indent)
    return "\n".join(out) + "\n"
