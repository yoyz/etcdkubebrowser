# Pre-release functional test plan

Run before shipping a release. Two tiers, driven from the repo root:

| Command | Scope | Needs etcd? |
| --- | --- | --- |
| `make test` | unit tests | no |
| `make release-test` | full gate (unit + integration) | yes (bundled snapshot auto-opens) |

Both run the standard-library `unittest` runner (`python3 -S`), so they need
no third-party packages. Running the tests with a normal `python3` (not `-S`)
optionally enables **PyYAML** round-trip checks of exported YAML leaves.

## 1. Unit tier — `make test`

`test/test_export_tree.py` runs against an in-memory `FakeKVClient` built by
`test/helpers.py`, so no etcd is required. It verifies:

- **one file per leaf** for both the `objects` and `keys` layouts, in both
  `json` and `yaml`;
- **JSON validity** — every `.json` leaf round-trips through `json.load`;
- **YAML validity** — every `.yaml` leaf is non-empty and (when PyYAML is
  present) round-trips through `yaml.safe_load`;
- **objects placement** — a namespaced object lands at
  `namespace/kind/name`, a cluster-scoped object under `(cluster-scoped)`,
  a CRD under its namespace/kind, and a non-object value under `(raw)`;
- **keys placement** — the keys layout mirrors the storage key trie
  (`kubernetes.io/...`, `openshift.io/...`);
- **sanitisation + collisions** — unsafe path segments are sanitised and
  same-path leaves are suffixed `-2`, `-3`, …;
- **decode ratio** — at least 90% of useful objects are decoded with their
  metadata intact (the fixture is 100%).

## 2. Integration tier — `make release-test`

`test/test_integration.py` runs against a **real restored snapshot**. It
auto-opens the bundled backup under `etcdbackup_hub1/backup/` when the
`etcd`/`etcdctl` binaries are installed; otherwise it uses an already-running
`etcdbrowser.py open` instance, or skips (never fails) if none is available.

It validates the release intent end to end:

- **full-tree export** of the *whole* snapshot in both layouts
  (`objects`, `keys`) and both formats (`json`, `yaml`) — asserting exactly
  one file per leaf;
- **every JSON leaf parses** back as valid JSON;
- **every YAML leaf parses** back as valid YAML (PyYAML available);
- **`>= 90%` of useful objects are decoded** with their metadata intact
  (the bundled snapshot achieves 100%);
- **decode adherence** — `verify.analyze` reports **0 unknown protobuf
  fields / 0 wire-type mismatches** and **0 k8s objects missing metadata**,
  i.e. the schemas in `schemas.py` still match the snapshot's wire data;
- **CLI smoke tests** drive the real `etcdbrowser.py export-tree` subcommand
  (objects/json with a summary file, and keys/yaml under a `--prefix`).

## 3. Running against a specific snapshot

```sh
make test                        # unit only (fast)
python3 -S etcdbrowser.py open <snapshot.db>   # or use the bundled backup
make release-test                # unit + integration
```

To point the integration tests at a particular snapshot instead of the
bundled one:

```sh
SNAPSHOT=/path/to/snapshot.db make release-test
```

## 4. What success looks like

`make release-test` exits 0 with a report of `Ran 16 tests ... OK`, including:

- `test_decode_adherence_has_no_unknown_fields` (0 unknown fields, 100%
  metadata coverage);
- the full-tree export tests reporting `values == files` and a decode ratio
  `>= 90%`.

A failing decode ratio, leaked files (values != files), an unparseable leaf,
or any unknown protobuf field means the release must not ship.
