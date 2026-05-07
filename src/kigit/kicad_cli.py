from __future__ import annotations

import os
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


class KiCadCliNotFound(RuntimeError):
    pass


class KiCadCliError(RuntimeError):
    pass


@dataclass(frozen=True)
class KiCadCliResult:
    argv: list[str]
    cwd: str
    returncode: int
    stdout: str
    stderr: str


class KiCadCli:
    def __init__(self, exe: str = "kicad-cli", timeout_s: int = 120) -> None:
        self._exe = exe
        self._timeout_s = timeout_s

    @staticmethod
    def detect() -> "KiCadCli":
        exe = shutil.which("kicad-cli")
        if not exe:
            raise KiCadCliNotFound("kicad-cli not found in PATH")
        return KiCadCli(exe=exe)

    def _run(self, args: Iterable[str], cwd: Optional[str] = None, *, allow_nonzero: bool = False) -> KiCadCliResult:
        argv = [self._exe, *list(args)]
        run_cwd = cwd or os.getcwd()
        try:
            cp = subprocess.run(
                argv,
                cwd=run_cwd,
                text=True,
                capture_output=True,
                timeout=self._timeout_s,
                check=False,
            )
        except FileNotFoundError as e:
            raise KiCadCliNotFound("kicad-cli not found. Install KiCad 7+ and ensure kicad-cli is in PATH.") from e
        except subprocess.TimeoutExpired as e:
            raise KiCadCliError(f"kicad-cli timed out: {' '.join(argv)}") from e

        res = KiCadCliResult(
            argv=argv,
            cwd=run_cwd,
            returncode=cp.returncode,
            stdout=cp.stdout or "",
            stderr=cp.stderr or "",
        )
        if res.returncode != 0 and not allow_nonzero:
            msg = res.stderr.strip() or res.stdout.strip() or f"kicad-cli failed ({res.returncode})"
            raise KiCadCliError(msg)
        return res

    def export_project_artifacts(self, project_dir: str) -> None:
        """
        Back-compat helper: export artifacts by auto-discovering files inside project_dir.
        Prefer using export_artifacts() with explicit file paths when available.
        """
        pdir = Path(project_dir)
        sch_files = sorted(pdir.glob("*.kicad_sch"))
        pcb_files = sorted(pdir.glob("*.kicad_pcb"))
        self.export_artifacts(
            project_dir=project_dir,
            schematic_file=str(sch_files[0]) if sch_files else None,
            board_file=str(pcb_files[0]) if pcb_files else None,
        )

    def export_artifacts(
        self,
        *,
        project_dir: str,
        schematic_file: Optional[str],
        board_file: Optional[str],
        revision: Optional[str] = None,
        clean_output: bool = True,
        export_pdf: bool = True,
        export_bom: bool = True,
        export_layers_svg: bool = True,
        export_gerbers: bool = True,
        export_drill: bool = True,
        export_images: bool = True,
        export_step: bool = False,
        export_glb: bool = False,
    ) -> None:
        """
        Phase 2+: Auto-export artifacts into `git-exports/`.
        When revision is provided, exports go to `git-exports/<REV>/`.
        - schematic_file: root schematic (*.kicad_sch)
        - board_file: board (*.kicad_pcb)
        """
        pdir = Path(project_dir)
        base_dir = pdir / "git-exports"
        out_root = base_dir / revision if revision else base_dir

        if clean_output and out_root.exists():
            # Only ever delete within the project `git-exports/` tree.
            try:
                out_root_resolved = str(out_root.resolve())
                base_resolved = str(base_dir.resolve())
                if out_root_resolved == base_resolved or out_root_resolved.startswith(base_resolved + os.sep):
                    shutil.rmtree(out_root)
            except Exception:
                # If safety checks fail, fall back to best-effort cleanup of known subfolders.
                for name in ("schematic", "pcb", "manufacturing", "3d", "reports"):
                    try:
                        shutil.rmtree(out_root / name)
                    except Exception:
                        pass

        out_root.mkdir(parents=True, exist_ok=True)
        sch_dir = out_root / "schematic"
        pcb_dir = out_root / "pcb"
        mfg_dir = out_root / "manufacturing"
        three_d_dir = out_root / "3d"
        reports_dir = out_root / "reports"

        sch_dir.mkdir(parents=True, exist_ok=True)
        pcb_dir.mkdir(parents=True, exist_ok=True)
        mfg_dir.mkdir(parents=True, exist_ok=True)
        three_d_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)

        def _rev_suffix() -> str:
            return f"_{revision}" if revision else ""

        def _board_stem() -> str:
            try:
                return Path(board_file).stem if board_file else "board"
            except Exception:
                return "board"

        def _sch_stem() -> str:
            try:
                return Path(schematic_file).stem if schematic_file else "schematic"
            except Exception:
                return "schematic"

        if schematic_file and export_pdf:
            self.export_schematic_pdf(schematic_file, str(sch_dir / f"{_sch_stem()}_schematic{_rev_suffix()}.pdf"))
        if schematic_file and export_bom:
            self.export_bom_csv(schematic_file, str(sch_dir / f"{_sch_stem()}_bom{_rev_suffix()}.csv"))

        if board_file:
            # Prep for Phase 3 (visual diff): plot key layers to SVG.
            if export_layers_svg:
                self.export_pcb_layers_svg(
                    board_file,
                    str(pcb_dir / f"layers_svg{_rev_suffix()}"),
                    layers=["F.Cu", "B.Cu", "F.SilkS", "B.SilkS", "Edge.Cuts"],
                )

            # Phase 2 requested outputs: Gerbers + drill + a quick visual render.
            if export_gerbers:
                self.export_gerbers(board_file, str(mfg_dir / f"gerbers{_rev_suffix()}"))
            if export_drill:
                self.export_drill(board_file, str(mfg_dir / f"drill{_rev_suffix()}"))
            if export_images:
                self.render_pcb_image(board_file, str(pcb_dir / f"{_board_stem()}_top{_rev_suffix()}.png"), side="top")
                self.render_pcb_image(board_file, str(pcb_dir / f"{_board_stem()}_bottom{_rev_suffix()}.png"), side="bottom")
            if export_step:
                self.export_step(board_file, str(three_d_dir / f"{_board_stem()}{_rev_suffix()}.step"))
            if export_glb:
                self.export_glb(board_file, str(three_d_dir / f"{_board_stem()}{_rev_suffix()}.glb"))

            # Convenience: create a fab ZIP containing gerbers + drill (when present).
            try:
                zip_name = f"{_board_stem()}_fab{_rev_suffix()}.zip"
                zip_path = out_root / zip_name
                with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for p in sorted(mfg_dir.rglob("*")):
                        if p.is_dir():
                            continue
                        arc = p.relative_to(out_root).as_posix()
                        zf.write(p, arcname=arc)
            except Exception:
                pass

    def export_schematic_pdf(self, schematic_file: str, out_pdf: str) -> None:
        self._run(["sch", "export", "pdf", "--output", out_pdf, schematic_file])

    def export_bom_csv(self, schematic_file: str, out_csv: str) -> None:
        self._run(["sch", "export", "bom", "--output", out_csv, schematic_file])

    def export_pcb_layers_svg(self, board_file: str, out_dir: str, *, layers: list[str]) -> None:
        layer_list = ",".join(layers)
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        # Ensure output is treated as a directory (multi-file mode).
        self._run(["pcb", "export", "svg", "--mode-multi", "--output", out_dir, "--layers", layer_list, board_file])

    def export_gerbers(self, board_file: str, out_dir: str) -> None:
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        # Prefer the plot settings stored in the board when available.
        self._run(["pcb", "export", "gerbers", "--output", out_dir, "--board-plot-params", board_file])

    def export_drill(self, board_file: str, out_dir: str) -> None:
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        # Defaults to Excellon; generate drill-map + report for convenience.
        self._run(
            [
                "pcb",
                "export",
                "drill",
                "--output",
                out_dir,
                "--generate-map",
                "--generate-report",
                board_file,
            ]
        )

    def export_step(self, board_file: str, out_file: str) -> None:
        Path(out_file).parent.mkdir(parents=True, exist_ok=True)
        self._run(["pcb", "export", "step", "--output", out_file, "--force", board_file])

    def export_glb(self, board_file: str, out_file: str) -> None:
        Path(out_file).parent.mkdir(parents=True, exist_ok=True)
        self._run(["pcb", "export", "glb", "--output", out_file, "--force", board_file])

    def render_pcb_image(self, board_file: str, out_file: str, *, side: str) -> None:
        Path(out_file).parent.mkdir(parents=True, exist_ok=True)
        self._run(
            [
                "pcb",
                "render",
                "--output",
                out_file,
                "--side",
                side,
                "--width",
                "1600",
                "--height",
                "900",
                board_file,
            ]
        )

    def run_pcb_drc_report(self, board_file: str, out_report: str) -> bool:
        """
        Returns True if DRC passes (no violations), False if violations exist.
        Always writes a report file (when possible).
        """
        out_path = Path(out_report)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        res = self._run(
            [
                "pcb",
                "drc",
                "--format",
                "report",
                "--exit-code-violations",
                "--output",
                str(out_path),
                board_file,
            ],
            allow_nonzero=True,
        )
        return res.returncode == 0
