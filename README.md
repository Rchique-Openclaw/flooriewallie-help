# flooriewallie-help

Downloadable help packs for the FloorieWallie Android app. One zip per language,
versioned; the app fetches `manifest.json`, compares its per-language installed
version, and downloads only changed packs.

## Layout

```
manifest.json        <- the only contract the app reads
ru/help-1.zip        <- immutable: never edited, never deleted
en/help-3.zip
scripts/publish_help.py
```

Zip root = help root: `index.html` at top level, referenced pages/images alongside.

## Manifest schema

```json
{
  "languages": {
    "ru": {
      "version": 1,
      "file": "ru/help-1.zip",
      "sha256": "...",
      "sizeBytes": 45000000,
      "publishedAt": "2026-10-27T04:00:00Z"
    }
  }
}
```

Languages are independent: publishing `ru` never touches `en`.

## Publishing

```bash
python3 scripts/publish_help.py /path/to/help.zip ru
```

The script reads the current version from this repo, strips `__MACOSX/` junk,
adds `<lang>/help-<v+1>.zip`, updates `manifest.json`, commits and pushes.
Do not edit `manifest.json` by hand.

## Raw URLs (what the app uses)

- `https://raw.githubusercontent.com/Rchique-Openclaw/flooriewallie-help/main/manifest.json`
- `https://raw.githubusercontent.com/Rchique-Openclaw/flooriewallie-help/main/<lang>/help-<v>.zip`
