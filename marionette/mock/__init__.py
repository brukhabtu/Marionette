"""Dockerless / LLM-free mocks that exercise the real DefaultAgent loop.

The mock environment is a real temp-dir git repo driven by a LocalEnvironment, and
the mock model is mini-swe-agent's own DeterministicModel. So a dry-run runs the
genuine agent loop, produces a genuine cumulative git diff, and exercises the
accounting/results/plot code unchanged — only Docker, the LLM, and SWE-bench
grading are stubbed.
"""
