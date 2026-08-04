# etcdbrowser

**Version 0.0.2**

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
python3 -S etcdbrowser.py browse --view objects   # object view by default

# headless export of everything under a prefix
python3 -S etcdbrowser.py export /kubernetes.io kubernetes.io.json

# report how well the decode schemas match this snapshot's wire data
python3 -S etcdbrowser.py verify

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
| `t` | toggle keys (etcd storage) <-> objects (namespace/kind) view |
| `y` | toggle JSON / YAML in the value panel |
| `e` | open the current object in `$EDITOR` (or nano/vi/vim) |
| `E` | export current entry (prompts for json or yaml) |
| `c` | clear value cache |
| `?` | help |
| `q` | quit |

The **objects view** (default via `browse --view objects`) groups decoded values
by `namespace -> kind -> name` (OpenShift-style), with cluster-scoped objects
(Node, ClusterOperator, ClusterVersion, ...) under `(cluster-scoped)`. Values
that do not decode as Kubernetes objects are kept under `(raw)` so they can be
examined.

Exports are written to `tmp/export/<path>.json` (or `.yaml`).

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

Coverage on the bundled snapshot: **every k8s object decodes its metadata** —
0 objects end up without a name/namespace, and `verify` reports **100 %
schema adherence** (0 unknown fields, 0 wire-type mismatches across all
~207k decoded fields). The `spec`/`status` of the common workload and storage
kinds (Pod, Deployment, StatefulSet, DaemonSet, Job, CronJob, Node, PV, PVC,
Service, PDB, …) are decoded to named fields as well. The only values kept in
the `(raw)` bucket are the internal `RangeAllocation` bitmaps (empty metadata
name), which have no usable identity to group by.

## Decode adherence (`verify`)

The schemas follow the canonical `k8s.io/api` + `k8s.io/apimachinery`
`generated.proto` field numbers (verified against the snapshot's wire data and
against upstream sources; the `openshift/kubernetes` fork is field-identical
to upstream). `etcdbrowser.py verify` checks a snapshot against those schemas
and reports, per kind, any unknown field numbers or wire-type mismatches — so
if a different apiserver ever renumbers fields, the report flags it instead of
silently producing `f<number>` output. `verify --json out.json` also writes the
aggregate stats.

## Layout

```
etcdbrowser.py          CLI
etcdbrowser/
  backend.py            snapshot restore/serve + KVClient (v3 JSON gateway)
  decode.py             protobuf parser + value decoding
  schemas.py            k8s/OpenShift field-number schemas
  objects.py            object view: namespace/kind/name tree + raw bucket
  yamlout.py            minimal stdlib YAML emitter (value view / export)
  verify.py             decode-adherence report (verify command)
  tui.py                curses browser
doc/design.md           full architecture notes
doc/protobuf.md         worked example: decoding one etcd entry byte-by-byte
etcdbackup_hub1/        local copy of the sample OpenShift backup (see NOTE)
tmp/                    runtime state, restore dir, exports (git-ignored)
```

`tmp/` (runtime state, restored etcd data dir, exports) and Python bytecode
(`__pycache__`, `*.pyc`) are git-ignored — they are regenerated on every
`open`/`browse`. The `etcdbackup_hub1/` backup is kept locally; see its `NOTE`
for provenance (pulled from a lab cluster with `cluster-backup.sh`).

## Version 0.0.2

Adds an OpenShift-style object view, YAML/editor/export improvements, canonical
decode schemas and a decode-adherence verifier:

- **objects view** (`browse --view objects`, `t` to toggle): browse by
  `namespace -> kind -> name` (OpenShift-style), cluster-scoped objects under
  `(cluster-scoped)`, undecodable values under `(raw)`; builds lazily with a
  progress indicator and starts collapsed.
- **value panel**: `y` toggles JSON/YAML (`yamlout.py`, stdlib YAML emitter);
  `e` opens the current object in `$EDITOR` (nano/vi/vim fallback) as a clean
  manifest; `E` exports the current entry and prompts for json/yaml.
- **decoding**: schemas rewritten to the canonical `k8s.io/api` +
  `k8s.io/apimachinery` + `openshift/api` `generated.proto` field numbers
  (the bundled schemas were wrong for several meta types, not an OpenShift
  fork difference). Every k8s object now keeps its metadata; the `spec`/`status`
  of the common workload/storage kinds decode to named fields. `decode_message`
  is per-field resilient.
- **`verify` command**: reports per-kind unknown field numbers / wire-type
  mismatches vs the schemas. On the bundled snapshot: 100 % adherence
  (0 unknown, 0 mismatches).
- New docs: `doc/protobuf.md` (byte-by-byte decoding walkthrough), expanded
  `doc/design.md`.

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

Known limitations:

- requires the `etcd` / `etcdctl` binaries to be installed;
- no packaging/install step yet — run from the repo root;
- snapshot restore is offline and local-only (no cluster modes yet).
