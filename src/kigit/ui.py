from __future__ import annotations

from dataclasses import dataclass

# The real UI is implemented in `ui_dialog.py`.
try:
    from .ui_dialog import KiGitDialog as _KiGitDialog
except Exception:
    from ui_dialog import KiGitDialog as _KiGitDialog  # type: ignore


def _wx():
    import wx  # type: ignore

    return wx


@dataclass(frozen=True)
class CommitOptions:
    message: str
    auto_export: bool = True
    run_drc_guard: bool = False
    smart_footer: bool = True


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
    dlg = _KiGitDialog(project_dir, board_file)
    try:
        dlg.ShowModal()
    finally:
        dlg.Destroy()
