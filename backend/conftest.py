"""Pytest bootstrap: make the backend modules importable from any cwd.

Keeps `import nlp_engine`, `import tax_engine`, etc. working whether pytest
is launched from backend/ or from the repository root.
"""
import os, sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(autouse=True)
def _reset_rate_limiter_state():
    """Sprint 3 Step B: isolate the shared rate limiter between tests.

    The hardening edge rate-limits state-changing endpoints per client IP
    with an in-memory limiter on the module-level app. The whole suite
    shares one TestClient identity ("testclient"), so the ~70 /chat calls
    spread across test modules would trip the 30/min production limit —
    an infrastructure artifact, not behavior any test exercises (the
    largest single test makes 5 /chat calls; the limiter itself is covered
    by test_hardening.py with a dedicated app + explicit env knobs).
    Resetting around each test keeps every existing test's request budget
    fresh without touching any test body.
    """
    yield
    previous_cwd = os.getcwd()
    os.chdir(BACKEND_DIR)  # bind main's relative paths exactly like the API fixtures do
    try:
        import main as main_module

        limiter = getattr(main_module.app.state, "rate_limiter", None)
        if limiter is not None:
            limiter.reset()
    finally:
        os.chdir(previous_cwd)
