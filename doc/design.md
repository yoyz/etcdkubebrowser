# etcdbrowser — Design Notes

Version 0.0.2 — see README.md for usage, `doc/design.md` for architecture,
`doc/protobuf.md` for a byte-by-byte worked example of decoding one entry.

## 1. Goal

Reliably open an **etcd snapshot** (typically from an OpenShift/Kubernetes
apiserver), **browse** the stored objects visually, and **export** them as
readable JSON. The hard part is not the snapshot itself — `etcdctl snapshot
restore` handles that — but **decoding the value format** the kube-apiserver
uses, which is *not* plain JSON for built-in types.

## 2. Why values are not plain JSON

> See `doc/protobuf.md` for a byte-by-byte worked example of decoding one
> real entry (a Secret) end to end, and the online sources of truth for the
> field numbers.

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
  __init__.py                 package exports + __version__ = "0.0.2"
  backend.py                  snapshot verify/restore/serve + KVClient
  decode.py                   protobuf parser + value decoding
  schemas.py                  k8s/OpenShift field-number schemas
  objects.py                  object view builder (namespace/kind/name tree)
  verify.py                   decode-adherence report (verify command)
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
  A `DecodeError` raised while converting one field falls back to generic
  rendering for that field only, so a single malformed nested field never
  blanks the whole object.
- `decode_k8s(payload)`: unwraps the `runtime.Unknown` envelope, resolves the
  schema via `schemas.for_kind(kind, apiVersion)`, decodes the raw body.
- `decode_value(value)` → stable shape:
  - `{"format": "json", "data": <parsed>}` — plain JSON (CRDs) or short text.
  - `{"format": "k8s", "apiVersion", "kind", "object": {...}}` — built-ins.
  - `{"format": "raw", "data": <base64>, "size": N}` — opaque bytes.
- Coverage on the bundled snapshot: every one of the ~10.8k k8s values decodes
  with a usable `metadata` (0 objects without a name/namespace). The only
  values left in the `(raw)` object-view bucket are the two internal
  `RangeAllocation` bitmaps, whose metadata name is empty.

## 6. Schemas (`schemas.py`)

- Field numbers follow the **canonical `k8s.io/api` + `k8s.io/apimachinery`
  `generated.proto`**. Verified three ways: (a) against the raw wire data of the
  bundled snapshot, (b) against the upstream `kubernetes/apimachinery` proto,
  and (c) against the `openshift/kubernetes` fork — the fork is
  **field-identical** to upstream.
- Historical bug (fixed): the schemas originally declared several meta types
  with the wrong field numbers (e.g. `OwnerReference` as
  `1=apiVersion/2=kind/3=name/4=uid/5=bool`, whereas canonical is
  `1=kind/3=name/4=uid/5=apiVersion/6=controller/7=blockOwnerDeletion`). This
  made every object carrying `ownerReferences`/`managedFields` throw a
  `DecodeError` and fall back to generic `f<number>` decode. It was a bug in
  these schemas, **not** an OpenShift serialization difference.
- Noteworthy canonical field numbers:
  - `Time` is a message `{1: seconds, 2: nanos}` (`creationTimestamp`,
    `deletionTimestamp`, `managedFields.time`), not a plain string.
  - `ObjectMeta`: `1=name … 8=creationTimestamp, 9=deletionTimestamp,
    11=labels, 12=annotations, 13=ownerReferences, 14=finalizers,
    17=managedFields`.
  - `OwnerReference`: `1=kind, 3=name, 4=uid, 5=apiVersion, 6=controller,
    7=blockOwnerDeletion` (there is no field 2).
  - `ManagedFieldsEntry`: `1=manager, 2=operation, 3=apiVersion, 4=time,
    6=fieldsType, 7=fieldsV1, 8=subresource` (no field 5); `FieldsV1` wraps
    its JSON in field 1.
- Schema values are `(name, type_tuple)`; type tuples as documented at the
  top of the file. `META` (ObjectMeta), `POD_SPEC`, `CONTAINER`, `SERVICE_SPEC`,
  `SECRET`, etc.
- `SCHEMAS` maps `kind → schema`. `for_kind(kind, api_version)` falls back to
  `GENERIC` (the metadata/spec/status shape) for any unknown kind, so even
  kinds without a hand-written schema keep a decoded `metadata`.
- `decode_message` is resilient: if a nested field fails its schema decode it
  falls back to generic rendering for that field only, so one bad field never
  blanks the whole object.

## 7. TUI (`tui.py`)

- **`build_tree(entries)`** (in `objects.py`): builds a `Node` trie from
  `(path_bytes, key)` entries; each node has `count` (entries below it) and
  leaf nodes carry `key`. Used by both views.
