#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vpk_pack.py - generic Valve VPK (Valve Pak) archive builder.

Creates a directory VPK that the Source engine can mount directly, with:
  * v1 or v2 header
  * all file data embedded after the directory (ArchiveIndex == 0x7FFF)
  * per-file CRC32, no preload bytes
  * offsets written relative to the end of the directory (as the engine expects)

Usage:
    python vpk_pack.py <SRC_DIR> <OUT.vpk> [--version 1|2] [--terminator auto|yes|no]

Examples:
    python vpk_pack.py extracted 3298975358.vpk
    python vpk_pack.py pak01_dir --version 1
"""

import argparse
import os
import struct
import sys
import zlib

VPK_SIGNATURE = 0x55AA1234
EMBEDDED_INDEX = 0x7FFF


def split_path(rel):
    """'materials/vgui/x.vmt' -> ('materials/vgui', 'x', 'vmt'); root/extensionless handled."""
    rel = rel.replace("\\", "/").lstrip("/")
    folder = os.path.dirname(rel)
    base = os.path.basename(rel)
    if "." in base and not base.startswith("."):
        name, ext = base.rsplit(".", 1)
    else:
        name, ext = base, " "
    return (folder if folder else " "), name, (ext if ext else " ")


def collect(src_dir):
    groups = {}  # (ext, folder) -> [(name, abspath), ...]
    for root, _dirs, files in os.walk(src_dir):
        for fn in files:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, src_dir)
            folder, name, ext = split_path(rel)
            groups.setdefault((ext, folder), []).append((name, full))
    return groups


def build(src_dir, out_path, version=1, terminator="yes"):
    groups = collect(src_dir)
    tree = bytearray()
    data = bytearray()
    total = 0

    for ext in sorted({k[0] for k in groups}):
        tree += ext.encode("utf-8") + b"\x00"
        for folder in sorted({k[1] for k in groups if k[0] == ext}):
            tree += folder.encode("utf-8") + b"\x00"
            for name, path in sorted(groups[(ext, folder)]):
                with open(path, "rb") as f:
                    content = f.read()
                tree += name.encode("utf-8") + b"\x00"
                tree += struct.pack("<IHHII", zlib.crc32(content) & 0xFFFFFFFF,
                                    0, EMBEDDED_INDEX, len(data), len(content))
                if terminator != "no":
                    tree += b"\xff\xff"
                data += content
                total += 1
            tree += b"\x00"  # end of file list for this folder
        tree += b"\x00"      # end of folder list for this extension
    tree += b"\x00"          # end of extension list

    if version == 1:
        header = struct.pack("<III", VPK_SIGNATURE, 1, len(tree))
    else:
        # v2: extra section sizes (all zero - we embed everything and write no MD5/sig sections)
        header = struct.pack("<IIIIIII", VPK_SIGNATURE, 2, len(tree), 0, 0, 0, 0)

    with open(out_path, "wb") as f:
        f.write(header)
        f.write(tree)
        f.write(data)

    print("packed %d file(s) -> %s (v%d, tree %d bytes, data %d bytes)"
          % (total, out_path, version, len(tree), len(data)))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a Valve VPK archive from a directory.")
    ap.add_argument("src", help="source directory to pack")
    ap.add_argument("out", help="output .vpk path")
    ap.add_argument("--version", type=int, choices=[1, 2], default=1,
                    help="VPK header version (default: 1)")
    ap.add_argument("--terminator", choices=["yes", "no"], default="yes",
                    help="write the 0xFFFF directory entry terminator (default: yes)")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.src):
        raise ValueError("source directory does not exist: %s" % args.src)
    build(args.src, args.out, args.version, args.terminator)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - report cleanly for CLI use
        print("error: %s" % exc, file=sys.stderr)
        sys.exit(1)
