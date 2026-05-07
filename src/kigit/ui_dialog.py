from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _wx():
    import wx  # type: ignore

    return wx


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

        self.notebook = wx.Notebook(self.dlg)

        self.page_overview = wx.Panel(self.notebook)
        self.page_commit = wx.Panel(self.notebook)
        self.page_branches = wx.Panel(self.notebook)
        self.page_timeline = wx.Panel(self.notebook)

        self.notebook.AddPage(self.page_overview, "Overview")
        self.notebook.AddPage(self.page_commit, "Commit")
        self.notebook.AddPage(self.page_branches, "Branches")
        self.notebook.AddPage(self.page_timeline, "Timeline")

        self.log = wx.TextCtrl(self.dlg, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.log.SetMinSize((-1, 140))

        btn_refresh = wx.Button(self.dlg, label="Refresh")
        btn_close = wx.Button(self.dlg, label="Close")
        btn_close.Bind(wx.EVT_BUTTON, lambda evt: self.dlg.EndModal(wx.ID_OK))
        btn_refresh.Bind(wx.EVT_BUTTON, lambda evt: self.refresh())

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.Add(btn_refresh, 0, wx.ALL, 6)
        btn_sizer.AddStretchSpacer(1)
        btn_sizer.Add(btn_close, 0, wx.ALL, 6)

        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 8)
        root.Add(wx.StaticText(self.dlg, label="Log"), 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        root.Add(self.log, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        root.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        self.dlg.SetSizer(root)
        self.dlg.SetMinSize((720, 520))

        self._build_overview_tab()
        self._build_commit_tab()
        self._build_branches_tab()
        self._build_timeline_tab()

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
            label="Tip: `git-exports/` is intended to be committed (for reproducible snapshots).",
        )

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self.page_commit, label="Commit message"), 0, wx.ALL, 8)
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

        toolbar = wx.BoxSizer(wx.HORIZONTAL)
        toolbar.Add(self.chk_all_branches, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 6)
        toolbar.AddStretchSpacer(1)
        toolbar.Add(wx.StaticText(self.page_timeline, label="Max commits"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 6)
        toolbar.Add(self.spin_count, 0, wx.ALL, 6)

        self.graph_box = wx.TextCtrl(
            self.page_timeline,
            style=wx.TE_MULTILINE | wx.TE_READONLY,
        )
        self.graph_box.SetFont(wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))

        self.commits = wx.ListCtrl(self.page_timeline, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.commits.InsertColumn(0, "Hash", width=80)
        self.commits.InsertColumn(1, "Date", width=160)
        self.commits.InsertColumn(2, "Author", width=140)
        self.commits.InsertColumn(3, "Message", width=520)
        self.commits.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda evt: self._on_select_commit())

        self.details = wx.TextCtrl(self.page_timeline, style=wx.TE_MULTILINE | wx.TE_READONLY)

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

        splitter.SplitVertically(left, right, sashPosition=420)

        top.Add(toolbar, 0, wx.EXPAND)
        top.Add(btns, 0, wx.EXPAND)
        top.Add(splitter, 1, wx.EXPAND | wx.ALL, 6)
        self.page_timeline.SetSizer(top)

    def ShowModal(self) -> int:
        return self.dlg.ShowModal()

    def Destroy(self) -> None:
        self.dlg.Destroy()

    def _log(self, text: str) -> None:
        self.log.AppendText(text.rstrip() + "\n")

    def refresh(self) -> None:
        wx = self._wx
        self._log("Refreshing…")

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
        else:
            self.txt_repo_root.SetLabel("(not a git repo)")
            self.txt_branch.SetLabel("")
            self.status_box.SetValue("")

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
        )

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
            self.graph_box.SetValue("(not a git repo)")
            self.commits.DeleteAllItems()
            self.details.SetValue("")
            return

        all_branches = bool(self.chk_all_branches.GetValue())
        max_commits = int(self.spin_count.GetValue())
        try:
            self.graph_box.SetValue(self.git.log_graph(max_count=max_commits, all_branches=all_branches))
        except Exception as exc:
            self.graph_box.SetValue(f"(log error) {exc}")

        self.commits.DeleteAllItems()
        try:
            tsv = self.git.log_commits_tsv(max_count=max_commits, all_branches=all_branches)
        except Exception as exc:
            self.details.SetValue(f"(log error) {exc}")
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
            self.details.SetValue("")
            return
        try:
            self.details.SetValue(self.git.show_summary(rev))
        except Exception as exc:
            self.details.SetValue(f"(show error) {exc}")

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
        self.details.SetValue(diff_text or "(no diff)")

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
