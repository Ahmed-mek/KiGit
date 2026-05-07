from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import re


def _wx():
    import wx  # type: ignore

    return wx


def _commit_presets() -> list[tuple[str, str]]:
    """
    (label, commit_message)
    Keep messages short; users can add details before committing.
    """
    return [
        ("Select a preset…", ""),
        ("PCB: routing changes", "PCB: routing changes"),
        ("PCB: component placement", "PCB: component placement"),
        ("PCB: power/ground tweaks", "PCB: power/ground tweaks"),
        ("PCB: board outline/mechanics", "PCB: board outline/mechanics"),
        ("PCB: silkscreen/labels", "PCB: silkscreen/labels"),
        ("PCB: DRC fixes", "PCB: fix DRC violations"),
        ("SCH: update schematic", "SCH: update schematic"),
        ("SCH: netlist/annotation", "SCH: update annotation / net names"),
        ("LIB: symbols/footprints", "LIB: update symbols/footprints"),
        ("BOM: fields cleanup", "BOM: cleanup fields / refs"),
        ("Exports: release package", "Exports: regenerate manufacturing outputs"),
        ("Refactor: project cleanup", "Chore: project cleanup"),
    ]


def _has_stc() -> bool:
    try:
        import wx.stc  # type: ignore  # noqa: F401

        return True
    except Exception:
        return False


def _make_code_view(parent):
    """
    Creates a read-only code-like viewer.
    Prefer StyledTextCtrl for coloring; fall back to TextCtrl.
    """
    wx = _wx()
    if _has_stc():
        import wx.stc as stc  # type: ignore

        view = stc.StyledTextCtrl(parent, style=wx.BORDER_SUNKEN)
        view.SetReadOnly(True)
        view.SetWrapMode(stc.STC_WRAP_NONE)
        view.SetUseHorizontalScrollBar(True)
        view.SetUseVerticalScrollBar(True)
        view.SetMarginWidth(0, 0)
        view.SetMarginWidth(1, 0)
        font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        view.StyleSetFont(stc.STC_STYLE_DEFAULT, font)
        view.StyleSetBackground(stc.STC_STYLE_DEFAULT, "#1E1E1E")
        view.StyleSetForeground(stc.STC_STYLE_DEFAULT, "#E6E6E6")
        view.StyleClearAll()
        return view

    view = wx.TextCtrl(parent, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.BORDER_SUNKEN)
    font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
    view.SetFont(font)
    return view


def _set_text(view, text: str) -> None:
    # Works for both TextCtrl and StyledTextCtrl
    if hasattr(view, "SetReadOnly") and hasattr(view, "SetText"):
        # StyledTextCtrl
        view.SetReadOnly(False)
        view.SetText(text)
        view.SetReadOnly(True)
        return
    view.SetValue(text)


def _style_timeline_graph(view, text: str) -> None:
    if not _has_stc() or not hasattr(view, "StartStyling"):
        return
    import wx.stc as stc  # type: ignore

    # Define small style palette
    STYLE_DEFAULT = 0
    STYLE_GRAPH = 1
    STYLE_HASH = 2
    STYLE_DECOR = 3

    view.StyleSetForeground(STYLE_DEFAULT, "#E6E6E6")
    view.StyleSetForeground(STYLE_GRAPH, "#9AA0A6")
    view.StyleSetForeground(STYLE_HASH, "#4FC3F7")
    view.StyleSetForeground(STYLE_DECOR, "#B39DDB")

    view.StartStyling(0)

    # Very lightweight styling: graph chars, hashes, decorations (...)
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in "|/*\\\\_":
            view.SetStyling(1, STYLE_GRAPH)
            i += 1
            continue
        if re.match(r"[0-9a-f]", ch):
            m = re.match(r"[0-9a-f]{7,40}", text[i:])
            if m:
                n = len(m.group(0))
                view.SetStyling(n, STYLE_HASH)
                i += n
                continue
        if ch == "(":
            end = text.find(")", i)
            if end != -1:
                n = end - i + 1
                view.SetStyling(n, STYLE_DECOR)
                i += n
                continue
        view.SetStyling(1, STYLE_DEFAULT)
        i += 1


def _style_diff(view, text: str) -> None:
    if not _has_stc() or not hasattr(view, "StartStyling"):
        return
    import wx.stc as stc  # type: ignore

    STYLE_DEFAULT = 0
    STYLE_ADD = 10
    STYLE_DEL = 11
    STYLE_HUNK = 12
    STYLE_META = 13

    view.StyleSetForeground(STYLE_DEFAULT, "#E6E6E6")
    view.StyleSetForeground(STYLE_ADD, "#81C784")
    view.StyleSetForeground(STYLE_DEL, "#E57373")
    view.StyleSetForeground(STYLE_HUNK, "#B39DDB")
    view.StyleSetForeground(STYLE_META, "#64B5F6")

    view.StartStyling(0)
    for line in text.splitlines(True):
        style = STYLE_DEFAULT
        if line.startswith("+++ ") or line.startswith("--- ") or line.startswith("diff ") or line.startswith("index "):
            style = STYLE_META
        elif line.startswith("@@"):
            style = STYLE_HUNK
        elif line.startswith("+") and not line.startswith("+++"):
            style = STYLE_ADD
        elif line.startswith("-") and not line.startswith("---"):
            style = STYLE_DEL
        view.SetStyling(len(line), style)


