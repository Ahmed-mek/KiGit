from __future__ import annotations

__all__ = []

# KiCad discovers SWIG action plugins by importing Python modules/packages in its plugin paths.
# Keep import-time side effects safe: only register when running inside KiCad.
try:
    import pcbnew  # type: ignore
    in_kicad = True
except Exception:
    in_kicad = False

if in_kicad:
    try:
        try:
            from .kigit_action import KiGitAction
        except Exception:
            from kigit_action import KiGitAction  # type: ignore

        KiGitAction().register()
    except Exception:
        # Avoid crashing KiCad plugin loader on import; errors will show when user runs the plugin.
        pass
