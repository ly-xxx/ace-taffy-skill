#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path


BACKUP_ITEMS = [
    "SKILL.md",
    "persona.md",
    "meta.json",
    "requirements.txt",
    "references",
    "prompts",
    "tools",
    "sources/targets",
]


def copy_item(src_root: Path, rel_path: str, dst_root: Path) -> None:
    src = src_root / rel_path
    dst = dst_root / rel_path
    if not src.exists():
        return

    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


def backup(root: Path, label: str | None) -> Path:
    versions_dir = root / "versions"
    versions_dir.mkdir(exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    name = f"{stamp}-{label}" if label else stamp
    target = versions_dir / name
    target.mkdir(parents=True, exist_ok=True)

    for rel_path in BACKUP_ITEMS:
        copy_item(root, rel_path, target)

    print(f"[OK] backup -> {target}")
    return target


def list_versions(root: Path) -> None:
    versions_dir = root / "versions"
    if not versions_dir.exists():
        print("no versions yet")
        return

    for item in sorted(versions_dir.iterdir()):
        if item.is_dir():
            print(item.name)


def rollback(root: Path, version: str) -> int:
    source = root / "versions" / version
    if not source.exists():
        print(f"version not found: {version}")
        return 1

    backup(root, "before-rollback")
    for rel_path in BACKUP_ITEMS:
        copy_item(source, rel_path, root)

    print(f"[OK] rolled back from {source}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup and rollback persona-skill artifacts.")
    parser.add_argument("--action", required=True, choices=["backup", "list", "rollback"])
    parser.add_argument("--root", default=".", help="Skill root")
    parser.add_argument("--label", help="Optional backup label")
    parser.add_argument("--version", help="Version directory name for rollback")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()

    if args.action == "backup":
        backup(root, args.label)
        return 0
    if args.action == "list":
        list_versions(root)
        return 0
    if args.action == "rollback":
        if not args.version:
            print("--version is required for rollback")
            return 1
        return rollback(root, args.version)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
