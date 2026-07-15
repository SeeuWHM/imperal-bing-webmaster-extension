"""Bing Webmaster Connector — entry point with module hot-reload."""
from __future__ import annotations

import sys
import os

_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _dir)

for _m in list(sys.modules):
    if _m in ("app", "bing_accounts", "bing_api", "params", "response_models",
              "skeleton", "handlers_accounts", "handlers_data",
              "panels", "panels_workspace"):
        del sys.modules[_m]

from app import ext, chat  # noqa: E402, F401

import skeleton            # noqa: E402, F401
import handlers_accounts   # noqa: E402, F401
import handlers_data       # noqa: E402, F401
import panels              # noqa: E402, F401
import panels_workspace    # noqa: E402, F401

# Multiple extensions share one worker process and each inserts its own
# directory at sys.path[0] on load. Leaving it there after our imports are
# done means a LATER extension's plain `import accounts` (or any other
# same-named top-level module) can resolve to THIS extension's file instead
# of its own. Once our modules are cached in sys.modules under their bare
# names, the directory is no longer needed on sys.path — remove it so it
# can't leak into the next extension's load (this is exactly the bug that
# hit gsc-connector and se-ranking-connector after this extension deployed).
if _dir in sys.path:
    sys.path.remove(_dir)
