"""Pytest bootstrap: make the backend modules importable from any cwd.

Keeps `import nlp_engine`, `import tax_engine`, etc. working whether pytest
is launched from backend/ or from the repository root.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
