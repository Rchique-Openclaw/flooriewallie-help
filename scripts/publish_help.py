#!/usr/bin/env python3
"""Publish a language help pack to the flooriewallie-help repo.

Usage:
    publish_help.py <zip-path> <lang>

- Reads the CURRENT version for <lang> from the remote repo's manifest.json.
- Writes the zip into the repo as <lang>/help-<version+1>.zip.
- Updates manifest.json (version, file, sha256, sizeBytes, publishedAt).
- Commits and pushes to the default branch.

Zips are sanitized: __MACOSX/ and .DS_Store entries are stripped;
the pack must contain index.html at the zip root.

Options:
    --repo-url   Git URL of the help repo (default: production repo).
    --raw-base   Raw-file URL base used only for printed links.
    --dry-run    Do everything except commit/push.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_REPO_URL = "git@github.com:Rchique-Openclaw/flooriewallie-help.git"
DEFAULT_RAW_BASE = "https://raw.githubusercontent.com/Rchique-Openclaw/flooriewallie-help/main"
JUNK_PATTERNS = ("__MACOSX/", ".DS_Store")
MAX_ZIP_BYTES = 95 * 1024 * 1024  # GitHub hard-limits files at 100 MB


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=check, text=True, capture_output=True)


def sanitize_zip(src: Path, workdir: Path) -> Path:
    """Return a zip without junk entries; same path object if already clean."""
    with zipfile.ZipFile(src) as zf:
        names = zf.namelist()
        junk = [n for n in names if any(p in n for p in JUNK_PATTERNS)]
        if "index.html" not in names:
            die(f"{src} has no index.html at the zip root; app expects it. Entries: {names[:5]}...")
        if not junk:
            return src
        print(f"Stripping {len(junk)} junk entries (__MACOSX/.DS_Store)...")
        cleaned = workdir / src.name
        with zipfile.ZipFile(cleaned, "w", zipfile.ZIP_DEFLATED) as out:
            for item in zf.infolist():
                if any(p in item.filename for p in JUNK_PATTERNS):
                    continue
                out.writestr(item, zf.read(item.filename))
        return cleaned


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def clone_repo(repo_url: str, workdir: Path) -> tuple[Path, str]:
    """Shallow-clone the repo; returns (clone_dir, default_branch). Handles empty repo."""
    probe = run(["git", "ls-remote", "--symref", repo_url], check=False)
    clone = workdir / "repo"
    if probe.returncode != 0:
        die(f"cannot reach {repo_url}: {probe.stderr.strip()}")
    m = re.search(r"ref:\s+refs/heads/(\S+)\s+HEAD", probe.stdout)
    if m:
        branch = m.group(1)
    else:  # no HEAD symref: pick a real branch if any exist, else treat as empty
        heads = [line.split("refs/heads/")[-1] for line in probe.stdout.splitlines() if "refs/heads/" in line and not line.startswith("ref:")]
        branch = next((b for b in ("main", "master") if b in heads), heads[0] if heads else None)
        if branch is None:
            clone.mkdir()
            run(["git", "init", "-b", "main", "."], cwd=clone)
            run(["git", "remote", "add", "origin", repo_url], cwd=clone)
            return clone, "main"
    run(["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(clone)])
    return clone, branch


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("zip_path", type=Path)
    ap.add_argument("lang")
    ap.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    ap.add_argument("--raw-base", default=DEFAULT_RAW_BASE)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    lang = args.lang.lower()
    if not re.fullmatch(r"[a-z]{2}", lang):
        die(f"language must be a 2-letter code (got '{args.lang}')")
    if not args.zip_path.is_file():
        die(f"zip not found: {args.zip_path}")

    with tempfile.TemporaryDirectory(prefix="help-pub-") as td:
        workdir = Path(td)

        zip_path = sanitize_zip(args.zip_path, workdir)
        size = zip_path.stat().st_size
        if size > MAX_ZIP_BYTES:
            die(f"zip is {size / 1e6:.0f} MB; GitHub rejects files over 100 MB")
        digest = sha256_of(zip_path)
        print(f"Pack: {zip_path}  {size / 1e6:.1f} MB  sha256={digest[:16]}...")

        clone, branch = clone_repo(args.repo_url, workdir)

        manifest_path = clone / "manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = {"languages": {}}
        manifest.setdefault("languages", {})
        entry = manifest["languages"].get(lang, {})
        version = int(entry.get("version", 0)) + 1
        rel_file = f"{lang}/help-{version}.zip"

        (clone / lang).mkdir(exist_ok=True)
        target = clone / rel_file
        if target.exists():
            die(f"{rel_file} unexpectedly exists in the repo")
        shutil.copy2(zip_path, target)  # copy: the user's original zip stays untouched

        manifest["languages"][lang] = {
            "version": version,
            "file": rel_file,
            "sha256": digest,
            "sizeBytes": size,
            "publishedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        manifest_path.write_text(
            json.dumps({"languages": dict(sorted(manifest["languages"].items()))}, indent=2) + "\n",
            encoding="utf-8",
        )

        print(f"{lang}: v{entry.get('version', 0)} -> v{version} as {rel_file}")
        if args.dry_run:
            print(json.dumps(manifest["languages"][lang], indent=2))
            print("dry-run: nothing committed")
            return

        env_name = run(["git", "config", "--global", "user.name"], check=False)
        git = ["git"]
        if not env_name.stdout.strip():
            git += ["-c", "user.name=Rodion", "-c", "user.email=volkov.rodion@gmail.com"]
        run(git + ["add", "-A"], cwd=clone)
        run(git + ["commit", "-m", f"{lang}: help pack v{version}"], cwd=clone)
        push = run(git + ["push", "origin", f"HEAD:{branch}"], cwd=clone, check=False)
        if push.returncode != 0:
            die(f"push failed (someone published in the meantime? re-run):\n{push.stderr}")

    print("Published:")
    print(f"  manifest: {args.raw_base}/manifest.json")
    print(f"  pack:     {args.raw_base}/{rel_file}")


if __name__ == "__main__":
    main()
