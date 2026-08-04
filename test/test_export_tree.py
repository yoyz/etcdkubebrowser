# Copyright (c) 2026
#
# Release tests for the `export-tree` command. Run before a release with:
#
#     make release-test
#
# Covers:
#   1. export-tree writes one file per leaf
#   2. both layouts: objects (namespace/kind/name) and keys (storage trie)
#   3. both formats: json and yaml
#   4. JSON leaves parse back as valid JSON
#   5. YAML leaves are valid YAML (structural check; full round-trip when PyYAML
#      is available, e.g. `python3 -m unittest`)
#   6. objects layout: namespaced / cluster-scoped / raw placement
#   7. keys layout mirrors the etcd storage trie
#   8. sanitisation + collision handling (safe names, unique file paths)
#   9. >= 90% of useful objects are decoded (metadata present)
#
# Run with stdlib only:   python3 -S -m unittest discover -s test -p 'test_*.py'
# Run with PyYAML, too:   python3 -m unittest discover -s test -p 'test_*.py'
#
# Most tests use an in-memory FakeKVClient (no etcd needed). The full computed
# decode-ratio check against a real restored snapshot is in test_verify.py.

from __future__ import annotations

import glob
import json
import os
import tempfile
import unittest

from etcdbrowser import exporttree
from etcdbrowser.objects import CLUSTER, RAW
from helpers import FakeKVClient, k8s_pod, sample_snapshot


try:
    import yaml as _yaml  # optional, only used when available
except Exception:  # pragma: no cover - not present under python3 -S
    _yaml = None


class ExportTreeBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="etcdbrowser-test-")
        self.addCleanup(self._rmtree, self._tmp)
        self.client = sample_snapshot()

    def _rmtree(self, path):
        import shutil
        shutil.rmtree(path, ignore_errors=True)

    def _walk(self, base):
        files = {}
        for root, _dirs, names in os.walk(base):
            for name in names:
                full = os.path.join(root, name)
                rel = os.path.relpath(full, base)
                with open(full, "rb") as fh:
                    files[rel] = fh.read()
        return files


class TestLayoutsAndFormats(ExportTreeBase):
    def test_objects_json_one_file_per_leaf(self):
        outdir = os.path.join(self._tmp, "obj-json")
        stats = exporttree.export_tree(self.client, outdir, layout="objects", fmt="json")
        self.assertEqual(stats["files"], 5)
        files = self._walk(outdir)
        self.assertEqual(len(files), 5)
        # each leaf is valid JSON
        for rel, blob in files.items():
            self.assertTrue(rel.endswith(".json"), rel)
            json.loads(blob.decode("utf-8"))  # raises if invalid

    def test_objects_yaml_parses_when_pyyaml_available(self):
        outdir = os.path.join(self._tmp, "obj-yaml")
        stats = exporttree.export_tree(self.client, outdir, layout="objects", fmt="yaml")
        self.assertEqual(stats["files"], 5)
        files = self._walk(outdir)
        self.assertEqual(len(files), 5)
        for rel, blob in files.items():
            self.assertTrue(rel.endswith(".yaml"), rel)
            text = blob.decode("utf-8")
            self.assertTrue(text.strip(), "empty yaml leaf: %s" % rel)
            if _yaml is not None:
                doc = _yaml.safe_load(text)
                self.assertIsInstance(doc, dict)

    def test_keys_layout_mirrors_storage_trie(self):
        outdir = os.path.join(self._tmp, "keys-json")
        stats = exporttree.export_tree(self.client, outdir, layout="keys", fmt="json")
        self.assertEqual(stats["files"], 5)
        files = self._walk(outdir)
        expected = {
            "kubernetes.io/pods/default/web-0.json",
            "kubernetes.io/pods/default/db-0.json",
            "kubernetes.io/namespaces/openshift.json",
            "kubernetes.io/config/config.network/channels.json",
            "openshift.io/cluster/rawblob.json",
        }
        self.assertEqual(set(files), expected)

    def test_keys_layout_yaml(self):
        outdir = os.path.join(self._tmp, "keys-yaml")
        stats = exporttree.export_tree(self.client, outdir, layout="keys", fmt="yaml")
        self.assertEqual(stats["files"], 5)
        files = self._walk(outdir)
        self.assertTrue(all(rel.endswith(".yaml") for rel in files))


