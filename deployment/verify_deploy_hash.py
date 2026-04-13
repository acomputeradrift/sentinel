#!/usr/bin/env python3
"""Compare SHA-256 of a zip member to a deployed file (run on the droplet after extract)."""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import zipfile


def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--zip", default="/tmp/sentinel_patch.zip", help="Path to deployment zip on server")
    p.add_argument(
        "--member",
        default="src/sentinel/server/app/main.py",
        help="Archive member path (forward slashes)",
    )
    p.add_argument(
        "--deployed",
        default="/opt/sentinel/app/src/sentinel/server/app/main.py",
        help="Extracted file path on server",
    )
    args = p.parse_args()

    with zipfile.ZipFile(args.zip, "r") as zf:
        zip_hash = sha256_bytes(zf.read(args.member))
    deployed_hash = sha256_bytes(pathlib.Path(args.deployed).read_bytes())
    print("zip_member:", args.member)
    print("zip_sha256:", zip_hash)
    print("deployed_path:", args.deployed)
    print("deployed_sha256:", deployed_hash)
    print("match:", zip_hash == deployed_hash)
    raise SystemExit(0 if zip_hash == deployed_hash else 1)


if __name__ == "__main__":
    main()
