# etcdbrowser — Design Notes

Version 0.0.1 — see README.md for usage, `doc/design.md` for architecture.

## 1. Goal

Reliably open an **etcd snapshot** (typically from an OpenShift/Kubernetes
apiserver), **browse** the stored objects visually, and **export** them as
readable JSON. The hard part is not the snapshot itself — `etcdctl snapshot
restore` handles that — but **decoding the value format** the kube-apiserver
uses, which is *not* plain JSON for built-in types.

## 2. Why values are not plain JSON

`kube-apiserver` stores built-in objects in etcd as:

```
k8s\x00
+ protobuf runtime.Unknown envelope:
    1  TypeMeta   {1: apiVersion, 2: kind}
    2  bytes raw  -> the object serialized with the k8s protobuf serializer
    3  string contentEncoding
    4  string contentType
```

The inner `raw` payload is a kubernetes protobuf object whose fields are
numbered per the k8s API schemas (`k8s.io/api` + `k8s.io/apimachinery`
`generated.proto`). CRDs and other unstructured objects are stored as plain
JSON instead. A handful of values (internal/compaction markers, or anything
else) are arbitrary bytes.

So a decoder has to know protobuf wire format **and** the field-number
schemas. This is implemented in pure stdlib (no `grpc`, `etcd3`, `urwid`…).

## 3. Architecture

```
etcdbrowser.py                CLI entry point
etcdbrowser/
  __init__.py                 package exports + __version__ = "0.0.1"
  backend.py                  snapshot verify/restore/serve + KVClient
  decode.py                   protobuf parser + value decoding
  schemas.py                  k8s/OpenShift field-number schemas
  tui.py                      curses browser
```

Data flow:

```
snapshot.db
   │  backend.open_snapshot()
   │    etcdctl snapshot status        (verify)
   │    etcdctl snapshot restore → tmp/restore-<port>/
   │    etcd serve on 127.0.0.1:22379  (detached)
   ▼
HTTP/JSON v3 gateway  (/v3/kv/range, /v3/kv/...)
   │  KVClient.iter_range()            (paged, keys_only / with values)
   ▼
decode.decode_value(bytes)  →  {"format": "json"|"k8s"|"raw", ...}
   ▼
tui.Browser (curses)   or   CLI export → JSON file
```

No Python third-party dependencies. Only external requirement: the **`etcd`
and `etcdctl` binaries** must be installed (they are only used to restore and
serve the snapshot).

## 4. Backend (`backend.py`)

- **State file** `tmp/etcdbrowser.state` (key=value lines) records `pid`,
  `client_url`, `peer_url`, `datadir`, `snapshot`, `logfile` for the running
  etcd. `read_state`/`write_state`/`close` manage it.
- **`open_snapshot`**: aborts if an etcd is already alive (from the state
  file); verifies the snapshot with `etcdctl snapshot status`; restores into
  `tmp/restore-<client_port>/`; starts etcd with `start_new_session=True`
  (so it survives the parent shell — the tool's shell kills backgrounded
  processes on timeout), waits for `/health == "true"` (up to 60s).
- **`close`**: SIGTERM → wait → SIGKILL fallback, removes the data dir
  unless `--keep-data`, deletes the state file.
- **`KVClient`**: talks to the built-in HTTP/JSON v3 gateway via stdlib
  `urllib`. `get(key)` reads one value (with revision metadata);
  `iter_range(prefix, keys_only, chunk=500)` pages over a range with
  `range_end = prefix + b"\xff"`, advancing `start = last_key + b"\x00"`
  (lexicographic successor). `count`, `list_prefixes` are convenience wrappers.
- **Gotcha**: the count reported by the gateway equals `etcdctl
  get / --prefix --keys-only | wc -l` exactly (12522 for the bundled
  snapshot). Immediately after restore the server may compact a few MVCC
  tombstone revisions, so counts can drop by a few keys in the first seconds.

## 5. Decode layer (`decode.py`)

- `read_varint` / `parse_fields`: minimal protobuf wire parser handling wire
  types varint(0), 64-bit(1), length-delimited(2), 32-bit(5).
- `generic_value` / `generic_message`: loss-less fallback — printable bytes →
  string, JSON → parsed, valid sub-message → `f<num>` dict, else base64.
- `decode_message(buf, schema)`: schema-driven decode. Supports `rep`
  (repeated → list), `map` (map entries merged via `dict.update`),
  `msg` (nested by schema name or generic), `json`, `str`, `bytes`, `bool`,
  ints, `float`. Unknown fields are kept under `f<num>` — **no data is lost**.
