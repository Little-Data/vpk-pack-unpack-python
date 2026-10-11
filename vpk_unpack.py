#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vpk_unpack.py - generic Valve VPK (Valve Pak) archive extractor.

Supports the full VPK directory format:
  * v1 and v2 directory files (both "name.vpk" and "name_dir.vpk")
  * embedded entries  (ArchiveIndex == 0x7FFF, data stored after the directory)
  * external archive parts ("name_000.vpk", "name_001.vpk", ...)
  * per-file preload bytes stored inside the directory
  * both 16-byte entries (no terminator) and 18-byte entries (0xFFFF terminator)

Usage:
    python vpk_unpack.py <archive.vpk> [-o OUTDIR] [--terminator auto|yes|no] [--list]

Examples:
    python vpk_unpack.py 3298975358.vpk
    python vpk_unpack.py pak01_dir.vpk -o pak01
    python vpk_unpack.py pak01_dir.vpk --list
"""

import argparse
import os
import struct
import sys

VPK_SIGNATURE = 0x55AA1234
EMBEDDED_INDEX = 0x7FFF
# crc(u32), preloadBytes(u16), archiveIndex(u16), entryOffset(u32), entryLength(u32)
DIR_ENTRY = struct.Struct("<IHHII")


def read_cstring(buf, pos):
    end = buf.find(b"\x00", pos)
    if end < 0:
        raise ValueError("malformed directory: unterminated string at offset %d" % pos)
    return buf[pos:end].decode("utf-8", "replace"), end + 1


def read_header(data):
    if len(data) < 12:
        raise ValueError("file is too small to be a VPK")
    sig, version, tree_size = struct.unpack_from("<III", data, 0)
    if sig != VPK_SIGNATURE:
        raise ValueError("bad VPK signature 0x%08X" % sig)
    if version not in (1, 2):
        raise ValueError("unsupported VPK version %d" % version)
    header_size = 12 if version == 1 else 28  # v2 has 4 extra uint32 section sizes
    return version, header_size, tree_size


def iter_entries(tree, terminator):
    """Yield (ext, folder, name, preload, archive_index, offset, length, crc)."""
    pos = 0
    n = len(tree)
    while True:
        ext, pos = read_cstring(tree, pos)
        if ext == "":
            break
        while True:
            folder, pos = read_cstring(tree, pos)
            if folder == "":
                break
            while True:
                name, pos = read_cstring(tree, pos)
                if name == "":
                    break
                crc, preload_len, archive_index, offset, length = DIR_ENTRY.unpack_from(tree, pos)
                pos += DIR_ENTRY.size
                # Optional 0xFFFF terminator. A (lowercased) filename never starts
                # with 0xFF, so peeking is a safe way to auto-detect it.
                if terminator == "yes":
                    pos += 2
                elif terminator == "auto" and pos + 2 <= n and tree[pos] == 0xFF and tree[pos + 1] == 0xFF:
                    pos += 2
                preload = tree[pos:pos + preload_len]
                pos += preload_len
                yield ext, folder, name, preload, archive_index, offset, length, crc


def base_name(path):
    """'pak01_dir.vpk' / 'pak01.vpk' -> 'pak01' (prefix used for external parts)."""
    root = path[:-4] if path.lower().endswith(".vpk") else path
    if root.lower().endswith("_dir"):
        root = root[:-4]
    return root


def entry_name(ext, folder, name):
    parts = []
    if folder and folder != " ":
        parts.append(folder)
    if name and name != " ":
        parts.append(name)
    path = "/".join(parts)
    if ext and ext != " ":
        path += "." + ext
    return path


def extract(vpk_path, out_dir, terminator, list_only):
    with open(vpk_path, "rb") as f:
        data = f.read()
    version, header_size, tree_size = read_header(data)
    tree = data[header_size:header_size + tree_size]
    if len(tree) != tree_size:
        raise ValueError("directory tree is truncated")
    data_start = header_size + tree_size

    archives = {}  # index -> bytes (lazy)
    count = 0
    for ext, folder, name, preload, archive_index, offset, length, crc in iter_entries(tree, terminator):
        rel = entry_name(ext, folder, name)
        if list_only:
            print("%-60s preload=%d archive=%04X offset=%d length=%d"
                  % (rel, len(preload), archive_index, offset, length))
            count += 1
            continue
        if archive_index == EMBEDDED_INDEX:
            body = data[data_start + offset:data_start + offset + length]
        else:
            if archive_index not in archives:
                part = "%s_%03d.vpk" % (base_name(vpk_path), archive_index)
                if not os.path.isfile(part):
                    raise ValueError("missing external archive part: %s" % part)
                with open(part, "rb") as pf:
                    archives[archive_index] = pf.read()
            body = archives[archive_index][offset:offset + length]
        content = preload + body
        dst = os.path.join(out_dir, rel)
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        with open(dst, "wb") as of:
            of.write(content)
        count += 1

    verb = "listed" if list_only else "extracted"
    print("%s %d entr%s from %s (v%d)" % (verb, count, "y" if count == 1 else "ies",
                                          vpk_path, version))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Extract a Valve VPK archive.")
    ap.add_argument("vpk", help="path to the .vpk / _dir.vpk file")
    ap.add_argument("-o", "--out", default=None,
                    help="output directory (default: <archive name>_extracted)")
    ap.add_argument("--terminator", choices=["auto", "yes", "no"], default="auto",
                    help="directory entry terminator handling (default: auto)")
    ap.add_argument("--list", action="store_true", help="only list entries, do not write files")
    args = ap.parse_args(argv)

    out = args.out
    if out is None:
        out = (args.vpk[:-4] if args.vpk.lower().endswith(".vpk") else args.vpk) + "_extracted"
    if not args.list:
        os.makedirs(out, exist_ok=True)
    extract(args.vpk, out, args.terminator, args.list)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - report cleanly for CLI use
        print("error: %s" % exc, file=sys.stderr)
        sys.exit(1)
