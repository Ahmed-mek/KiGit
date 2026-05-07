from __future__ import annotations

# KiCad discovers SWIG action plugins by importing Python modules/packages in its plugin paths.
# Keep the import-time side effects minimal: instantiate/register the action plugin.
from .kigit_action import KiGitAction

KiGitAction().register()

