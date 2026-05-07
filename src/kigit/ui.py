from __future__ import annotations

from dataclasses import dataclass


def _wx():
    import wx  # type: ignore

    return wx


@dataclass(frozen=True)
class CommitOptions:
    message: str
    auto_export: bool = True
    run_drc_guard: bool = False


def prompt_commit_options(parent, default_message: str) -> CommitOptions:
    wx = _wx()

    class CommitDialog(wx.Dialog):
        def __init__(self):
            super().__init__(parent, title="KiGit Commit")

            msg_label = wx.StaticText(self, label="Commit message")
            self.msg = wx.TextCtrl(self, value=default_message, style=wx.TE_MULTILINE)

            self.chk_export = wx.CheckBox(self, label="Auto-export (BOM, PDF, Gerbers, drill, PCB images) when possible")
            self.chk_export.SetValue(True)

            self.chk_drc = wx.CheckBox(self, label="DRC guard (block commit on DRC violations)")
            self.chk_drc.SetValue(False)

            info = wx.StaticText(
                self,
                label="Exports are written to a `git-exports/` folder in the project directory. Auto-export and DRC guard require kicad-cli.",
            )

            btns = self.CreateButtonSizer(wx.OK | wx.CANCEL)

            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(msg_label, 0, wx.ALL, 8)
            sizer.Add(self.msg, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
            sizer.Add(self.chk_export, 0, wx.ALL, 8)
            sizer.Add(self.chk_drc, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
            sizer.Add(info, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
            if btns:
                sizer.Add(btns, 0, wx.EXPAND | wx.ALL, 8)

            self.SetSizerAndFit(sizer)
            self.SetMinSize((520, 240))

    dlg = CommitDialog()
    try:
        if dlg.ShowModal() != wx.ID_OK:
            raise RuntimeError("Cancelled")
        msg = (dlg.msg.GetValue() or "").strip()
        if not msg:
            raise RuntimeError("Commit message is required")
        return CommitOptions(
            message=msg,
            auto_export=bool(dlg.chk_export.GetValue()),
            run_drc_guard=bool(dlg.chk_drc.GetValue()),
        )
    finally:
        dlg.Destroy()


def run_kigit_flow(project_dir: str, board_file: str) -> None:
    """
    UI entry point. Keep UI thin; delegate to helpers.
    """
    wx = _wx()

    from .git_handler import GitHandler
    from .gitops import smart_commit
    from .project import discover_project_files

    files = discover_project_files(project_dir, board_file=board_file)
    handler = GitHandler(files.project_dir)

    if not handler.is_git_repo():
        resp = wx.MessageBox(
            "This project is not a Git repository. Initialize one now?",
            "KiGit",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )
        if resp != wx.YES:
            return
        handler.init()

        resp_ig = wx.MessageBox(
            "Create a KiCad-friendly .gitignore now?",
            "KiGit",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )
        if resp_ig == wx.YES:
            from pathlib import Path

            template_path = Path(__file__).resolve().parent / "gitignore_template.txt"
            template_text = template_path.read_text(encoding="utf-8")
            handler.ensure_gitignore(template_text)

    default_msg = "KiCad: update design"
    if files.board_file:
        from pathlib import Path

        default_msg = f"KiCad: update {Path(files.board_file).stem}"

    options = prompt_commit_options(None, default_message=default_msg)
    result = smart_commit(
        handler,
        options,
        board_file=files.board_file,
        schematic_file=files.schematic_file,
    )
    wx.MessageBox(result, "KiGit", wx.OK | wx.ICON_INFORMATION)
