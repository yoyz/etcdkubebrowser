# Copyright (c) 2026
#
# curses TUI for browsing an opened etcd snapshot: a key tree on the left, a
# decoded value view on the right, with search, value scrolling and JSON export.

from __future__ import annotations

import curses
import json
import os
import shlex
import shutil
import subprocess

from . import decode
from . import yamlout
from .backend import KVClient
from .objects import Node, build_tree, object_paths


def wrap_lines(lines, width: int) -> list[str]:
    """Wrap a list of lines to ``width`` columns (breaks on spaces, else mid-word)."""
    if width <= 1:
        return [ln[: max(width, 1)] for ln in lines]
    out = []
    for ln in lines:
        if len(ln) <= width:
            out.append(ln)
            continue
        while len(ln) > width:
            cut = ln.rfind(" ", 0, width + 1)
            if cut <= 0:
                cut = width
            out.append(ln[:cut])
            ln = ln[cut:].lstrip()
        out.append(ln)
    return out


class Browser:
    def __init__(self, client: KVClient, snapshot: str, view: str = "keys"):
        self.client = client
        self.snapshot = snapshot
        self.view = view
        self.root = Node("/")
        self.all_keys: list[bytes] = []
        self.filter = ""
        self.filtered_keys: list[bytes] = []
        self.entries: list[tuple[bytes, bytes | None]] = []
        self.obj_entries: list[tuple[bytes, bytes]] | None = None
        self.expanded: set[Node] = set()
        self.visible: list[Node] = []
        self.sel = 0
        self.top = 0
        self.voff = 0
        self.value_cache: dict[bytes, dict] = {}
        self._val_lines: list[str] = []
        self._val_node_id: int | None = None
        self._H = 24
        self._W = 80
        self.status = ""
        self.value_fmt = "json"
        self.export_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                       "tmp", "export")

    # ------------------------------------------------------------ loading --

    def load(self, stdscr=None) -> None:
        self.all_keys = [k for k, _ in self.client.iter_range(b"/", keys_only=True)]
        self.apply_filter(stdscr)

    def ensure_objects(self, stdscr=None) -> None:
        if self.obj_entries is not None:
            return
        self.obj_entries = []
        n = 0
        for item in object_paths(self.client):
            self.obj_entries.append(item)
            n += 1
            if stdscr is not None and n % 150 == 0:
                self.status = "indexing objects... %d keys" % n
                self.draw(stdscr)
        self.status = ""

    def apply_filter(self, stdscr=None) -> None:
        needle = self.filter.encode("utf-8") if self.filter else None
        if self.view == "objects":
            self.ensure_objects(stdscr)
            assert self.obj_entries is not None
            if needle is None:
                self.entries = list(self.obj_entries)
            else:
                self.entries = [(p, k) for p, k in self.obj_entries if needle in p]
        else:
            if needle is None:
                keys = list(self.all_keys)
            else:
                keys = [k for k in self.all_keys if needle in k]
            self.entries = [(k, k) for k in keys]
        self.root = build_tree(self.entries)
        self.expanded = set()

        def expand(node: Node, depth: int) -> None:
            if depth >= 1:
                return
            for child in node.children.values():
                self.expanded.add(child)
                expand(child, depth + 1)

        if self.view == "keys":
            expand(self.root, 0)
        self.sel = 0
        self.top = 0
        self.voff = 0
        self.recompute_visible()

    def toggle_view(self, stdscr=None) -> None:
        self.view = "keys" if self.view == "objects" else "objects"
        self.filter = ""
        self.apply_filter(stdscr)

    def recompute_visible(self) -> None:
        self.visible = []
        stack = list(reversed(sorted(self.root.children.items(), key=lambda kv: kv[0])))
        while stack:
            name, node = stack.pop()
            self.visible.append(node)
            if node in self.expanded and not node.is_leaf():
                for cname, child in sorted(node.children.items(),
                                           key=lambda kv: kv[0], reverse=True):
                    stack.append((cname, child))

    # ------------------------------------------------------------ select --

    def current(self) -> Node | None:
        if 0 <= self.sel < len(self.visible):
            return self.visible[self.sel]
        return None

    def move(self, delta: int) -> None:
        n = len(self.visible)
        if n == 0:
            return
        self.sel = max(0, min(n - 1, self.sel + delta))
        if self.sel < self.top:
            self.top = self.sel
        elif self.sel >= self.top + self._view_h:
            self.top = self.sel - self._view_h + 1

    def toggle(self) -> None:
        node = self.current()
        if node is None or node.is_leaf():
            return
        if node in self.expanded:
            self.expanded.discard(node)
        else:
            self.expanded.add(node)
        self.recompute_visible()

    def collapse_to_parent(self) -> None:
        node = self.current()
        if node is None:
            return
        if node in self.expanded and not node.is_leaf():
            self.expanded.discard(node)
            self.recompute_visible()
            return
        if node.parent is not None and node.parent.parent is not None:
            try:
                self.sel = self.visible.index(node.parent)
            except ValueError:
                pass
            self.expanded.discard(node.parent)
            self.recompute_visible()

    def prefix_of(self, node: Node) -> bytes:
        parts = []
        cur = node
        while cur.parent is not None:
            parts.append(cur.name)
            cur = cur.parent
        return ("/" + "/".join(reversed(parts))).encode("utf-8")

    def _depth(self, node: Node) -> int:
        d = 0
        cur = node.parent
        while cur is not None and cur.parent is not None:
            d += 1
            cur = cur.parent
        return d

    # ------------------------------------------------------------- value --

    def fetch(self, key: bytes):
        if key in self.value_cache:
            return self.value_cache[key]
        kv = self.client.get(key)
        if kv is None:
            return None
        decoded = decode.decode_value(kv["value"])
        decoded["_meta"] = {"key": key.decode("utf-8", errors="replace"),
                            "create_revision": kv["create_revision"],
                            "mod_revision": kv["mod_revision"],
                            "version": kv["version"], "lease": kv["lease"],
                            "size": len(kv["value"])}
        self.value_cache[key] = decoded
        return decoded

    def _render_obj(self, obj, width: int) -> list[str]:
        if self.value_fmt == "yaml":
            try:
                return yamlout.dumps(obj).split("\n")
            except Exception as exc:
                return ["<yaml render error: %s>" % exc]
        return _json_lines(obj, width)

    def value_lines(self, width: int) -> list[str]:
        node = self.current()
        if node is None:
            return []
        if id(node) == self._val_node_id and self._val_lines:
            return self._val_lines
        self._val_node_id = id(node)
        lines: list[str] = []
        if node.is_leaf():
            data = self.fetch(node.key)
            if data is None:
                lines.append("(key disappeared)")
            else:
                fmt = data.get("format")
                meta = data.get("_meta", {})
                lines.append("KEY   %s" % meta.get("key", node.key.decode("utf-8", errors="replace")))
                lines.append("REV   create=%s mod=%s version=%s lease=%s size=%sB" % (
                    meta.get("create_revision"), meta.get("mod_revision"),
                    meta.get("version"), meta.get("lease"), meta.get("size")))
                lines.append("FMT   %s view  (y toggles json/yaml)" % self.value_fmt)
                lines.append("-" * max(width, 10))
                if fmt == "k8s":
                    lines.append("KIND  %s (%s)" % (data.get("kind"), data.get("apiVersion")))
                    obj = data.get("object", {})
                    if isinstance(obj, dict):
                        m = obj.get("metadata") or {}
                        lines.append("OBJ   %s/%s  ns=%s" % (m.get("name"), m.get("uid"), m.get("namespace")))
                    lines.append("")
                    lines.extend(self._render_obj(obj, width))
                elif fmt == "json":
                    lines.extend(self._render_obj(data.get("data"), width))
                else:
                    lines.append("RAW   base64, %s bytes" % data.get("size", 0))
                    lines.extend(self._render_obj(data.get("data"), width))
        else:
            prefix = self.prefix_of(node)
            lines.append("PATH  %s" % prefix.decode("utf-8", errors="replace"))
            lines.append("KEYS  %d under this prefix" % node.count)
            lines.append("CHILDREN")
            for k in sorted(node.children.keys())[:60]:
                child = node.children[k]
                suffix = " (%d)" % child.count if not child.is_leaf() else ""
                lines.append("  %s%s %s" % ("+" if not child.is_leaf() else " ", k, suffix))
            if len(node.children) > 60:
                lines.append("  ... and %d more" % (len(node.children) - 60))
        wrapped = wrap_lines(lines, max(width - 1, 1))
        self._val_lines = wrapped
        return wrapped

    def value_scroll(self, delta: int) -> None:
        n = len(self._val_lines)
        if n:
            self.voff = max(0, min(n - 1, self.voff + delta))

    # ------------------------------------------------------- edit / export --

    def _safe_name(self, name: str) -> str:
        safe = name.strip("/").replace("/", "__")
        return safe or "all"

    def export_path(self, prefix: str, fmt: str = "json") -> str:
        os.makedirs(self.export_dir, exist_ok=True)
        return os.path.join(self.export_dir, "%s.%s" % (self._safe_name(prefix), fmt))

    def _write_obj(self, path: str, obj, fmt: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            if fmt == "yaml":
                fh.write(yamlout.dumps(obj))
            else:
                json.dump(obj, fh, indent=2, ensure_ascii=False, default=str)

    def _leaf_payload(self, key: bytes):
        """The decoded object itself (not the ``format``/``_meta`` envelope).

        For ``k8s`` values this merges apiVersion/kind on top of the decoded
        object so the result reads as a proper manifest; for plain JSON (CRDs)
        it is the parsed document; for raw bytes it is the base64 blob.
        """
        data = self.fetch(key)
        if data is None:
            return None
        fmt = data.get("format")
        if fmt == "k8s":
            out = {"apiVersion": data.get("apiVersion"), "kind": data.get("kind")}
            obj = data.get("object") or {}
            if isinstance(obj, dict):
                out.update(obj)
            return out
        if fmt == "json":
            return data.get("data")
        return data.get("data")

    def _current_data(self, node: Node):
        if node.is_leaf():
            return self._leaf_payload(node.key)
        if self.view == "objects":
            keys = [k for k in self._subtree_keys(node) if k is not None]
            sub = {k.decode("utf-8", errors="replace"): self._leaf_payload(k) for k in keys}
            return {"count": len(sub), "entries": sub}
        prefix = self.prefix_of(node)
        out: dict = {}
        n = 0
        for key, value in self.client.iter_range(prefix, keys_only=False):
            out[key.decode("utf-8", errors="replace")] = decode.decode_value(value)
            n += 1
        return {"count": n, "entries": out}

    def _export_path_for_node(self, node: Node, fmt: str) -> str:
        if node.is_leaf():
            return self.export_path(node.key.decode("utf-8", errors="replace"), fmt)
        return self.export_path(self.prefix_of(node).decode("utf-8", errors="replace"), fmt)

    def export_interactive(self, stdscr) -> None:
        node = self.current()
        if node is None:
            return
        res = self.prompt(stdscr, "export format (json/yaml)")
        if res is None:
            return
        fmt = res.strip().lower()
        if fmt not in ("json", "yaml"):
            self.status = "export cancelled (bad format %r)" % fmt
            return
        self.export(fmt)

    def export(self, fmt: str = "json") -> None:
        node = self.current()
        if node is None:
            return
        try:
            path = self._export_path_for_node(node, fmt)
            self._write_obj(path, self._current_data(node), fmt)
            self.status = "exported -> %s" % path
        except Exception as exc:
            self.status = "export failed: %s" % exc

    def _pick_editor(self) -> str | None:
        env = os.environ.get("EDITOR")
        if env:
            parts = shlex.split(env)
            if parts:
                return parts[0]
        for name in ("nano", "vi", "vim"):
            if shutil.which(name):
                return name
        return None

    def launch_editor(self, stdscr) -> None:
        node = self.current()
        if node is None:
            return
        try:
            editor = self._pick_editor()
            if editor is None:
                self.status = "no editor found (set $EDITOR or install nano/vi/vim)"
                return
            data = self._current_data(node)
            fmt = self.value_fmt
            path = self._export_path_for_node(node, fmt)
            self._write_obj(path, data, fmt)
            curses.def_prog_mode()
            curses.endwin()
            try:
                subprocess.call([editor, path])
            finally:
                curses.reset_prog_mode()
                stdscr.refresh()
            self.status = "edited -> %s" % path
        except Exception as exc:
            self.status = "editor failed: %s" % exc

    def _subtree_keys(self, node: Node) -> list[bytes]:
        """Every etcd key below ``node`` (leaf keys only)."""
        keys: list[bytes] = []
        stack = [node]
        while stack:
            cur = stack.pop()
            if cur.is_leaf():
                if cur.key is not None:
                    keys.append(cur.key)
            else:
                stack.extend(cur.children.values())
        return keys

    # -------------------------------------------------------------- input --

    def prompt(self, stdscr, title: str) -> str | None:
        buf = ""
        while True:
            stdscr.move(self._H - 1, 0)
            stdscr.clrtoeol()
            stdscr.addstr(self._H - 1, 0, "%s: %s" % (title, buf))
            stdscr.refresh()
            ch = stdscr.getch()
            if ch in (curses.KEY_ENTER, 10, 13):
                return buf
            if ch in (27, curses.KEY_CANCEL):
                return None
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                buf = buf[:-1]
            elif 32 <= ch < 127:
                buf += chr(ch)

    # ------------------------------------------------------------- render --

    def run(self, stdscr) -> None:
        curses.curs_set(0)
        stdscr.keypad(True)
        stdscr.timeout(300)
        self._H, self._W = stdscr.getmaxyx()
        self._view_h = max(1, self._H - 2)
        self.load(stdscr)
        while True:
            H, W = stdscr.getmaxyx()
            self._H, self._W = H, W
            self._view_h = max(1, H - 2)
            self.draw(stdscr)
            ch = stdscr.getch()
            if ch == -1:
                continue
            if ch == curses.KEY_RESIZE:
                continue
            if ch in (ord("q"), ord("Q")):
                break
            elif ch in (curses.KEY_DOWN, ord("j")):
                self.voff = 0
                self.move(1)
            elif ch in (curses.KEY_UP, ord("k")):
                self.voff = 0
                self.move(-1)
            elif ch in (curses.KEY_PPAGE, ord("b")):
                self.voff = 0
                self.move(-self._view_h)
            elif ch in (curses.KEY_NPAGE, ord(" ")):
                self.voff = 0
                self.move(self._view_h)
            elif ch in (curses.KEY_ENTER, 10, 13, curses.KEY_RIGHT, ord("l")):
                self.voff = 0
                self.toggle()
            elif ch in (curses.KEY_LEFT, ord("h")):
                self.voff = 0
                self.collapse_to_parent()
            elif ch in (ord("g"), ord("G")):
                self.sel = 0 if ch == ord("g") else max(0, len(self.visible) - 1)
                self.top = max(0, self.sel - self._view_h + 1)
            elif ch in (ord("["), ord("]")):
                self.value_scroll(-1 if ch == ord("[") else 1)
            elif ch in (ord("{"),):
                self.voff = 0
            elif ch in (ord("/"),):
                res = self.prompt(stdscr, "filter")
                if res is not None:
                    self.filter = res
                    self.apply_filter(stdscr)
            elif ch in (ord("t"), ord("T")):
                self.toggle_view(stdscr)
            elif ch in (ord("y"),):
                self.value_fmt = "yaml" if self.value_fmt == "json" else "json"
                self._val_lines = []
                self._val_node_id = None
                self.voff = 0
            elif ch in (ord("e"),):
                self.launch_editor(stdscr)
            elif ch in (ord("E"),):
                self.export_interactive(stdscr)
            elif ch in (ord("c"),):
                self.value_cache.clear()
                self._val_lines = []
            elif ch in (ord("?"),):
                self.show_help(stdscr)

    def draw(self, stdscr) -> None:
        H, W = self._H, self._W
        left_w = max(16, min(int(W * 0.42), W // 2))
        if left_w >= W:
            left_w = W - 1
        right_w = max(1, W - left_w - 2)
        stdscr.erase()
        # header
        stdscr.attron(curses.A_BOLD)
        stdscr.addnstr(0, 0, " etcd backup browser ".center(left_w, "="), left_w)
        stdscr.attroff(curses.A_BOLD)
        head = " %s | view %s | keys %d | filter: %r " % (
            os.path.basename(self.snapshot), self.view, len(self.all_keys), self.filter)
        stdscr.addnstr(0, left_w + 1, head, right_w, curses.A_BOLD)
        # separator
        stdscr.vline(1, left_w, curses.ACS_VLINE, H - 2)

        lw = curses.newwin(H - 2, left_w, 1, 0)
        rw = curses.newwin(H - 2, right_w, 1, left_w + 1)
        lw.erase()
        rw.erase()

        for r in range(H - 2):
            idx = self.top + r
            if idx < len(self.visible):
                node = self.visible[idx]
                line = self.node_line(node)
                line = line[: max(left_w - 1, 0)]
                attr = curses.A_REVERSE if idx == self.sel else curses.A_NORMAL
                lw.addnstr(r, 0, line, max(left_w - 1, 0), attr)

        lines = self.value_lines(right_w)
        view_h = H - 2
        total = len(lines)
        if self.voff > total:
            self.voff = 0
        for r in range(view_h):
            i = self.voff + r
            if i < total:
                rw.addnstr(r, 0, lines[i][: max(right_w - 1, 0)],
                           max(right_w - 1, 0))

        # status bar
        node = self.current()
        info = ""
        if node is not None:
            info = node.name if node.is_leaf() else "%s/ (%d keys)" % (node.name, node.count)
        status = " %s | j/k move  enter expand  / filter  t view  y json/yaml  e edit  E export  [ ] scroll  q quit" % info
        if total > view_h:
            status += "  [%d-%d/%d]" % (self.voff, self.voff + view_h - 1, total)
        if self.status:
            status = self.status + " | q quit"
            self.status = ""
        stdscr.attron(curses.A_REVERSE)
        stdscr.addnstr(H - 1, 0, status, W - 1)
        stdscr.attroff(curses.A_REVERSE)

        # refresh base window first so the overlay panels win overlapping cells
        stdscr.noutrefresh()
        lw.noutrefresh()
        rw.noutrefresh()
        curses.doupdate()

    def node_line(self, node: Node) -> str:
        depth = self._depth(node)
        indent = "  " * min(depth, 60)
        if node.is_leaf():
            marker = " "
        else:
            marker = "-" if node in self.expanded else "+"
        label = "%s %s%s" % (indent, marker, node.name)
        suffix = " (%d)" % node.count if not node.is_leaf() else ""
        return label + suffix

    def show_help(self, stdscr) -> None:
        H, W = self._H, self._W
        stdscr.erase()
        lines = [
            "ETCD BACKUP BROWSER",
            "",
            "  j/k, Up/Down       move in the key tree",
            "  b / Space / PgUp/PgDn  move by page",
            "  Enter / Right / l  expand / collapse a node",
            "  Left / h           collapse node, or jump to parent",
            "  /                  filter keys by substring (empty = clear)",
            "  t                  toggle keys <-> objects view",
            "  y                  toggle JSON / YAML in the value view",
            "  [  ]               scroll the value view",
            "  g / G              go to first / last row",
            "  e                  open current object in $EDITOR (nano/vi/vim)",
            "  E                  export current entry (asks json/yaml)",
            "  c                  clear value cache",
            "  ?                  this help",
            "  q                  quit",
            "",
            "Values are decoded from the k8s 'k8s\\x00' protobuf envelope",
            "or plain JSON (CRDs). Binary payloads are shown as base64.",
            "",
            "press any key to return",
        ]
        for i, line in enumerate(lines[: H - 1]):
            stdscr.addnstr(i, 0, line, W - 1)
        stdscr.refresh()
        stdscr.getch()


def _json_lines(obj, width: int) -> list[str]:
    try:
        text = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    except Exception as exc:
        text = "<render error: %s>" % exc
    return text.split("\n")


def run(client: KVClient, snapshot: str, view: str = "keys") -> int:
    browser = Browser(client, snapshot, view=view)
    try:
        return curses.wrapper(browser.run)
    except KeyboardInterrupt:
        return 0
