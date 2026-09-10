import os
import sys

# Ensure repository root is in sys.path so 'backend.app...' package imports resolve
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from backend.app.main import app  # noqa: F401
