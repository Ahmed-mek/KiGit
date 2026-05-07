from __future__ import annotations

__all__ = []

# KiCad discovers SWIG action plugins by importing Python modules/packages in its plugin paths.
# Keep import-time side effects safe: only register when running inside KiCad.
try:
    import pcbnew  # type: ignore

    pgm = getattr(pcbnew, "PgmOrNull", None)
    in_kicad = bool(pgm and pgm() is not None)
except Exception:
    in_kicad = False

if in_kicad:
    try:
        from .kigit_action import KiGitAction

        KiGitAction().register()
    except Exception:
        # Avoid crashing KiCad plugin loader on import; errors will show when user runs the plugin.
        pass
