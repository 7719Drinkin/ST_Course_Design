"""Test generation, FSM & oracle routes (/generate, /fsm, /oracle)."""


from fastapi import APIRouter

router = APIRouter(tags=["generation"])
