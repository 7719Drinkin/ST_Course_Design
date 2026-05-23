"""Agent interaction layer — AI model orchestration, LLM prompting, and
multi-agent collaboration.

This package is intentionally isolated from `app/`. All functions it exposes
are callable without an HTTP context. `app/` modules consume it through
interfaces defined here, never depending on its internal implementation.
"""
