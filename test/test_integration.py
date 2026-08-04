# Copyright (c) 2026
#
# Integration tests against a real restored snapshot (requires etcd running via
# `etcdbrowser.py open <snapshot.db>`, and a SNAPSHOT set in the environment or
# the repo's bundled backup). These validate the actual release intent:
#
#   - the full tree exports in both layouts (objects, keys) and both formats
#     (json, yaml), one file per leaf;
#   - every JSON leaf parses back as valid JSON;
#   - every YAML leaf parses back as valid YAML (when PyYAML is available);
#   - at least 90% of the useful objects are decoded with metadata intact
#     (the bundled snapshot achieves 100%).
#
# Skipped (not failed) when no etcd snapshot is available, so unit-only runs
# stay green. To run against the bundled backup:
#
#   python3 -S etcdbrowser.py open etcdbackup_hub1/backup/snapshot_*.db
#   SNAPSHOT=etcdbackup_hub1/backup/snapshot_*.db python3 -S -m unittest \
#       discover -s test -p 'test_integration.py' -v

from __future__ import annotations

import glob
import json
import os
import subprocess
import tempfile
import unittest

from etcdbrowser import exporttree
from etcdbrowser import decode
from etcdbrowser import verify
from etcdbrowser.backend import KVClient, read_state, _pid_alive

try:
    import yaml as _yaml  # optional, only used when available
except Exception:  # pragma: no cover
    _yaml = None

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLED = sorted(glob.glob(os.path.join(REPO, "etcdbackup_hub1", "backup",
                                        "snapshot_*.db")))


def _find_snapshot() -> str | None:
    env = os.environ.get("SNAPSHOT")
    if env and os.path.isfile(env):
        return env
    if BUNDLED:
        return BUNDLED[-1]
    return None


def _live_client():
    state = read_state()
    if not state or not _pid_alive(state.get("pid")):
        return None
    return KVClient(state["client_url"])


def _build_run_py(args) -> str:
    """Return a python snippet that runs etcdbrowser.py as a module."""
    script = os.path.join(REPO, "etcdbrowser.py")
    return [os.sys.executable, "-S", script] + args


class IntegrationBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = _find_snapshot()
        cls.client = _live_client()
        if cls.snapshot and cls.client is None:
            cls._open()
            cls.client = _live_client()
        cls.skip_reason = None
        if not cls.client:
            cls.skip_reason = ("no running etcd and no %s found; "
                               "open a snapshot first" % (
                                   cls.snapshot or "snapshot"))

    @classmethod
    def _open(cls):
        cmd = _build_run_py(["open", cls.snapshot])
        subprocess.run(cmd, check=True, capture_output=True, text=True)

    def setUp(self):
        if getattr(self.__class__, "skip_reason"):
            self.skipTest(self.__class__.skip_reason)


class TestFullTreeExport(IntegrationBase):
    def test_decode_adherence_has_no_unknown_fields(self):
        """Strongest decode validation: every protobuf field must be schema-known."""
        report = verify.analyze(self.client)
        self.assertGreater(report["values"], 0)
        self.assertEqual(report["top_level"]["unknown"], 0,
                         "unknown protobuf fields found")
        self.assertEqual(report["top_level"]["mismatched"], 0,
                         "wire-type mismatches found")
        self.assertEqual(report["metadata"]["unknown"], 0,
                         "unknown metadata fields found")
        self.assertEqual(report["k8s_without_metadata"], 0,
                         "k8s objects missing metadata")
        self.assertGreater(report["k8s"], 0)
        self.assertGreaterEqual(report["k8s_with_metadata"] / report["k8s"], 0.9)

    def test_json_objects_layout_every_leaf_valid_and_ratio(self):
        with tempfile.TemporaryDirectory() as outdir:
            stats = exporttree.export_tree(self.client, outdir,
                                           layout="objects", fmt="json")
            self.assertGreater(stats["values"], 0)
            self.assertEqual(stats["files"], stats["values"],
                             "one file per leaf")
            parsed = 0
            for root, _dirs, files in os.walk(outdir):
                for name in files:
                    self.assertTrue(name.endswith(".json"), name)
                    with open(os.path.join(root, name)) as fh:
                        json.load(fh)  # raises if not valid JSON
                    parsed += 1
            self.assertEqual(parsed, stats["files"])
            self.assertGreaterEqual(stats["decoded_ratio"], 90.0)
            self.assertGreaterEqual(stats["object_ratio"], 90.0)
            # the real snapshot should be at or very near 100%
            self.assertGreaterEqual(stats["decoded_ratio"], 99.0)

    def test_yaml_objects_layout_every_leaf_valid(self):
        with tempfile.TemporaryDirectory() as outdir:
            stats = exporttree.export_tree(self.client, outdir,
                                           layout="objects", fmt="yaml")
            self.assertEqual(stats["files"], stats["values"])
            parsed = 0
            for root, _dirs, files in os.walk(outdir):
                for name in files:
                    self.assertTrue(name.endswith(".yaml"), name)
                    if _yaml is None:
                        continue
                    with open(os.path.join(root, name)) as fh:
                        doc = _yaml.safe_load(fh)
                    self.assertIsInstance(doc, dict)
                    parsed += 1
            if _yaml is not None:
                self.assertEqual(parsed, stats["files"])

    def test_keys_layout(self):
        with tempfile.TemporaryDirectory() as outdir:
            stats = exporttree.export_tree(self.client, outdir,
                                           layout="keys", fmt="json")
            self.assertEqual(stats["files"], stats["values"])
            # top of the keys trie should contain the storage namespaces
            tops = {n for n in os.listdir(outdir)}
            self.assertTrue({"kubernetes.io", "openshift.io"} <= tops)


class TestCLIExportTree(IntegrationBase):
    def test_cli_exports_json_objects(self):
        with tempfile.TemporaryDirectory() as td:
            outdir = os.path.join(td, "x")
            summary = os.path.join(td, "s.json")
            cmd = _build_run_py(["export-tree", outdir, "--layout", "objects",
                                 "--format", "json", "--summary", summary])
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            with open(summary) as fh:
                stat = json.load(fh)
            self.assertEqual(stat["layout"], "objects")
            self.assertEqual(stat["format"], "json")
            self.assertGreaterEqual(stat["decoded_ratio"], 90.0)

    def test_cli_exports_yaml_keys_prefix(self):
        with tempfile.TemporaryDirectory() as td:
            outdir = os.path.join(td, "x")
            cmd = _build_run_py(["export-tree", outdir, "--layout", "keys",
                                 "--format", "yaml",
                                 "--prefix", "/kubernetes.io/namespaces"])
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            n = 0
            for root, _dirs, files in os.walk(outdir):
                for name in files:
                    self.assertTrue(name.endswith(".yaml"), name)
                    n += 1
            self.assertGreater(n, 0)


if __name__ == "__main__":
    unittest.main()
