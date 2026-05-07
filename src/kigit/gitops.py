from __future__ import annotations

from typing import Optional

try:
    from .git_handler import GitHandler
    from .kicad_cli import KiCadCli, KiCadCliNotFound
    from .ui import CommitOptions
except Exception:
    from git_handler import GitHandler  # type: ignore
    from kicad_cli import KiCadCli, KiCadCliNotFound  # type: ignore
    from ui import CommitOptions  # type: ignore


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
    revision = handler.next_revision()

    schematic_backup: Optional[str] = None
    schematic_rev_changed = False

    def _revert_schematic_rev_best_effort() -> None:
        if not schematic_file or not schematic_rev_changed or schematic_backup is None:
            return
        try:
            from pathlib import Path

            Path(schematic_file).write_text(schematic_backup, encoding="utf-8")
        except Exception:
            pass

    try:
        # Update schematic title block REV only as part of a commit flow.
        if schematic_file:
            try:
                from pathlib import Path

                p = Path(schematic_file)
                if p.exists():
                    schematic_backup = p.read_text(encoding="utf-8", errors="replace")

                try:
                    from .kicad_schematic import set_title_block_revision
                except Exception:
                    from kicad_schematic import set_title_block_revision  # type: ignore

                schematic_rev_changed = bool(set_title_block_revision(schematic_file, revision))
                if schematic_rev_changed:
                    notes.append(f"Schematic REV updated: {revision}")
            except Exception as exc:
                notes.append(f"Schematic REV update skipped ({exc})")
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
            report_path = pdir / "git-exports" / revision / "reports" / f"drc_report_{revision}.txt"
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
                    revision=revision,
                    clean_output=True,
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

        commit_msg = options.message
        footer_revision = ""

        # Always-on smart footer: append revision+date, and create a matching git tag.
        if True:
            from datetime import datetime

            footer_revision = revision
            footer_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            commit_msg = f"{commit_msg.strip()}\n\n[Revision: {footer_revision}] [Date: {footer_date}]"

        commit_hash = handler.commit(commit_msg)
        if not commit_hash:
            msg = "No changes to commit"
        else:
            msg = f"Committed: {commit_hash}"
            if footer_revision:
                try:
                    handler.create_annotated_tag(footer_revision, message=f"KiGit {footer_revision}")
                    notes.append(f"Tag created: {footer_revision}")
                except Exception as exc:
                    notes.append(f"Tag skipped ({exc})")
                msg += f" ({footer_revision})"
                # Persist last committed revision for stable export-only runs.
                try:
                    try:
                        from .settings import KiGitSettings
                    except Exception:
                        from settings import KiGitSettings  # type: ignore

                    s = KiGitSettings.load(handler.project_dir)
                    s.last_revision = footer_revision
                    s.save(handler.project_dir)
                except Exception:
                    pass
        if notes:
            msg = msg + "\n\n" + "\n".join(notes)
        return msg
    except Exception:
        _revert_schematic_rev_best_effort()
        raise
