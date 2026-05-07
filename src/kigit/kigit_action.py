from __future__ import annotations

import os
import traceback
from pathlib import Path


def _in_kicad() -> bool:
    try:
        import pcbnew  # type: ignore

        pgm = getattr(pcbnew, "PgmOrNull", None)
        return bool(pgm and pgm() is not None)
    except Exception:
        return False


if _in_kicad():
    import pcbnew  # type: ignore
    import wx  # type: ignore

    from .ui import run_kigit_flow


    class KiGitAction(pcbnew.ActionPlugin):  # pragma: no cover (runs inside KiCad)
        def defaults(self) -> None:
            self.name = "KiGit"
            self.category = "Version Control"
            self.description = "Commit and automate exports for the current KiCad project"
            self.show_toolbar_button = False

            plugin_dir = Path(__file__).resolve().parent
            toolbar = plugin_dir / "toolbar.png"
            if toolbar.exists():
                self.show_toolbar_button = True
                self.icon_file_name = str(toolbar)
                dark_toolbar = plugin_dir / "toolbar_dark.png"
                if dark_toolbar.exists():
                    self.dark_icon_file_name = str(dark_toolbar)

        def Run(self) -> None:
            board = pcbnew.GetBoard()
            board_path = board.GetFileName() if board else ""
            if not board_path:
                wx.MessageBox(
                    "Save the board before running KiGit.",
                    "KiGit",
                    wx.OK | wx.ICON_WARNING,
                )
                return

            project_dir = os.path.dirname(board_path)

            consent = wx.MessageBox(
                "KiGit may create commits and export project artifacts. Continue?",
                "KiGit",
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
            )
            if consent != wx.YES:
                return

            try:
                run_kigit_flow(project_dir, board_path)
            except Exception as exc:
                details = traceback.format_exc()
                log_path = Path(project_dir) / "git-exports" / "kigit_error.txt"
                try:
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                    log_path.write_text(details, encoding="utf-8")
                except Exception:
                    log_path = Path("")
                wx.MessageBox(
                    f"KiGit failed.\n\n{exc}\n\nDetails: {log_path}" if str(log_path) else f"KiGit failed.\n\n{exc}",
                    "KiGit",
                    wx.OK | wx.ICON_ERROR,
                )

else:

    class KiGitAction:  # noqa: D401
        """Stub class for non-KiCad environments (imports, tests, tooling)."""

        def register(self) -> None:
            return
