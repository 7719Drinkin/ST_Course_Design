"""Test generation, FSM & oracle routes (/generate, /fsm, /oracle)."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["generation"])
