from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ProjectFiles:
    project_dir: str
    board_file: Optional[str]
    schematic_file: Optional[str]
    project_file: Optional[str]


def discover_project_files(project_dir: str, *, board_file: Optional[str] = None) -> ProjectFiles:
    """
    Best-effort discovery for KiCad project artifacts inside a directory.

    Strategy:
    - If board_file is provided, prefer matching schematic by stem.
    - Otherwise, pick the only *.kicad_pcb / *.kicad_sch when unambiguous.
    - Project file is optional (*.kicad_pro).
    """
    pdir = Path(project_dir).resolve()

    board_path = Path(board_file).resolve() if board_file else None
    if board_path and board_path.parent != pdir:
        # In practice KiCad board is inside project_dir; keep it safe if caller passed a different path.
        pdir = board_path.parent

    pcb_files = sorted(pdir.glob("*.kicad_pcb"))
    sch_files = sorted(pdir.glob("*.kicad_sch"))
    pro_files = sorted(pdir.glob("*.kicad_pro"))

    chosen_board: Optional[Path] = None
    if board_path and board_path.suffix == ".kicad_pcb" and board_path.exists():
        chosen_board = board_path
    elif len(pcb_files) == 1:
        chosen_board = pcb_files[0]

    chosen_sch: Optional[Path] = None
    if chosen_board is not None:
        candidate = chosen_board.with_suffix(".kicad_sch")
        if candidate.exists():
            chosen_sch = candidate
    if chosen_sch is None and len(sch_files) == 1:
        chosen_sch = sch_files[0]

    chosen_pro: Optional[Path] = None
    if chosen_board is not None:
        candidate = chosen_board.with_suffix(".kicad_pro")
        if candidate.exists():
            chosen_pro = candidate
    if chosen_pro is None and len(pro_files) == 1:
        chosen_pro = pro_files[0]

    return ProjectFiles(
        project_dir=str(pdir),
        board_file=str(chosen_board) if chosen_board else None,
        schematic_file=str(chosen_sch) if chosen_sch else None,
        project_file=str(chosen_pro) if chosen_pro else None,
    )

