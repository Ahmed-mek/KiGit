# KiGit — KiCad Git workflow plugin

KiGit is a KiCad Python plugin (SWIG `pcbnew.ActionPlugin`) that integrates Git workflows and `kicad-cli` automation to make hardware projects feel closer to modern software development.

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
  - 3D models (STEP, GLB)
  - PCB DRC report (optional DRC guard)

## Quick dev smoke-check (outside KiCad)

```bash
python3 -m py_compile src/kigit/*.py
python3 scripts/build_pcm_zip.py --version 0.1.0
```

The ZIP artifact is written to `dist/`.

## Dev install shortcut (KiCad 10, Linux)

If you want rapid iteration without re-installing the ZIP each time, create a symlink from KiCad’s PCM plugin folder to the staged plugin files:

```bash
python3 scripts/build_pcm_zip.py --version 0.3.0
bash scripts/install_kicad_dev_link.sh
```

This creates a dev entry under:
`~/.local/share/kicad/10.0/3rdparty/plugins/com_github_ahmed_mek_kigit_dev`

## Install in KiCad (manual, for SWIG action plugins)

Copy the *contents* of the ZIP’s `plugins/` directory into your KiCad scripting plugins folder (paths vary by KiCad version/OS).

## Notes

- The plugin keeps UI thin and puts logic in helper modules (easier to test).
- Git operations use the system `git` CLI via `subprocess` (no GitPython dependency).
- `kicad-cli` integration is optional and fails gracefully when missing.
- Auto-export writes all artifacts to `git-exports/` under the project directory.

# KiGit
