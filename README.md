# etcdbrowser

**Version 0.0.1**

Open an etcd snapshot, browse its Kubernetes / OpenShift objects visually, and
export them as readable JSON.

The kube-apiserver stores built-in objects in etcd as `k8s\x00` + protobuf
(`runtime.Unknown` envelope wrapping the API object), while CRDs are plain
JSON. `etcdbrowser` decodes **both** using only the Python standard library,
then serves the data in a curses TUI.

## Requirements

- **Python 3.11+** (standard library only — no third-party packages).
- **`etcd` and `etcdctl` binaries on `PATH`** — required to restore and serve
  the snapshot locally (`etcdctl` ≥ 3.4; tested with 3.4.30). They are not
  bundled; install them from your distro or the etcd releases page.

## Usage

```sh
# verify a snapshot
python3 -S etcdbrowser.py status snapshot.db

# open (verify → restore into tmp/ → serve on 127.0.0.1:22379)
python3 -S etcdbrowser.py open snapshot.db

# interactive browser (needs a running etcd from `open`)
python3 -S etcdbrowser.py browse

# headless export of everything under a prefix
python3 -S etcdbrowser.py export /kubernetes.io kubernetes.io.json

# stop the served etcd (and delete the restored data dir)
python3 -S etcdbrowser.py close

python3 -S etcdbrowser.py --version
```

`open` and `browse` must be run in the same project directory (state is kept
in `tmp/etcdbrowser.state`).

## Browser keys

| Key | Action |
| --- | --- |
| `j` / `k` / arrows | move up / down |
| `Enter`, `l`, `Right` | expand / collapse a node |
| `h`, `Left` | collapse, or jump to parent |
| `b`, `Space`, `PgUp/PgDn` | page |
| `/` | filter keys by substring (empty = clear) |
| `[` / `]` | scroll the value panel |
| `g` / `G` | first / last row |
| `e` | export selected object (or subtree if it is a folder) |
| `E` | export the whole subtree |
| `c` | clear value cache |
| `?` | help |
| `q` | quit |

Exports are written to `tmp/export/<path>.json`.

## How it works

1. `etcdctl snapshot status` verifies the snapshot.
2. `etcdctl snapshot restore` materialises it under `tmp/`, then a local etcd
   serves it on `127.0.0.1:22379`.
3. `etcdbrowser` talks to etcd's built-in **HTTP/JSON v3 gateway**
   (`/v3/kv/…`) — no gRPC/protobuf client libraries needed.
4. `decode.py` parses each value:
   - `k8s\x00` envelope → unwrap `runtime.Unknown` → decode the inner
     protobuf body using field-number schemas from `schemas.py`;
   - plain JSON (CRDs) → parsed as-is;
   - anything else → base64 + size.
   Nothing is ever lost: unknown protobuf fields are preserved under
   `f<number>`.
5. The curses TUI renders the key tree on the left and the decoded value on
   the right.

Coverage on the bundled snapshot: **zero decode failures** over ~12.5k keys
(≈1,747 JSON, ≈10.8k k8s-protobuf objects).

## Layout

```
etcdbrowser.py          CLI
etcdbrowser/
  backend.py            snapshot restore/serve + KVClient (v3 JSON gateway)
  decode.py             protobuf parser + value decoding
  schemas.py            k8s/OpenShift field-number schemas
  tui.py                curses browser
doc/design.md           full architecture notes
etcdbackup_hub1/        local copy of the sample OpenShift backup (see NOTE)
tmp/                    runtime state, restore dir, exports (git-ignored)
```

`tmp/` (runtime state, restored etcd data dir, exports) and Python bytecode
(`__pycache__`, `*.pyc`) are git-ignored — they are regenerated on every
`open`/`browse`. The `etcdbackup_hub1/` backup is kept locally; see its `NOTE`
for provenance (pulled from a lab cluster with `cluster-backup.sh`).

## Version 0.0.1

First working version:

- reliable `open`/`close` of an etcd snapshot (restore + serve + health wait);
- pure-stdlib protobuf decoding of the `k8s\x00` `runtime.Unknown` envelope
  and the inner API objects, with generic fallback so nothing is lost;
- curses browser with tree, filter, value view/scrolling and export
  (`e` object, `E` subtree, CLI `export`);
- headless CLI export for scripting;
- verified end-to-end against an OpenShift backup (12.5k keys, 0 decode
  errors, gateway count matches `etcdctl` exactly).

Known limitations for 0.0.1:

- requires the `etcd` / `etcdctl` binaries to be installed;
- no packaging/install step yet — run from the repo root;
- snapshot restore is offline and local-only (no cluster modes yet).
