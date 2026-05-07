from __future__ import annotations

# KiCad discovers SWIG action plugins by importing Python modules/packages in its plugin paths.
# Avoid import-time side effects outside KiCad (unit tests, tooling, scripts).
try:
    import pcbnew  # type: ignore  # noqa: F401

    _IN_KICAD = True
except Exception:
    _IN_KICAD = False

if _IN_KICAD:
    from .kigit_action import KiGitAction

    KiGitAction().register()
