# KiGit (KiCad Plugin) — repo scaffold

This repository is currently a **scaffold** for a KiCad Python plugin (SWIG `pcbnew.ActionPlugin`) that integrates Git workflows and (optionally) `kicad-cli` automation.

## What’s included right now

- Source layout under `src/kigit/` (development-friendly).
- A build script that produces a **PCM-compatible ZIP** with the exact required shape:
  - `plugins/` (plugin code, flattened)
  - `resources/` (optional PCM listing icon)
  - `metadata.json`
- A minimal SWIG Action Plugin entrypoint (`KiGitAction`) + small wxPython UI for “Smart Commit”.
- A safe `git` subprocess wrapper (`src/kigit/git_handler.py`).
- Best-effort `kicad-cli` hooks for:
  - Schematic PDF export
  - BOM CSV export
  - PCB layer SVG export (for later visual diff)
  - Gerbers + drill export
  - 3D PCB renders (PNG)
  - PCB DRC report (optional DRC guard)

## Quick dev smoke-check (outside KiCad)

```bash
python3 -m py_compile src/kigit/*.py
python3 scripts/build_pcm_zip.py --version 0.1.0
```

The ZIP artifact is written to `dist/`.

## Install in KiCad (manual, for SWIG action plugins)

Copy the *contents* of the ZIP’s `plugins/` directory into your KiCad scripting plugins folder (paths vary by KiCad version/OS).

## Notes

- The plugin keeps UI thin and puts logic in helper modules (easier to test).
- Git operations use the system `git` CLI via `subprocess` (no GitPython dependency).
- `kicad-cli` integration is optional and fails gracefully when missing.
 - Auto-export writes all artifacts to `git-exports/` under the project directory.

# KiGit
