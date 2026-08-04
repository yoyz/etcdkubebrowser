# AGENTS.md

## Project

**etcdbrowser** (version 0.0.1) — open an etcd snapshot, browse and export the
Kubernetes / OpenShift objects it contains. Pure-Python (stdlib only) with a
curses TUI.

Key facts to remember:

- It is **not** a self-contained tool: it shells out to the **`etcd` and
  `etcdctl` binaries** (must be installed on PATH, tested with 3.4.30) to
  verify, restore and serve the snapshot.
- etcd is started **detached** (`start_new_session=True`) so it survives the
  shell; if a test harness kills backgrounded processes, always relaunch via
  `etcdbrowser.py open` (never by re-invoking etcd manually).
- Runtime state lives in `tmp/etcdbrowser.state` (pid, urls, datadir).
- Values come in three formats: `k8s\x00` protobuf envelope (built-ins),
  plain JSON (CRDs), or raw bytes. See `etcdbrowser/decode.py`.

## Temp directory policy

- Use the local `tmp/` directory inside this project for all temporary work:
  `/home/ollama/build/etcdkubebrowser/tmp/`
- NEVER read from or write to `/tmp/` or any other system temp directory.

## Commands (run from the repo root)

```sh
python3 -S etcdbrowser.py status <snapshot.db>       # verify
python3 -S etcdbrowser.py open   <snapshot.db>       # restore + serve on 127.0.0.1:22379
python3 -S etcdbrowser.py browse                     # curses TUI
python3 -S etcdbrowser.py export <prefix> <out.json> # headless export (single file)
python3 -S etcdbrowser.py export-tree <outdir>       # one file per leaf (see below)
python3 -S etcdbrowser.py close [--keep-data]        # stop etcd
python3 -S etcdbrowser.py --version
```

## export-tree

`export-tree <outdir> [--layout objects|keys] [--format json|yaml]
[--prefix P] [--summary FILE]` writes the whole snapshot (or a `--prefix`
subtree) as a directory of files, one per leaf.

- `--layout objects` (default, OpenShift style): `namespace/kind/name`, with
  cluster-scoped objects under `(cluster-scoped)` and non-object values under
  `(raw)`. k8s values are written as clean `{apiVersion, kind, ...}` manifests
  (apply-able via `oc apply -f`).
- `--layout keys`: mirrors the etcd storage key trie (`kubernetes.io/...`,
  `openshift.io/...`).
- `--format json|yaml` (default json). Leaves are never dropped; object names
  are sanitised and same-path collisions suffixed with `-2`, `-3`, …
- `--summary FILE` also writes a JSON summary embedding `verify`-style decode /
  adherence stats.

Implementation lives in `etcdbrowser/exporttree.py` (reuses `decode.py`,
`objects.py`, `yamlout.py`, `verify.py`).

## Testing (run before a release)

- `make test` — fast stdlib-only **unit tests** (`test/test_export_tree.py`
  uses an in-memory `FakeKVClient`, no etcd needed).
- `make release-test` — the full gate: unit **plus** integration
  (`test/test_integration.py`) against a real snapshot (the bundled backup
  auto-opens if `etcd`/`etcdctl` are installed). It exports in both layouts
  and both formats, checks every JSON/YAML leaf parses, and asserts **>= 90 %
  of useful objects decode with metadata intact** (0 unknown protobuf fields).
- `test/helpers.py` builds synthetic `k8s\x00` runtime.Unknown protobuf values
  and a `FakeKVClient` for fixtures.
- Full plan: `doc/functionnal_test.md`. Individual YAML round-trips use PyYAML
  when available (`python3 -m unittest`); under `python3 -S` YAML tests fall
  back to structural checks.

## Gotchas for TUI work

- `stdscr.keypad(True)` is required for arrow keys; without it escape
  sequences are read byte-by-byte.
- Refresh order matters: refresh the base `stdscr` first, then the overlay
  panels, then a single `doupdate()`. A redundant early `noutrefresh` of the
  panels blanks them.
- For pty tests via `script -qec "python3 -S etcdbrowser.py browse"`, the
  arrow-key sequence must match the terminfo (here cursor-down is `\x1bOB`,
  application-cursor mode — not `\x1b[B`).

## Docs

- `README.md` — user-facing usage and design summary.
- `doc/design.md` — full architecture notes (backend, decode, schemas, TUI,
  pitfalls). Read it before modifying the decoder or renderer.
