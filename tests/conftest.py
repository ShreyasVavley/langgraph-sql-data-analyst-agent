"""
tests/conftest.py
=============================================================================
Pytest configuration ensuring workspace root is on sys.path.
=============================================================================
"""

import sys
import os

workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)
