"""Test-only sys.path bootstrap for ada-service's test suite.

Mirrors the bootstrap main.py does at the top of the file: `domain`/`infra`
live one directory up (agent-sa/), so they need to be on sys.path alongside
ada-service/ itself (for `features.*`, ADA's own vertical slices).

Why this suite is run separately (`pytest ada-service/tests`, not folded
into the root `pytest` invocation): ada-service/features/ and the top-level
agent-sa/features/ (AIA's slice) are two different directories that both
declare a top-level `features` package. Python's sys.modules only ever binds
one directory to that dotted name per process. Two separate pytest
processes each import only their own `features` — no collision, same as
agent.py and ada-service/main.py already being two separate deployments.
See pytest.ini for the corresponding testpaths exclusion.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ada_service_dir = Path(__file__).resolve().parent
_agent_sa_dir = _ada_service_dir.parent

for _p in (_ada_service_dir, _agent_sa_dir):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
