# Help delivery — design and process

_Why this repo exists, how the pieces fit, and the decisions behind them, so nothing is lost._

## 1. Goal

FloorieWallie shows in-app HTML help (an `index.html` plus referenced pages/images, one pack per language) on a dedicated screen. Help must be updatable **without rebuilding or resubmitting the app**.

## 2. Why this mechanism (and not the alternatives)

| Option | Verdict |
|---|---|
| Bundled in APK/assets only | ❌ every help fix needs an app release |
| Play Asset Delivery (asset packs) | ❌ delivered by Play but **version-pinned to app releases** — it solves download size (>150 MB AAB), not live updates. Games' "downloaded separately, updated later" content is always their own HTTP pipeline, not PAD |
| Dynamic feature modules / OBB | ❌ tied to submissions; downloading *code* outside releases violates Play policy (HTML content is fine) |
| A hosted website | ❌ none available; not actually needed |
| **Static files in a public git repo, fetched via raw URLs** | ✅ one `git push` is the deploy; zero infrastructure; versioned and reviewable by nature |

The help repo must be **public**: raw.githubusercontent.com links to a private repo require a token, and a token in an APK is a leak. FloorieWallie itself stays private — which is also why help lives in its own repo rather than a folder of the app repo (plus binary zips would bloat the app's clone history forever).

## 3. Architecture (app side)

```
assets/help/<lang>/                     frozen baseline shipped in the APK (fallback, offline)
getExternalFilesDir(null)/help/<lang>/  live overlay — downloaded packs land here
```

- **Resolution on Help tap:** overlay `<lang>` dir if it contains `index.html`, else assets. Language = current app locale → fallback to default language.
- **Serving:** WebViewAssetLoader maps everything under a fake https domain; never `file://` (relative links/CORS break). External links open in a Custom Tab.
- **Update check:** fetch `manifest.json` → if `languages.<lang>.version` > installed version (stored per language in prefs/DataStore) → download that pack.

## 4. Repo contract (this repo)

- `manifest.json` — the app's only contract; **machine-written, never hand-edited**:
  `version`, `file` (`<lang>/help-<v>.zip`), `sha256`, `sizeBytes`, `publishedAt`.
- Packs are **immutable and append-only**: never overwrite `help-N.zip`, never delete old packs — apps mid-update keep valid URLs.
- Zip root = help root (`index.html` at top level; `__MACOSX/` junk stripped at publish).
- **Languages are independent version tracks**: publishing `ru` touches nothing in `en` — neither files nor manifest entries; English users download nothing.

## 5. Publish process (human side)

```bash
cd ~/.openclaw/workspace-Developer/flooriewallie-help
python3 scripts/publish_help.py <zip-path> <lang>
```

Script steps: read current version from the remote manifest → sanitize zip (junk out, `index.html` presence check, ≤95 MB guard) → clone the default branch shallowly → write `<lang>/help-<v+1>.zip` → rewrite `manifest.json` → commit + push. On push rejection (concurrent publish) it stops; re-run picks up the new base.

## 6. App-side install logic (robustness rules)

1. Download to a temp file; **verify sha256** against the manifest before touching anything.
2. Extract to a staging dir, then **atomically swap** with the live dir (never extract in place — a crash mid-extract must not leave half-help).
3. Record the new version only after a successful swap.
4. Any failure → keep the previous overlay (or assets fallback). Help is never broken, only possibly stale; retry happens on the next check.

## 7. Consistency & caching notes

- raw.githubusercontent.com caches ~5 min. Versioned filenames make this harmless: a new manifest always points at a **never-before-requested URL**, so a stale cache can only serve the *old* consistent pair, never a torn one.
- Manifest-then-zip are two requests and can straddle a publish; sha256 + retry-on-next-check covers it. For strict atomicity the manifest could pin the **commit SHA** and the app could fetch packs via SHA-pinned URLs (`.../flooriewallie-help/<sha>/<file>` — immutable by construction); not needed at help-criticality, documented as the upgrade path.
- GitHub limits single files to 100 MB (script guards at 95).

## 8. Verification after any publish

```bash
curl -s  https://raw.githubusercontent.com/Rchique-Openclaw/flooriewallie-help/main/manifest.json
curl -sI https://raw.githubusercontent.com/Rchique-Openclaw/flooriewallie-help/main/<lang>/help-<v>.zip   # expect HTTP 200 + content-length
```

The publish script prints both URLs; sha256 of the downloaded pack must equal the manifest value.
