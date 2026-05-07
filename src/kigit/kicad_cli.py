from __future__ import annotations

import os
import shutil
import subprocess
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

    def export_artifacts(self, *, project_dir: str, schematic_file: Optional[str], board_file: Optional[str]) -> None:
        """
        Phase 2: Auto-export BOM/PDF (and optional layer SVG) into `exports/`.
        - schematic_file: root schematic (*.kicad_sch)
        - board_file: board (*.kicad_pcb)
        """
        pdir = Path(project_dir)
        out_dir = pdir / "exports"
        out_dir.mkdir(parents=True, exist_ok=True)

        if schematic_file:
            self.export_schematic_pdf(schematic_file, str(out_dir / "schematic.pdf"))
            self.export_bom_csv(schematic_file, str(out_dir / "bom.csv"))

        if board_file:
            # Prep for Phase 3 (visual diff): plot key layers to SVG.
            self.export_pcb_layers_svg(
                board_file,
                str(out_dir / "layers_svg"),
                layers=["F.Cu", "B.Cu", "F.SilkS", "B.SilkS", "Edge.Cuts"],
            )

            # Phase 2 requested outputs: Gerbers + drill + a quick visual render.
            self.export_gerbers(board_file, str(out_dir / "gerbers"))
            self.export_drill(board_file, str(out_dir / "drill"))
            self.render_pcb_image(board_file, str(out_dir / "pcb_top.png"), side="top")
            self.render_pcb_image(board_file, str(out_dir / "pcb_bottom.png"), side="bottom")

    def export_schematic_pdf(self, schematic_file: str, out_pdf: str) -> None:
        self._run(["sch", "export", "pdf", "--output", out_pdf, schematic_file])

    def export_bom_csv(self, schematic_file: str, out_csv: str) -> None:
        self._run(["sch", "export", "bom", "--output", out_csv, schematic_file])

    def export_pcb_layers_svg(self, board_file: str, out_dir: str, *, layers: list[str]) -> None:
        layer_list = ",".join(layers)
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        self._run(["pcb", "export", "svg", "--output", out_dir, "--layers", layer_list, board_file])

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
