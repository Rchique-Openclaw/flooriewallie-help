# flooriewallie-help

## Purpose
CDN-style hosting of FloorieWallie in-app help packs: per-language zips + `manifest.json`, consumed by the app over `raw.githubusercontent.com` URLs so help can update without an app release.

## Ownership
Rodion publishes; the app only reads. This repo is a separate GitHub project, not part of FloorieWallie's history.

## Local Contracts
- `manifest.json` is the app's only contract; it is machine-written by `scripts/publish_help.py` — never hand-edited.
- Packs are immutable and append-only: `<lang>/help-<v>.zip`, never overwrite, never delete (apps mid-update keep valid URLs).
- Zip root = help root: `index.html` must be at top level; `__MACOSX/` junk is stripped at publish time.
- Languages are independent version tracks; publishing one language must not modify another's entry.
- The app verifies sha256 before installing a pack; stale/failed downloads are retried on the next check.

## Work Guidance
- Source zips come from Rodion (typically exported from the help authoring folder).
- Global git `user.name` is unset on this host; the script injects a committer identity itself.

## Verification
- After publishing, `curl` the printed raw manifest and pack URL (HEAD 200, manifest version bumped) — the script prints both links.

## Child DOX Index
(none)