class TestObjectPlacement(ExportTreeBase):
    def test_namespaced_and_cluster_scoped_and_raw(self):
        outdir = os.path.join(self._tmp, "obj")
        exporttree.export_tree(self.client, outdir, layout="objects", fmt="json")
        files = self._walk(outdir)
        expected = {
            os.path.join("default", "Pod", "web-0.json"),
            os.path.join("default", "Pod", "db-0.json"),
            os.path.join(CLUSTER, "Namespace", "openshift.json"),
            os.path.join("default", "Channel", "chan-1.json"),
            os.path.join(RAW, "openshift.io", "cluster", "rawblob.json"),
        }
        self.assertEqual(set(files), expected)
        # Pod leaf is a clean manifest
        pod = json.loads(files[os.path.join("default", "Pod", "web-0.json")])
        self.assertEqual(pod["kind"], "Pod")
        self.assertEqual(pod["metadata"]["name"], "web-0")
        self.assertEqual(pod["metadata"]["namespace"], "default")
        # raw leaves carry the decode envelope (nothing dropped)
        raw = json.loads(files[os.path.join(RAW, "openshift.io", "cluster", "rawblob.json")])
        self.assertEqual(raw["format"], "raw")

    def test_plain_json_crd_goes_to_namespaced_placement(self):
        outdir = os.path.join(self._tmp, "obj2")
        exporttree.export_tree(self.client, outdir, layout="objects", fmt="json")
        files = self._walk(outdir)
        chan = json.loads(files[os.path.join("default", "Channel", "chan-1.json")])
        self.assertEqual(chan["kind"], "Channel")
        self.assertEqual(chan["metadata"]["namespace"], "default")


class TestCollisionAndSanitisation(ExportTreeBase):
    def test_same_name_in_same_namespace_kind_is_suffixed(self):
        # two storage keys mapping to the same virtual object path
        # (same namespace/kind/name) -> the second file is suffixed -2
        data = {
            b"/kubernetes.io/pods/default/web-0": k8s_pod("web-0", "default"),
            b"/kubernetes.io/other/pods/default/web-0": k8s_pod("web-0", "default"),
        }
        client = FakeKVClient(data)
        outdir = os.path.join(self._tmp, "collide")
        exporttree.export_tree(client, outdir, layout="objects", fmt="json")
        files = sorted(os.path.basename(p) for p in glob.glob(
            os.path.join(outdir, "default", "Pod", "*")))
        self.assertEqual(files, ["web-0-2.json", "web-0.json"])

    def test_sanitise_segment(self):
        self.assertEqual(exporttree.sanitize_segment("a/b: c*"), "a_b__c_")
        self.assertEqual(exporttree.sanitize_segment(".."), "_")
        self.assertEqual(exporttree.sanitize_segment("."), "_")
        self.assertEqual(exporttree.sanitize_segment(""), "_")


class TestDecodeRatio(ExportTreeBase):
    def test_all_useful_objects_are_decoded(self):
        outdir = os.path.join(self._tmp, "ratio")
        stats = exporttree.export_tree(self.client, outdir, layout="objects", fmt="json")
        self.assertEqual(stats["decoded_ratio"], 100.0)
        self.assertEqual(stats["k8s"]["total"], 3)
        self.assertEqual(stats["k8s"]["with_metadata"], 3)
        self.assertEqual(stats["raw"], 1)

    def test_useful_ratio_at_least_90_percent(self):
        outdir = os.path.join(self._tmp, "ratio2")
        stats = exporttree.export_tree(self.client, outdir, layout="objects", fmt="json")
        self.assertGreaterEqual(stats["decoded_ratio"], 90.0)
        self.assertGreaterEqual(stats["object_ratio"], 90.0)


if __name__ == "__main__":
    unittest.main()