def _style_summary(view, text: str) -> None:
    if not _has_stc() or not hasattr(view, "StartStyling"):
        return

    STYLE_DEFAULT = 0
    STYLE_HEADER = 14
    STYLE_AUTHOR = 15
    STYLE_DATE = 16
    STYLE_STAT_FILE = 17
    STYLE_STAT_ADD = 18
    STYLE_STAT_DEL = 19

    view.StyleSetForeground(STYLE_DEFAULT, "#E6E6E6")
    view.StyleSetForeground(STYLE_HEADER, "#FFB74D")  # Orange
    view.StyleSetForeground(STYLE_AUTHOR, "#4FC3F7")  # Light blue
    view.StyleSetForeground(STYLE_DATE, "#9AA0A6")    # Grey
    view.StyleSetForeground(STYLE_STAT_FILE, "#B39DDB") # Purple
    view.StyleSetForeground(STYLE_STAT_ADD, "#81C784")  # Green
    view.StyleSetForeground(STYLE_STAT_DEL, "#E57373")  # Red

    view.StartStyling(0)
    for line in text.splitlines(True):
        if line.startswith("commit "):
            view.SetStyling(len(line), STYLE_HEADER)
        elif line.startswith("Author:"):
            view.SetStyling(len(line), STYLE_AUTHOR)
        elif line.startswith("Date:"):
            view.SetStyling(len(line), STYLE_DATE)
        elif line.startswith(" ") and "|" in line:
            idx = line.find("|")
            view.SetStyling(idx, STYLE_STAT_FILE)
            view.SetStyling(1, STYLE_DEFAULT)
            rest = line[idx+1:]
            
            plus_count = rest.count("+")
            minus_count = rest.count("-")
            
            if plus_count > 0 or minus_count > 0:
                first_sign = -1
                for i, c in enumerate(rest):
                    if c in "+-":
                        first_sign = i
                        break
                view.SetStyling(first_sign, STYLE_DEFAULT)
                
                for c in rest[first_sign:]:
                    if c == "+":
                        view.SetStyling(1, STYLE_STAT_ADD)
                    elif c == "-":
                        view.SetStyling(1, STYLE_STAT_DEL)
                    else:
                        view.SetStyling(1, STYLE_DEFAULT)
            else:
                view.SetStyling(len(rest), STYLE_DEFAULT)
        elif line.strip().startswith("[Version:"):
            view.SetStyling(len(line), STYLE_HEADER)
        else:
            view.SetStyling(len(line), STYLE_DEFAULT)


def _choice_dialog(parent, title: str, message: str, choices: list[str]) -> Optional[str]:
    wx = _wx()
    dlg = wx.SingleChoiceDialog(parent, message, title, choices)
    try:
        if dlg.ShowModal() != wx.ID_OK:
            return None
        return dlg.GetStringSelection() or None
    finally:
        dlg.Destroy()


@dataclass(frozen=True)
class CommitOptions:
    message: str
    auto_export: bool
    run_drc_guard: bool
    export_pdf: bool
    export_bom: bool
    export_layers_svg: bool
    export_gerbers: bool
    export_drill: bool
    export_images: bool
    export_step: bool
    export_glb: bool
    # smart_footer is always on (no UI toggle)
    smart_footer: bool = True


