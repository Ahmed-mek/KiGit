from __future__ import annotations

from typing import Optional

from .git_handler import GitHandler
from .kicad_cli import KiCadCli, KiCadCliNotFound
from .ui import CommitOptions


def smart_commit(
    handler: GitHandler,
    options: CommitOptions,
    *,
    board_file: Optional[str] = None,
    schematic_file: Optional[str] = None,
) -> str:
    """
    Performs:
      - optional DRC guard (future)
      - optional exports (BOM/PDF) via kicad-cli when available
      - git add + commit
    """
    notes: list[str] = []
    cli = None
    if options.auto_export or options.run_drc_guard:
        try:
            cli = KiCadCli.detect()
        except KiCadCliNotFound:
            cli = None
            if options.auto_export:
                notes.append("Auto-export skipped (kicad-cli not found)")
            if options.run_drc_guard:
                notes.append("DRC guard skipped (kicad-cli not found)")

    if options.run_drc_guard and cli is not None:
        if not board_file:
            raise RuntimeError("DRC guard requires a saved .kicad_pcb board file")
        from pathlib import Path

        pdir = Path(handler.project_dir)
        report_path = pdir / "git-exports" / "drc_report.txt"
        ok = cli.run_pcb_drc_report(board_file, str(report_path))
        if not ok:
            raise RuntimeError(f"DRC violations found. See: {report_path}")

    if options.auto_export and cli is not None:
        try:
            if not schematic_file:
                notes.append("No schematic file found (PDF/BOM skipped)")
            if not board_file:
                notes.append("No board file found (PCB layer SVG skipped)")
            cli.export_artifacts(
                project_dir=handler.project_dir,
                schematic_file=schematic_file,
                board_file=board_file,
                export_pdf=bool(getattr(options, "export_pdf", True)),
                export_bom=bool(getattr(options, "export_bom", True)),
                export_layers_svg=bool(getattr(options, "export_layers_svg", True)),
                export_gerbers=bool(getattr(options, "export_gerbers", True)),
                export_drill=bool(getattr(options, "export_drill", True)),
                export_images=bool(getattr(options, "export_images", True)),
                export_step=bool(getattr(options, "export_step", False)),
                export_glb=bool(getattr(options, "export_glb", False)),
            )
        except Exception as exc:
            notes.append(f"Auto-export failed ({exc})")

    handler.add_all()
    commit_hash = handler.commit(options.message)
    if not commit_hash:
        msg = "No changes to commit"
    else:
        msg = f"Committed: {commit_hash}"
    if notes:
        msg = msg + "\n\n" + "\n".join(notes)
    return msg