- `decode_k8s(payload)`: unwraps the `runtime.Unknown` envelope, resolves the
  schema via `schemas.for_kind(kind, apiVersion)`, decodes the raw body.
- `decode_value(value)` → stable shape:
  - `{"format": "json", "data": <parsed>}` — plain JSON (CRDs) or short text.
  - `{"format": "k8s", "apiVersion", "kind", "object": {...}}` — built-ins.
  - `{"format": "raw", "data": <base64>, "size": N}` — opaque bytes.
- Coverage on the bundled snapshot: **0 decode failures** across all 12.5k
  values (`json` ≈1,747, `k8s` ≈10,778).

## 6. Schemas (`schemas.py`)

- Field numbers copied from canonical `k8s.io/api/…/generated.proto` +
  `k8s.io/apimachinery/…/generated.proto`.
- Schema values are `(name, type_tuple)`; type tuples as documented at the
  top of the file. `META` (ObjectMeta), `POD_SPEC`, `CONTAINER`, `SERVICE_SPEC`,
  `SECRET` (corrected: data=2, type=3, stringData=4, immutable=5), etc.
- `SCHEMAS` maps `kind → schema`. OpenShift kinds without a hand-written
  schema and many others fall back to `GENERIC` (field-number shaped output)
  or `None` (pure generic). `for_kind(kind, api_version)` is the resolver.

## 7. TUI (`tui.py`)

- **`build_tree(keys)`**: builds a `Node` trie from all keys under `/`;
  each node has `count` (keys below it) and leaf nodes carry `key`.
- **`apply_filter`**: substring filter over key bytes; rebuilds the tree and
  auto-expands only the top level (so the initial view is ~95 rows, not 13k).
- **`recompute_visible`**: DFS over expanded nodes → flat row list.
- **Rendering**: two `curses.newwin` panels (left = tree, right = value view)
  clipped by width, a `ACS_VLINE` separator, a header and a status bar.
  `value_lines()` produces the right panel (object info + wrapped JSON, or
  PATH/KEYS/CHILDREN for internal nodes) with `[`/`]` scrolling.
- **Known curses pitfalls (fixed)**
  - Refresh order matters: `stdscr.noutrefresh()` first, then the overlay
    panels, then one `doupdate()`. A redundant early
    `lw.noutrefresh()/rw.noutrefresh()` before the status bar was drawn
    caused the panels to render blank.
  - `stdscr.keypad(True)` must be set or arrow keys are never translated
    into `KEY_UP/KEY_DOWN`. (Terminfo for xterm here maps cursor-down to
    `\x1bOB` — relevant for pty test harnesses.)
- **Export**: `e` on a leaf → decoded single object JSON; `e` on an internal
  node (and always `E`) → whole subtree `{"count", "entries": {key: decoded}}`.
  Output lands in `tmp/export/`.
- **Keys**: `j/k/arrows` move, `Enter/l/Right` expand, `h/Left` collapse,
  `/` filter, `[ ]` value scroll, `g/G` jump, `e/E` export, `c` clear cache,
  `?` help, `q` quit.

## 8. CLI (`etcdbrowser.py`)

- `status <snapshot.db>` — verify.
- `open <snapshot.db> [--client-port N]` — restore + serve, prints state.
- `browse` — curses browser (requires a running etcd).
- `export <prefix> <out.json>` — headless export.
- `close [--keep-data]` — stop etcd, remove data dir.
- `--version`.

## 9. Key observations on the bundled snapshot

- `snapshot_2026-08-04_150427.db`, 101 MB, hash `4f9242b6`, 22,010 revisions.
- 12,525 keys under `/` (12,526 with the internal `compact_rev_key`, which is
  correctly excluded because it does not start with `/`); gateway + etcdctl
  agree on the live count (12,522 after tombstone compaction).
- Two top-level groups: `kubernetes.io` (~12,47x keys) and `openshift.io`.
- Provenance (see `etcdbackup_hub1/NOTE`): pulled from `hub1.tnc.bootcamp420.lab`
  via `sudo /usr/local/bin/cluster-backup.sh /tmp/backup` + `scp`, alongside a
  `static_kuberesources` tarball. The backup directory is kept locally and is
  not part of the public repo by default.

## 10. Working conventions

- All temp/state work happens under the project's `tmp/` (see AGENTS.md).
  Never use `/tmp`.
- Run the CLI with `python3 -S etcdbrowser.py …` (stdlib only, no site
  packages interference).
- TUI pty tests are done via `script -qec "python3 -S etcdbrowser.py browse"`;
  the keypad sequences must match the terminfo (`\x1bOB` for down here).