class KiGitDialog:  # pragma: no cover (runs inside KiCad)
    def __init__(self, project_dir: str, board_file: str):
        wx = _wx()
        self._wx = wx

        self.project_dir = project_dir
        self.board_file = board_file

        from .project import discover_project_files

        self.files = discover_project_files(project_dir, board_file=board_file)

        from .git_handler import GitHandler

        self.git = GitHandler(self.files.project_dir)

        self.dlg = wx.Dialog(None, title="KiGit", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        wx = self._wx

        splitter = wx.SplitterWindow(self.dlg, style=wx.SP_LIVE_UPDATE)
        top_pane = wx.Panel(splitter)
        bottom_pane = wx.Panel(splitter)

        self.notebook = wx.Notebook(top_pane)

        self.page_overview = wx.Panel(self.notebook)
        self.page_commit = wx.Panel(self.notebook)
        self.page_branches = wx.Panel(self.notebook)
        self.page_timeline = wx.Panel(self.notebook)
        self.page_sync = wx.Panel(self.notebook)

        self.notebook.AddPage(self.page_overview, "Overview")
        self.notebook.AddPage(self.page_commit, "Commit")
        self.notebook.AddPage(self.page_branches, "Branches")
        self.notebook.AddPage(self.page_timeline, "Timeline")
        self.notebook.AddPage(self.page_sync, "Sync")

        self.log = wx.TextCtrl(bottom_pane, style=wx.TE_MULTILINE | wx.TE_READONLY)

        top_sizer = wx.BoxSizer(wx.VERTICAL)
        top_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 4)
        top_pane.SetSizer(top_sizer)

        bottom_sizer = wx.BoxSizer(wx.VERTICAL)
        bottom_sizer.Add(wx.StaticText(bottom_pane, label="Log"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 4)
        bottom_sizer.Add(self.log, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)
        bottom_pane.SetSizer(bottom_sizer)

        splitter.SetMinimumPaneSize(100)
        splitter.SplitHorizontally(top_pane, bottom_pane, sashPosition=-150)

        btn_refresh = wx.Button(self.dlg, label="Refresh")
        btn_close = wx.Button(self.dlg, label="Close")
        btn_close.Bind(wx.EVT_BUTTON, lambda evt: self.dlg.EndModal(wx.ID_OK))
        btn_refresh.Bind(wx.EVT_BUTTON, lambda evt: self.refresh())

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.Add(btn_refresh, 0, wx.ALL, 6)
        btn_sizer.AddStretchSpacer(1)
        btn_sizer.Add(btn_close, 0, wx.ALL, 6)

        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(splitter, 1, wx.EXPAND | wx.ALL, 4)
        root.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        self.dlg.SetSizer(root)
        self.dlg.SetMinSize((720, 560))

        self._build_overview_tab()
        self._build_commit_tab()
        self._build_branches_tab()
        self._build_timeline_tab()
        self._build_sync_tab()

    def _build_overview_tab(self) -> None:
        wx = self._wx

        grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=10)
        grid.AddGrowableCol(1, 1)

        def row(label: str):
            grid.Add(wx.StaticText(self.page_overview, label=label), 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
            value = wx.StaticText(self.page_overview, label="")
            grid.Add(value, 1, wx.EXPAND)
            return value

        self.txt_project_dir = row("Project dir")
        self.txt_repo_root = row("Repo root")
        self.txt_branch = row("Branch")
        self.txt_board = row("Board")
        self.txt_schematic = row("Schematic")
        self.txt_cli = row("kicad-cli")
        self.txt_exports = row("Exports folder")

        self.status_box = wx.TextCtrl(self.page_overview, style=wx.TE_MULTILINE | wx.TE_READONLY)

        btn_init = wx.Button(self.page_overview, label="Initialize Git Repo…")
        btn_init.Bind(wx.EVT_BUTTON, lambda evt: self._on_init_repo())

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 10)
        sizer.Add(btn_init, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        sizer.Add(wx.StaticText(self.page_overview, label="Git status (porcelain)"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        sizer.Add(self.status_box, 1, wx.EXPAND | wx.ALL, 10)
        self.page_overview.SetSizer(sizer)

        self.btn_init_repo = btn_init

    def _build_commit_tab(self) -> None:
        wx = self._wx

        default_msg = "KiCad: update design"
        if self.files.board_file:
            default_msg = f"KiCad: update {Path(self.files.board_file).stem}"

        self.commit_msg = wx.TextCtrl(self.page_commit, value=default_msg, style=wx.TE_MULTILINE)
        self.chk_export = wx.CheckBox(self.page_commit, label="Enable exports to git-exports/")
        self.chk_export.SetValue(True)

        exports_box = wx.StaticBoxSizer(wx.StaticBox(self.page_commit, label="Exports"), wx.VERTICAL)
        self.chk_pdf = wx.CheckBox(self.page_commit, label="Schematic PDF")
        self.chk_bom = wx.CheckBox(self.page_commit, label="BOM (CSV)")
        self.chk_layers_svg = wx.CheckBox(self.page_commit, label="PCB layer snapshots (SVG)")
        self.chk_gerbers = wx.CheckBox(self.page_commit, label="Gerbers")
        self.chk_drill = wx.CheckBox(self.page_commit, label="Drill files")
        self.chk_images = wx.CheckBox(self.page_commit, label="PCB renders (PNG)")
        self.chk_step = wx.CheckBox(self.page_commit, label="3D model (STEP)")
        self.chk_glb = wx.CheckBox(self.page_commit, label="3D model (GLB)")

        for chk in (
            self.chk_pdf,
            self.chk_bom,
            self.chk_layers_svg,
            self.chk_gerbers,
            self.chk_drill,
            self.chk_images,
        ):
            chk.SetValue(True)
        # 3D exports can be large/slow; default OFF.
        self.chk_step.SetValue(False)
        self.chk_glb.SetValue(False)

        exports_box.Add(self.chk_pdf, 0, wx.ALL, 4)
        exports_box.Add(self.chk_bom, 0, wx.ALL, 4)
        exports_box.Add(self.chk_layers_svg, 0, wx.ALL, 4)
        exports_box.Add(self.chk_gerbers, 0, wx.ALL, 4)
        exports_box.Add(self.chk_drill, 0, wx.ALL, 4)
        exports_box.Add(self.chk_images, 0, wx.ALL, 4)
        exports_box.Add(self.chk_step, 0, wx.ALL, 4)
        exports_box.Add(self.chk_glb, 0, wx.ALL, 4)

        self.chk_export.Bind(wx.EVT_CHECKBOX, lambda evt: self._sync_export_enable())
        self.chk_drc = wx.CheckBox(self.page_commit, label="DRC guard (block commit if DRC violations exist)")
        self.chk_drc.SetValue(False)

        # Smart footer is always enabled (no checkbox).

        self.commit_presets = wx.Choice(self.page_commit, choices=[p[0] for p in _commit_presets()])
        self.commit_presets.SetSelection(0)
        self.commit_presets.Bind(wx.EVT_CHOICE, lambda evt: self._apply_preset())

        btn_export = wx.Button(self.page_commit, label="Export Now…")
        btn_commit = wx.Button(self.page_commit, label="Commit…")
        btn_export_commit = wx.Button(self.page_commit, label="Export + Commit")

        btn_export.Bind(wx.EVT_BUTTON, lambda evt: self._on_export_only())
        btn_commit.Bind(wx.EVT_BUTTON, lambda evt: self._on_commit_only())
        btn_export_commit.Bind(wx.EVT_BUTTON, lambda evt: self._on_export_and_commit())

        btns = wx.BoxSizer(wx.HORIZONTAL)
        btns.Add(btn_export, 0, wx.ALL, 6)
        btns.Add(btn_commit, 0, wx.ALL, 6)
        btns.AddStretchSpacer(1)
        btns.Add(btn_export_commit, 0, wx.ALL, 6)

        info = wx.StaticText(
            self.page_commit,
            label="Tip: A footer like [Version: v1.0.N] [Date: YYYY-MM-DD HH:MM:SS] is appended automatically.",
        )

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self.page_commit, label="Commit message"), 0, wx.ALL, 8)
        preset_row = wx.BoxSizer(wx.HORIZONTAL)
        preset_row.Add(wx.StaticText(self.page_commit, label="Presets"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 6)
        preset_row.Add(self.commit_presets, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 6)
        sizer.Add(preset_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 2)
        sizer.Add(self.commit_msg, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        sizer.Add(self.chk_export, 0, wx.ALL, 8)
        sizer.Add(exports_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        sizer.Add(self.chk_drc, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        sizer.Add(info, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        sizer.Add(btns, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        self.page_commit.SetSizer(sizer)
        self._sync_export_enable()

    def _sync_export_enable(self) -> None:
        enabled = bool(self.chk_export.GetValue())
        for chk in (
            self.chk_pdf,
            self.chk_bom,
            self.chk_layers_svg,
            self.chk_gerbers,
            self.chk_drill,
            self.chk_images,
            self.chk_step,
            self.chk_glb,
        ):
            chk.Enable(enabled)

    def _build_branches_tab(self) -> None:
        wx = self._wx

        self.branches = wx.ListBox(self.page_branches)

        btn_refresh = wx.Button(self.page_branches, label="Refresh")
        btn_checkout = wx.Button(self.page_branches, label="Checkout…")
        btn_create = wx.Button(self.page_branches, label="Create Branch…")

        btn_refresh.Bind(wx.EVT_BUTTON, lambda evt: self._refresh_branches())
        btn_checkout.Bind(wx.EVT_BUTTON, lambda evt: self._on_checkout_branch())
        btn_create.Bind(wx.EVT_BUTTON, lambda evt: self._on_create_branch())

        btns = wx.BoxSizer(wx.HORIZONTAL)
        btns.Add(btn_refresh, 0, wx.ALL, 6)
        btns.Add(btn_checkout, 0, wx.ALL, 6)
        btns.Add(btn_create, 0, wx.ALL, 6)
        btns.AddStretchSpacer(1)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self.page_branches, label="Local branches"), 0, wx.ALL, 8)
        sizer.Add(self.branches, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        sizer.Add(btns, 0, wx.EXPAND | wx.ALL, 6)
        self.page_branches.SetSizer(sizer)

    def _build_timeline_tab(self) -> None:
        wx = self._wx

        top = wx.BoxSizer(wx.VERTICAL)

        self.chk_all_branches = wx.CheckBox(self.page_timeline, label="Show all branches")
        self.chk_all_branches.SetValue(True)

        self.spin_count = wx.SpinCtrl(self.page_timeline, min=10, max=500, initial=80)
        self.spin_count.SetMinSize((90, -1))

        toolbar = wx.BoxSizer(wx.HORIZONTAL)
        toolbar.Add(self.chk_all_branches, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 6)
        toolbar.AddStretchSpacer(1)
        toolbar.Add(wx.StaticText(self.page_timeline, label="Max commits"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 6)
        toolbar.Add(self.spin_count, 0, wx.ALL, 6)

        btn_refresh = wx.Button(self.page_timeline, label="Refresh")
        btn_diff_parent = wx.Button(self.page_timeline, label="Diff to parent")
        btn_copy_hash = wx.Button(self.page_timeline, label="Copy hash")

        btn_refresh.Bind(wx.EVT_BUTTON, lambda evt: self._refresh_timeline())
        btn_diff_parent.Bind(wx.EVT_BUTTON, lambda evt: self._show_diff_to_parent())
        btn_copy_hash.Bind(wx.EVT_BUTTON, lambda evt: self._copy_selected_hash())

        btns = wx.BoxSizer(wx.HORIZONTAL)
        btns.Add(btn_refresh, 0, wx.ALL, 6)
        btns.Add(btn_diff_parent, 0, wx.ALL, 6)
        btns.AddStretchSpacer(1)
        btns.Add(btn_copy_hash, 0, wx.ALL, 6)

        splitter = wx.SplitterWindow(self.page_timeline, style=wx.SP_LIVE_UPDATE)
        left = wx.Panel(splitter)
        right = wx.Panel(splitter)

        # IMPORTANT: these controls must be parented to their splitter panes,
        # otherwise wx will lay them out as children of page_timeline and they will overlap.
        self.graph_box = _make_code_view(left)

        self.commits = wx.ListCtrl(left, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.commits.InsertColumn(0, "Hash", width=80)
        self.commits.InsertColumn(1, "Date", width=160)
        self.commits.InsertColumn(2, "Author", width=140)
        self.commits.InsertColumn(3, "Message", width=520)
        self.commits.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda evt: self._on_select_commit())

        self.details = _make_code_view(right)

        left_s = wx.BoxSizer(wx.VERTICAL)
        left_s.Add(wx.StaticText(left, label="Graph"), 0, wx.ALL, 6)
        left_s.Add(self.graph_box, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        left_s.Add(wx.StaticText(left, label="Commits"), 0, wx.ALL, 6)
        left_s.Add(self.commits, 2, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        left.SetSizer(left_s)

        right_s = wx.BoxSizer(wx.VERTICAL)
        right_s.Add(wx.StaticText(right, label="Details"), 0, wx.ALL, 6)
        right_s.Add(self.details, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        right.SetSizer(right_s)

        splitter.SetMinimumPaneSize(220)
        splitter.SetSashGravity(0.5)
        splitter.SplitVertically(left, right, sashPosition=420)

        top.Add(toolbar, 0, wx.EXPAND)
        top.Add(btns, 0, wx.EXPAND)
        top.Add(splitter, 1, wx.EXPAND | wx.ALL, 6)
        self.page_timeline.SetSizer(top)

    def _build_sync_tab(self) -> None:
        wx = self._wx

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Remote Settings
        remote_box = wx.StaticBoxSizer(wx.StaticBox(self.page_sync, label="Remote Repository"), wx.VERTICAL)
        
        self.txt_remote_url = wx.TextCtrl(self.page_sync)
        btn_set_remote = wx.Button(self.page_sync, label="Set Remote URL…")
        btn_set_remote.Bind(wx.EVT_BUTTON, lambda evt: self._on_set_remote())

        remote_hz = wx.BoxSizer(wx.HORIZONTAL)
        remote_hz.Add(wx.StaticText(self.page_sync, label="Origin URL:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 6)
        remote_hz.Add(self.txt_remote_url, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 6)
        remote_hz.Add(btn_set_remote, 0, wx.ALL, 6)
        
        remote_box.Add(remote_hz, 0, wx.EXPAND | wx.ALL, 6)
        
        # Sync Actions (Push / Pull)
        sync_box = wx.StaticBoxSizer(wx.StaticBox(self.page_sync, label="Synchronize"), wx.HORIZONTAL)
        
        btn_pull = wx.Button(self.page_sync, label="Pull (Fetch + Merge)")
        btn_push = wx.Button(self.page_sync, label="Push to Origin")

        btn_pull.Bind(wx.EVT_BUTTON, lambda evt: self._on_pull())
        btn_push.Bind(wx.EVT_BUTTON, lambda evt: self._on_push())
        
        sync_box.Add(btn_pull, 1, wx.ALL | wx.EXPAND, 6)
        sync_box.Add(btn_push, 1, wx.ALL | wx.EXPAND, 6)

        info_text = (
            "Authentication / التحقق من الهوية:\n"
            "KiGit uses your system's Git credentials.\n"
            "If using HTTPS, ensure a Git Credential Manager is installed.\n"
            "If using SSH (git@github.com:...), ensure your SSH keys are set up."
        )

        sizer.Add(remote_box, 0, wx.EXPAND | wx.ALL, 8)
        sizer.Add(sync_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        sizer.AddStretchSpacer(1)
        sizer.Add(wx.StaticText(self.page_sync, label=info_text), 0, wx.ALL, 8)

        self.page_sync.SetSizer(sizer)

    def ShowModal(self) -> int:
        return self.dlg.ShowModal()

    def Destroy(self) -> None:
        self.dlg.Destroy()

    def _log(self, text: str) -> None:
        self.log.AppendText(text.rstrip() + "\n")

    def refresh(self) -> None:
        wx = self._wx
        self._log("---------------------Refreshing------------------")

        self.txt_project_dir.SetLabel(self.files.project_dir)
        self.txt_board.SetLabel(self.files.board_file or "(not found)")
        self.txt_schematic.SetLabel(self.files.schematic_file or "(not found)")
        self.txt_exports.SetLabel(str(Path(self.files.project_dir) / "git-exports"))

        is_repo = self.git.is_git_repo()
        self.btn_init_repo.Enable(not is_repo)

        if is_repo:
            self.txt_repo_root.SetLabel(self.git.repo_root())
            try:
                self.txt_branch.SetLabel(self.git.current_branch())
            except Exception:
                self.txt_branch.SetLabel("(unknown)")
            try:
                self.status_box.SetValue(self.git.status_porcelain())
            except Exception as exc:
                self.status_box.SetValue(f"(status error) {exc}")
            try:
                self.txt_remote_url.SetValue(self.git.get_remote_url())
            except Exception:
                self.txt_remote_url.SetValue("")
        else:
            self.txt_repo_root.SetLabel("(not a git repo)")
            self.txt_branch.SetLabel("")
            self.status_box.SetValue("")
            self.txt_remote_url.SetValue("")

        from .kicad_cli import KiCadCli, KiCadCliNotFound

        try:
            KiCadCli.detect()
            self.txt_cli.SetLabel("available")
        except KiCadCliNotFound:
            self.txt_cli.SetLabel("not found")

        self._refresh_branches()
        self._refresh_timeline()
        wx.CallAfter(self.dlg.Layout)

    def _refresh_branches(self) -> None:
        self.branches.Clear()
        if not self.git.is_git_repo():
            return
        try:
            current = self.git.current_branch()
        except Exception:
            current = ""
        for name in self.git.list_branches():
            label = f"* {name}" if name == current else name
            self.branches.Append(label)

    def _on_init_repo(self) -> None:
        wx = self._wx
        if self.git.is_git_repo():
            return

        resp = wx.MessageBox(
            "Initialize a Git repository in this project directory?",
            "KiGit",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )
        if resp != wx.YES:
            return
        self.git.init()
        self._log("Initialized git repository.")

        resp_ig = wx.MessageBox(
            "Create a KiCad-friendly .gitignore now?",
            "KiGit",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )
        if resp_ig == wx.YES:
            template_path = Path(__file__).resolve().parent / "gitignore_template.txt"
            template_text = template_path.read_text(encoding="utf-8")
            created = self.git.ensure_gitignore(template_text)
            self._log("Created .gitignore." if created else ".gitignore already exists.")

        # Mandatory remote setup + connectivity check (first-time).
        self.notebook.SetSelection(4)  # Sync tab index: Overview, Commit, Branches, Timeline, Sync
        while True:
            dlg = wx.TextEntryDialog(
                self.dlg,
                "Enter remote repository URL for 'origin' (SSH or HTTPS):",
                "Set Remote URL",
                self.txt_remote_url.GetValue() if hasattr(self, "txt_remote_url") else "",
            )
            try:
                if dlg.ShowModal() != wx.ID_OK:
                    wx.MessageBox(
                        "Remote URL is required to complete setup. You can set it later in the Sync tab.",
                        "KiGit",
                        wx.OK | wx.ICON_WARNING,
                    )
                    break
                remote_url = (dlg.GetValue() or "").strip()
            finally:
                dlg.Destroy()

            if not remote_url:
                wx.MessageBox("Remote URL cannot be empty.", "KiGit", wx.OK | wx.ICON_WARNING)
                continue

            try:
                self.git.set_remote_url(remote_url)
                self.txt_remote_url.SetValue(remote_url)
            except Exception as exc:
                wx.MessageBox(str(exc), "KiGit", wx.OK | wx.ICON_ERROR)
                continue

            # Connectivity check
            try:
                self._run_with_busy(lambda: self.git.check_remote("origin"), "Checking remote connectivity…")
                self._log("Remote connectivity: OK")
                break
            except Exception as exc:
                retry = wx.MessageBox(
                    f"Remote connectivity check failed:\n\n{exc}\n\nRetry?",
                    "KiGit",
                    wx.YES_NO | wx.NO_DEFAULT | wx.ICON_ERROR,
                )
                if retry != wx.YES:
                    self._log("Remote connectivity: FAILED (kept URL)")
                    break

        self.refresh()

    def _collect_commit_options(self, *, force_export: Optional[bool] = None) -> CommitOptions:
        msg = (self.commit_msg.GetValue() or "").strip()
        if not msg:
            raise RuntimeError("Commit message is required")
        auto_export = bool(self.chk_export.GetValue()) if force_export is None else bool(force_export)
        export_pdf = bool(self.chk_pdf.GetValue()) and auto_export
        export_bom = bool(self.chk_bom.GetValue()) and auto_export
        export_layers_svg = bool(self.chk_layers_svg.GetValue()) and auto_export
        export_gerbers = bool(self.chk_gerbers.GetValue()) and auto_export
        export_drill = bool(self.chk_drill.GetValue()) and auto_export
        export_images = bool(self.chk_images.GetValue()) and auto_export
        export_step = bool(self.chk_step.GetValue()) and auto_export
        export_glb = bool(self.chk_glb.GetValue()) and auto_export
        return CommitOptions(
            message=msg,
            auto_export=auto_export,
            run_drc_guard=bool(self.chk_drc.GetValue()),
            export_pdf=export_pdf,
            export_bom=export_bom,
            export_layers_svg=export_layers_svg,
            export_gerbers=export_gerbers,
            export_drill=export_drill,
            export_images=export_images,
            export_step=export_step,
            export_glb=export_glb,
            smart_footer=True,
        )

    def _apply_preset(self) -> None:
        idx = self.commit_presets.GetSelection()
        if idx < 0:
            return
        presets = _commit_presets()
        if idx >= len(presets):
            return
        preset_msg = presets[idx][1]
        if not preset_msg:
            return
        current = self.commit_msg.GetValue() or ""
        lines = current.splitlines()
        if not lines:
            new_text = preset_msg
        else:
            # Replace the first line (title) and keep any extra details the user wrote.
            # If the user pasted a multi-line message, preserve everything after line 1.
            tail = "\n".join(lines[1:]).lstrip("\n")
            new_text = preset_msg if not tail else f"{preset_msg}\n{tail}"
        self.commit_msg.SetValue(new_text)
        try:
            self.commit_msg.SetInsertionPointEnd()
        except Exception:
            pass

    def _run_with_busy(self, fn, label: str) -> None:
        wx = self._wx
        self._log(label)
        wx.BeginBusyCursor()
        try:
            fn()
        finally:
            if wx.IsBusy():
                wx.EndBusyCursor()

    def _on_export_only(self) -> None:
        wx = self._wx
        if not bool(self.chk_export.GetValue()):
            wx.MessageBox("Enable exports first (Commit tab).", "KiGit", wx.OK | wx.ICON_INFORMATION)
            return

        export_pdf = bool(self.chk_pdf.GetValue())
        export_bom = bool(self.chk_bom.GetValue())
        export_layers_svg = bool(self.chk_layers_svg.GetValue())
        export_gerbers = bool(self.chk_gerbers.GetValue())
        export_drill = bool(self.chk_drill.GetValue())
        export_images = bool(self.chk_images.GetValue())
        export_step = bool(self.chk_step.GetValue())
        export_glb = bool(self.chk_glb.GetValue())

        if not any([export_pdf, export_bom, export_layers_svg, export_gerbers, export_drill, export_images, export_step, export_glb]):
            wx.MessageBox("No exports selected.", "KiGit", wx.OK | wx.ICON_INFORMATION)
            return

        def work():
            from .kicad_cli import KiCadCli

            cli = KiCadCli.detect()
            cli.export_artifacts(
                project_dir=self.files.project_dir,
                schematic_file=self.files.schematic_file,
                board_file=self.files.board_file,
                export_pdf=export_pdf,
                export_bom=export_bom,
                export_layers_svg=export_layers_svg,
                export_gerbers=export_gerbers,
                export_drill=export_drill,
                export_images=export_images,
                export_step=export_step,
                export_glb=export_glb,
            )
            self._log("Export complete: git-exports/")

        try:
            self._run_with_busy(work, "Running exports…")
            self.refresh()
        except Exception as exc:
            wx.MessageBox(str(exc), "KiGit Export Failed", wx.OK | wx.ICON_ERROR)

    def _on_commit_only(self) -> None:
        self._run_commit(force_export=False)

    def _on_export_and_commit(self) -> None:
        self._run_commit(force_export=True)

    def _run_commit(self, *, force_export: Optional[bool]) -> None:
        wx = self._wx
        if not self.git.is_git_repo():
            wx.MessageBox("Initialize a Git repo first (Overview tab).", "KiGit", wx.OK | wx.ICON_WARNING)
            return

        def work():
            from .gitops import smart_commit

            opts = self._collect_commit_options(force_export=force_export)
            result = smart_commit(
                self.git,
                opts,
                board_file=self.files.board_file,
                schematic_file=self.files.schematic_file,
            )
            self._log(result)

        try:
            self._run_with_busy(work, "Committing…")
            self.refresh()
        except Exception as exc:
            wx.MessageBox(str(exc), "KiGit Commit Failed", wx.OK | wx.ICON_ERROR)

    def _selected_branch(self) -> Optional[str]:
        sel = self.branches.GetSelection()
        if sel == self._wx.NOT_FOUND:
            return None
        label = self.branches.GetString(sel).strip()
        if label.startswith("* "):
            label = label[2:]
        return label or None

    def _on_checkout_branch(self) -> None:
        wx = self._wx
        name = self._selected_branch()
        if not name:
            wx.MessageBox("Select a branch first.", "KiGit", wx.OK | wx.ICON_INFORMATION)
            return
        resp = wx.MessageBox(f"Checkout branch '{name}'?", "KiGit", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        if resp != wx.YES:
            return
        try:
            self.git.checkout(name)
            self._log(f"Checked out: {name}")
            self.refresh()
        except Exception as exc:
            wx.MessageBox(str(exc), "KiGit", wx.OK | wx.ICON_ERROR)

    def _on_create_branch(self) -> None:
        wx = self._wx
        dlg = wx.TextEntryDialog(self.dlg, "New branch name:", "Create Branch")
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            name = (dlg.GetValue() or "").strip()
        finally:
            dlg.Destroy()
        if not name:
            return
        try:
            self.git.create_branch(name, checkout=True)
            self._log(f"Created and checked out: {name}")
            self.refresh()
        except Exception as exc:
            wx.MessageBox(str(exc), "KiGit", wx.OK | wx.ICON_ERROR)

    def _refresh_timeline(self) -> None:
        if not self.git.is_git_repo():
            _set_text(self.graph_box, "(not a git repo)")
            self.commits.DeleteAllItems()
            _set_text(self.details, "")
            return

        all_branches = bool(self.chk_all_branches.GetValue())
        max_commits = int(self.spin_count.GetValue())
        try:
            graph = self.git.log_graph(max_count=max_commits, all_branches=all_branches)
            _set_text(self.graph_box, graph)
            _style_timeline_graph(self.graph_box, graph)
        except Exception as exc:
            _set_text(self.graph_box, f"(log error) {exc}")

        self.commits.DeleteAllItems()
        try:
            tsv = self.git.log_commits_tsv(max_count=max_commits, all_branches=all_branches)
        except Exception as exc:
            _set_text(self.details, f"(log error) {exc}")
            return

        for row in tsv.splitlines():
            parts = row.split("\t")
            if len(parts) < 5:
                continue
            short_hash, date, author, decorations, subject = parts[0], parts[1], parts[2], parts[3], parts[4]
            idx = self.commits.InsertItem(self.commits.GetItemCount(), short_hash)
            self.commits.SetItem(idx, 1, date)
            self.commits.SetItem(idx, 2, author)
            msg = subject
            if decorations.strip():
                msg = f"{subject} {decorations.strip()}"
            self.commits.SetItem(idx, 3, msg)
            # Row coloring heuristic
            lower = subject.lower()
            color = None
            if lower.startswith("feat:"):
                color = "#81C784"
            elif lower.startswith("fix:"):
                color = "#E57373"
            elif lower.startswith("chore:") or lower.startswith("refactor:"):
                color = "#B0BEC5"
            elif lower.startswith("pcb:"):
                color = "#64B5F6"
            elif lower.startswith("sch:"):
                color = "#4DB6AC"
            elif lower.startswith("exports:"):
                color = "#FFB74D"
            if color:
                item = self.commits.GetItem(idx)
                item.SetTextColour(color)
                self.commits.SetItem(item)

        if self.commits.GetItemCount() > 0 and self.commits.GetFirstSelected() == -1:
            self.commits.Select(0)
            self._on_select_commit()

    def _selected_hash(self) -> Optional[str]:
        idx = self.commits.GetFirstSelected()
        if idx == -1:
            return None
        return self.commits.GetItemText(idx) or None

    def _on_select_commit(self) -> None:
        rev = self._selected_hash()
        if not rev:
            _set_text(self.details, "")
            return
        try:
            summary = self.git.show_summary(rev)
            _set_text(self.details, summary)
            _style_summary(self.details, summary)
        except Exception as exc:
            _set_text(self.details, f"(show error) {exc}")

    def _show_diff_to_parent(self) -> None:
        wx = self._wx
        rev = self._selected_hash()
        if not rev:
            wx.MessageBox("Select a commit first.", "KiGit", wx.OK | wx.ICON_INFORMATION)
            return
        try:
            diff_text = self.git.diff_to_parent(rev)
        except Exception as exc:
            wx.MessageBox(str(exc), "KiGit", wx.OK | wx.ICON_ERROR)
            return
        # Show diff in-place (can be big).
        diff = diff_text or "(no diff)"
        _set_text(self.details, diff)
        _style_diff(self.details, diff)

    def _copy_selected_hash(self) -> None:
        wx = self._wx
        rev = self._selected_hash()
        if not rev:
            return
        if wx.TheClipboard.Open():
            try:
                wx.TheClipboard.SetData(wx.TextDataObject(rev))
            finally:
                wx.TheClipboard.Close()

    def _on_set_remote(self) -> None:
        wx = self._wx
        if not self.git.is_git_repo():
            wx.MessageBox("Initialize a Git repo first.", "KiGit", wx.OK | wx.ICON_WARNING)
            return
        
        current_url = self.txt_remote_url.GetValue()
        dlg = wx.TextEntryDialog(self.dlg, "Enter Git remote URL (origin):", "Set Remote URL", current_url)
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            new_url = dlg.GetValue().strip()
        finally:
            dlg.Destroy()
            
        if not new_url:
            return
            
        try:
            self.git.set_remote_url(new_url)
            self._log(f"Remote URL set to: {new_url}")
            try:
                self._run_with_busy(lambda: self.git.check_remote("origin"), "Checking remote connectivity…")
                self._log("Remote connectivity: OK")
            except Exception as exc:
                wx.MessageBox(
                    f"Remote connectivity check failed:\n\n{exc}",
                    "KiGit",
                    wx.OK | wx.ICON_ERROR,
                )
            self.refresh()
        except Exception as exc:
            wx.MessageBox(str(exc), "KiGit", wx.OK | wx.ICON_ERROR)

    def _on_push(self) -> None:
        wx = self._wx
        if not self.git.is_git_repo():
            wx.MessageBox("Initialize a Git repo first.", "KiGit", wx.OK | wx.ICON_WARNING)
            return
        
        remote = self.txt_remote_url.GetValue().strip()
        if not remote:
            wx.MessageBox("Please set a Remote URL first.", "KiGit", wx.OK | wx.ICON_WARNING)
            return

        resp = wx.MessageBox(
            f"Push current branch to origin?\n\nRemote:\n{remote}",
            "KiGit",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )
        if resp != wx.YES:
            return

        try:
            out_holder: dict[str, str] = {"out": ""}

            def work():
                out_holder["out"] = self.git.push(include_tags=False)

            self._run_with_busy(work, "Pushing to remote…")
            self._log(f"Push successful:\n{out_holder['out']}")
            wx.MessageBox("Push completed successfully.", "KiGit", wx.OK | wx.ICON_INFORMATION)
            self.refresh()
        except Exception as exc:
            err = str(exc)
            # Non-fast-forward is very common: offer guided resolution.
            if ("non-fast-forward" in err) or ("fetch first" in err) or ("rejected" in err and "fast-forward" in err):
                choice = _choice_dialog(
                    self.dlg,
                    "Push rejected",
                    "Remote has new commits. Choose how to proceed:",
                    [
                        "Pull (rebase), then push",
                        "Pull (merge), then push",
                        "Cancel",
                    ],
                )
                if choice and choice != "Cancel":
                    try:
                        if choice.startswith("Pull (rebase)"):
                            self._run_with_busy(lambda: self.git.pull_rebase(), "Pulling (rebase)…")
                        else:
                            self._run_with_busy(lambda: self.git.pull_merge(), "Pulling (merge)…")
                        self._run_with_busy(lambda: self.git.push(include_tags=False), "Pushing…")
                        wx.MessageBox("Sync completed successfully.", "KiGit", wx.OK | wx.ICON_INFORMATION)
                        self.refresh()
                        return
                    except Exception as exc2:
                        wx.MessageBox(f"Sync failed:\n{exc2}", "KiGit Error", wx.OK | wx.ICON_ERROR)
                        return
            wx.MessageBox(f"Push failed:\n{exc}", "KiGit Error", wx.OK | wx.ICON_ERROR)

    def _on_pull(self) -> None:
        wx = self._wx
        if not self.git.is_git_repo():
            wx.MessageBox("Initialize a Git repo first.", "KiGit", wx.OK | wx.ICON_WARNING)
            return

        remote = self.txt_remote_url.GetValue().strip()
        if not remote:
            wx.MessageBox("Please set a Remote URL first.", "KiGit", wx.OK | wx.ICON_WARNING)
            return

        resp = wx.MessageBox(
            f"Pull updates from origin into current branch?\n\nRemote:\n{remote}",
            "KiGit",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )
        if resp != wx.YES:
            return

        # Special case: repo has no commits yet, but local project files exist.
        # Pulling from a non-empty remote requires checking out remote branch, which can overwrite untracked files.
        if not self.git.has_commits() and self.git.has_untracked_files():
            untracked = self.git.list_untracked_paths()
            msg = (
                "This repo has no local commits yet, but there are local untracked files.\n\n"
                "Pulling from the remote will replace files in this folder.\n\n"
                "Do you want KiGit to BACK UP your local files to .kigit-backups/ and then pull?"
            )
            resp2 = wx.MessageBox(msg, "KiGit", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
            if resp2 != wx.YES:
                return

            from datetime import datetime
            from pathlib import Path

            backup_dir = Path(self.files.project_dir) / ".kigit-backups" / f"backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            try:
                moved = self.git.backup_paths(untracked, str(backup_dir))
                self._log(f"Backed up {len(moved)} files to: {backup_dir}")
            except Exception as exc:
                wx.MessageBox(f"Backup failed:\n{exc}", "KiGit", wx.OK | wx.ICON_ERROR)
                return

        def work_pull() -> str:
            return self.git.pull()

        try:
            out_holder: dict[str, str] = {"out": ""}

            def work():
                out_holder["out"] = work_pull()

            self._run_with_busy(work, "Pulling from remote…")
            self._log(f"Pull successful:\n{out_holder['out']}")
            wx.MessageBox("Pull completed successfully.", "KiGit", wx.OK | wx.ICON_INFORMATION)
            self.refresh()
        except Exception as exc:
            err = str(exc)
            # Handle untracked overwrite case with a backup option (even for non-empty repos).
            if "untracked working tree files would be overwritten" in err.lower():
                untracked = self.git.list_untracked_paths()
                msg = (
                    "Git refused to pull because local untracked files would be overwritten.\n\n"
                    "Do you want KiGit to back them up into .kigit-backups/ and retry?"
                )
                resp2 = wx.MessageBox(msg, "KiGit", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING)
                if resp2 == wx.YES:
                    from datetime import datetime
                    from pathlib import Path

                    backup_dir = Path(self.files.project_dir) / ".kigit-backups" / f"backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                    try:
                        moved = self.git.backup_paths(untracked, str(backup_dir))
                        self._log(f"Backed up {len(moved)} files to: {backup_dir}")
                        out_holder2: dict[str, str] = {"out": ""}

                        def work2():
                            out_holder2["out"] = work_pull()

                        self._run_with_busy(work2, "Pulling from remote…")
                        self._log(f"Pull successful:\n{out_holder2['out']}")
                        wx.MessageBox("Pull completed successfully.", "KiGit", wx.OK | wx.ICON_INFORMATION)
                        self.refresh()
                        return
                    except Exception as exc2:
                        wx.MessageBox(f"Backup/pull failed:\n{exc2}", "KiGit Error", wx.OK | wx.ICON_ERROR)
                        return

            # Offer strategy choices when ff-only fails or conflicts happen.
            choice = _choice_dialog(
                self.dlg,
                "Pull failed",
                "Choose a safe resolution strategy:",
                [
                    "Retry pull (rebase)",
                    "Retry pull (merge)",
                    "Cancel",
                ],
            )
            if choice and choice != "Cancel":
                try:
                    if "rebase" in choice:
                        out_holder3: dict[str, str] = {"out": ""}

                        def work3():
                            out_holder3["out"] = self.git.pull_rebase()

                        self._run_with_busy(work3, "Pulling (rebase)…")
                        self._log(f"Pull successful:\n{out_holder3['out']}")
                    else:
                        out_holder4: dict[str, str] = {"out": ""}

                        def work4():
                            out_holder4["out"] = self.git.pull_merge()

                        self._run_with_busy(work4, "Pulling (merge)…")
                        self._log(f"Pull successful:\n{out_holder4['out']}")
                    wx.MessageBox("Pull completed successfully.", "KiGit", wx.OK | wx.ICON_INFORMATION)
                    self.refresh()
                    return
                except Exception as exc2:
                    wx.MessageBox(f"Pull failed:\n{exc2}", "KiGit Error", wx.OK | wx.ICON_ERROR)
                    return

            wx.MessageBox(f"Pull failed:\n{exc}", "KiGit Error", wx.OK | wx.ICON_ERROR)
