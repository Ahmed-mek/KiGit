# KiGit - Comprehensive Project Analysis & Improvement Plan

This document outlines an analysis of the current state of the **KiGit** project, covering its architecture, features, and a roadmap for potential enhancements.

## 1. Architectural Overview

The KiGit codebase is structured with excellent modularity, separating the KiCad context from the core Git logic. This is highly beneficial for testing and maintainability.

*   **`git_handler.py`**: A robust wrapper around the `git` command-line executable. It handles everything from repository initialization to advanced timeline tracking and auto-tagging.
*   **`kicad_cli.py`**: Interacts with the `kicad-cli` tool (introduced in KiCad 7). This handles the heavy lifting of generating artifacts (PDF, BOM, Gerbers, Drill, SVG, STEP, GLB).
*   **`gitops.py`**: Acts as the orchestrator. It bridges the UI options (`CommitOptions`), the CLI logic (exporting), and the Git logic (committing and auto-versioning).
*   **`project.py`**: Contains discovery logic to locate related KiCad schematic and project files based on the active board path.
*   **`ui_dialog.py` / `ui.py`**: A pure `wxPython` GUI featuring a multi-tabbed layout (Overview, Commit, Branches, Timeline, Sync).
*   **`kigit_action.py`**: The `pcbnew.ActionPlugin` entry point that registers the plugin inside KiCad's Plugin/Action menu and passes the active board context to the dialog.

## 2. Strong Points & Current Features

*   **Decoupled Logic:** The codebase doesn't mix KiCad's Python API (`pcbnew`) directly with the UI or Git logic, which keeps the plugin robust across different KiCad versions.
*   **Automated Artifacts:** Integrating `kicad-cli` on commit is a game-changer. By automatically exporting reproducible snapshots (`git-exports/`) like BOMs, PDFs, and Gerbers alongside the code change, the plugin enforces a professional hardware CI/CD pipeline locally.
*   **Auto-Versioning:** The system intelligently generates version tags (e.g., `v1.0.X`) based on the repository commit count, ensuring traceability of schematic/PCB revisions without requiring the user to manually maintain a version file.
*   **Comprehensive Git Sync:** Native integration for Remote URLs, Pushing, Pulling, and fetching.

---

## 3. Recommended Improvements & Roadmap

Here are the key areas where KiGit can be taken to the next level:

### A. User Experience & Interface (UI/UX)
1.  **Background Processing (Threading):**
    *   *Current State:* Long-running operations like exporting `.step` or `.glb` files block the main UI thread using `wx.BeginBusyCursor()`.
    *   *Improvement:* Use `wx.lib.delayedresult` or `threading.Thread` to run `kicad-cli` and `git` push/pull commands in the background. A progress bar dialog (or gauge in the bottom corner) would keep the user informed without freezing KiCad.
2.  **Persistence of Settings:**
    *   *Current State:* Checkboxes for exports (PDF, BOM, DRC) revert to their default states when the plugin is closed and reopened.
    *   *Improvement:* Save user preferences to a local configuration file (e.g., `kigit.json` in the project root or via KiCad's standard `wx.Config` tools).
3.  **UI State Restoration:**
    *   *Improvement:* Remember the last active tab and the size/position of the `KiGitDialog` window across sessions.

### B. Advanced Version Control Features
1.  **Stashing (`git stash`):**
    *   Often, a hardware designer might want to switch branches to check an older version of the PCB without committing their messy current layout. Adding a "Stash Changes" and "Pop Stash" feature in the Branches tab would be incredibly useful.
2.  **Submodule Support:**
    *   Hardware projects often use external repositories for symbol and footprint libraries. Detecting and updating submodules would make KiGit a comprehensive tool for complex hardware architectures.
3.  **Selective Committing (Staging):**
    *   Currently, the plugin executes `git add -A`. It would be powerful to let the user select which files to stage (e.g., commit schematic only, without the PCB layout).

### C. The "Killer Feature": Visual Diffing
*   *Current State:* The plugin relies on text-based diffing, which isn't very helpful for `.kicad_pcb` layout files.
*   *Improvement:* KiGit already generates `layers_svg` files. By taking the SVG output from `HEAD` and comparing it with the SVG output of the parent commit (or current working directory), the plugin could render a **Visual Overlay Diff**.
    *   **Implementation Idea:** Generate red SVGs for deleted tracks and green SVGs for added tracks. Display them overlaid in a custom `wx.html2.WebView` panel or a standard `wx.Panel` to show the user *exactly* what copper changed before they commit.

### D. Safety & Integrations
1.  **DRC / ERC Blocking Refinement:**
    *   The DRC guard is excellent. Extending this to read the DRC violation count and displaying it within the UI (instead of just a block) would provide better feedback. Adding ERC (Electrical Rules Check for schematics) would complete the verification suite.
2.  **Remote Repository Auto-Creation:**
    *   Integrating the GitHub API or GitLab API to allow users to create a remote repository directly from the KiGit dialog if the remote is empty.