- **Two views**, toggled with `t` (or `browse --view {keys,objects}`):
  - **keys** (default): trie over the raw etcd keys (storage point of view).
  - **objects**: trie over virtual paths `namespace -> kind -> name` built from
    decoded values (`objects.object_paths`). Cluster-scoped objects go under
    `(cluster-scoped)`; values that do not decode as objects go under `(raw)`.
    Built lazily on first switch (decodes ~12.5k values, a few seconds).
- **`apply_filter`**: substring filter; applies to the active view's paths and
  rebuilds the tree, auto-expanding only the top level.
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
- **Export / edit**: `E` prompts for a format (`json`/`yaml`) then exports the
  current entry — a leaf → decoded object; an internal node → whole subtree
  `{"count", "entries": {key: decoded}}`. In the objects view internal nodes
  export via their leaf keys (the virtual path is not an etcd prefix). Output
  lands in `tmp/export/`. YAML output is produced by `yamlout.py`, a minimal
  stdlib YAML emitter (dict/list/str/int/float/bool/None/bytes-as-base64).
  `e` opens the current object in `$EDITOR` (fallback nano → vi → vim);
  `def_prog_mode()`/`reset_prog_mode()` suspend/resume curses around the
  external editor.
- **Value format**: `y` toggles the value panel between JSON and YAML
  rendering (`value_fmt`); the `_val_lines` cache is cleared on toggle.
- **Keys**: `j/k/arrows` move, `Enter/l/Right` expand, `h/Left` collapse,
  `/` filter, `[ ]` value scroll, `g/G` jump, `t` toggle view, `y` json/yaml,
  `e` edit, `E` export, `c` clear cache, `?` help, `q` quit.

## 8. CLI (`etcdbrowser.py`)

- `status <snapshot.db>` — verify.
- `open <snapshot.db> [--client-port N]` — restore + serve, prints state.
- `browse` — curses browser (requires a running etcd).
- `export <prefix> <out.json>` — headless export.
- `verify [--kinds N] [--json out.json]` — decode-adherence report: scans the
  snapshot and reports, per kind, unknown field numbers and wire-type
  mismatches vs the bundled schemas. Run it on any snapshot to confirm the
  schemas still hold (see §6.5).
- `close [--keep-data]` — stop etcd, remove data dir.
- `--version`.

## 6.5 Decode adherence (`verify.py`)

- `analyze(client)` walks every value and, for each k8s object, re-parses the
  raw protobuf and compares each (field number, wire type) against the schema:
  `known`/`unknown`/`mismatched` counters, plus which unknown numbers appear.
- `expected_wire_types()` maps schema type tuples to legal wire types
  (str/bytes/msg/map → length-delimited, bool/ints → varint, float → 32/64-bit,
  `any` → all), so a schema that says `bool` but receives a length-delimited
  field is flagged — exactly the class of bug that broke the original schemas.
- On the bundled snapshot: 100 % adherence — 81,446 top-level fields and
  125,934 metadata fields all known, 0 mismatches, all 10,775 objects keep
  their metadata.
- The schemas cover not just `metadata` but also the `spec`/`status` of the
  common workload and storage kinds: Pod, Service, Deployment, ReplicaSet,
  StatefulSet, DaemonSet, Job, CronJob, Node, PV, PVC, PDB, Namespace,
  NetworkPolicy, IngressClass, ResourceQuota, LimitRange, CSIDriver/CSINode,
  IPAddress, ServiceCIDR, admission webhook configs, FlowSchema,
  PriorityLevelConfiguration, ValidatingAdmissionPolicy(+Binding), and the
  OpenShift kinds Route, Image, ImageStream, OAuthClient, OAuthAccessToken,
  CSIStorageCapacity. Nested condition/status sub-messages (PodCondition,
  JobCondition, DeploymentCondition, ContainerStatus, NodeCondition, Taint,
  …) have their own schemas too.

## 9. Key observations on the bundled snapshot

- `snapshot_2026-08-04_150427.db`, 101 MB, hash `4f9242b6`, 22,010 revisions.
- 12,525 keys under `/` (12,526 with the internal `compact_rev_key`, which is
  correctly excluded because it does not start with `/`); gateway + etcdctl
  agree on the live count (12,522 after tombstone compaction).
- Two top-level groups: `kubernetes.io` (~12,47x keys) and `openshift.io`.
- Object view breakdown after the schema fixes: ~12.5k values → 9,706
  namespaced objects, 2,814 cluster-scoped, and only 2 in `(raw)` (the
  internal `RangeAllocation` bitmaps with empty metadata names).
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
