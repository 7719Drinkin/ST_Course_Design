"""Common type aliases shared across feature modules."""

from __future__ import annotations

from typing import Literal

RiskLevel = Literal["High", "Medium", "Low"]
Technique = Literal["EP", "BVA", "DT", "FSM"]
TestCaseStatus = Literal["Draft", "Approved", "Rejected"]
Verdict = Literal["Pass", "Fail"]
OptimizeMode = Literal["risk_priority", "normal"]
