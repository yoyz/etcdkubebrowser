#!/usr/bin/env python3
# Copyright (c) 2026
#
# etcdbrowser - reliably open an etcd snapshot, browse it visually and export
# Kubernetes / OpenShift objects.
#
# Usage:
#   etcdbrowser.py status <snapshot.db>
#   etcdbrowser.py open   <snapshot.db> [--client-port N]
#   etcdbrowser.py browse
#   etcdbrowser.py export <prefix> <outfile.json>
#   etcdbrowser.py close  [--keep-data]
#
# `open` verifies the snapshot, restores it into tmp/ and serves it on a local
# etcd instance (127.0.0.1:22379 by default). `browse` opens the curses TUI.
# All commands talk to etcd through its HTTP/JSON v3 gateway, so no extra
# Python packages (grpc, etcd3, urwid...) are required.

import argparse
import json
import os
import sys

from etcdbrowser import backend
from etcdbrowser.backend import KVClient, BackendError
from etcdbrowser import decode
from etcdbrowser import tui
from etcdbrowser import verify
from etcdbrowser import __version__


def die(msg: str) -> None:
    print("etcdbrowser: %s" % msg, file=sys.stderr)
    sys.exit(1)


def cmd_status(args) -> None:
    try:
        print(backend.snapshot_status(args.snapshot))
    except BackendError as exc:
        die(str(exc))


def cmd_open(args) -> None:
    try:
        state = backend.open_snapshot(args.snapshot, client_port=args.client_port,
                                      peer_port=args.peer_port)
    except BackendError as exc:
        die(str(exc))
    print("opened: %s" % state["snapshot"])
    print("client : %s  (pid %s)" % (state["client_url"], state["pid"]))
    print("log    : %s" % state["logfile"])
    print("browse : etcdbrowser.py browse")


def cmd_browse(args) -> None:
    state = backend.read_state()
    if not state or not backend._pid_alive(state.get("pid")):
        die("no etcd running. Run: etcdbrowser.py open <snapshot.db>")
    client = KVClient(state["client_url"])
    try:
        client.count(b"/")
    except BackendError as exc:
        die(str(exc))
    tui.run(client, state.get("snapshot", ""), view=args.view)


def cmd_export(args) -> None:
    state = backend.read_state()
    if not state or not backend._pid_alive(state.get("pid")):
        die("no etcd running. Run: etcdbrowser.py open <snapshot.db>")
    client = KVClient(state["client_url"])
    prefix = args.prefix.encode("utf-8")
    out: dict = {}
    n = 0
    try:
        for key, value in client.iter_range(prefix, keys_only=False):
            out[key.decode("utf-8", errors="replace")] = decode.decode_value(value)
            n += 1
    except BackendError as exc:
        die(str(exc))
    with open(args.outfile, "w", encoding="utf-8") as fh:
        json.dump({"count": n, "entries": out}, fh, indent=2, ensure_ascii=False,
                  default=str)
    print("exported %d keys to %s" % (n, args.outfile))


def cmd_verify(args) -> None:
    state = backend.read_state()
    if not state or not backend._pid_alive(state.get("pid")):
        die("no etcd running. Run: etcdbrowser.py open <snapshot.db>")
    client = KVClient(state["client_url"])
    try:
        report = verify.analyze(client)
    except BackendError as exc:
        die(str(exc))
    text = verify.render(report, kind_limit=args.kinds)
    print(text)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({k: v for k, v in report.items() if k != "kinds"},
                      fh, indent=2, default=str)
            print("report written to %s" % args.json)



def cmd_close(args) -> None:
    backend.close(keep_data=args.keep_data)
    print("closed")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="etcdbrowser.py",
                                     description="Browse and extract data from etcd snapshots.")
    parser.add_argument("--version", action="version",
                        version="etcdbrowser.py %s" % __version__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status", help="verify a snapshot")
    p.add_argument("snapshot")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("open", help="verify, restore and serve a snapshot")
    p.add_argument("snapshot")
    p.add_argument("--client-port", type=int, default=backend.DEFAULT_CLIENT_PORT)
    p.add_argument("--peer-port", type=int, default=backend.DEFAULT_PEER_PORT)
    p.set_defaults(func=cmd_open)

    p = sub.add_parser("browse", help="interactive curses browser")
    p.add_argument("--view", choices=["keys", "objects"], default="keys",
                   help="initial view: keys (etcd storage) or objects (k8s model)")
    p.set_defaults(func=cmd_browse)

    p = sub.add_parser("export", help="export all keys under a prefix to JSON")
    p.add_argument("prefix")
    p.add_argument("outfile")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("verify",
                       help="report how well the decode schemas match the snapshot")
    p.add_argument("--kinds", type=int, default=12,
                   help="how many kinds to list in the report (default 12)")
    p.add_argument("--json", metavar="OUT.json",
                   help="also write the aggregate stats to a JSON file")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("close", help="stop the served etcd")
    p.add_argument("--keep-data", action="store_true")
    p.set_defaults(func=cmd_close)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
