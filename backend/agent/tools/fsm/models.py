from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


FSM_TECHNIQUE = "FSM"
FSM_STANDARD_REF = "ISTQB state transition testing / finite state machine testing"


@dataclass(frozen=True)
class FSMState:
    """A stable, serializable finite-state-machine state."""

    state_id: str
    name: str
    description: str = ""
    is_initial: bool = False
    is_terminal: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_id": self.state_id,
            "name": self.name,
            "description": self.description,
            "is_initial": self.is_initial,
            "is_terminal": self.is_terminal,
        }


@dataclass(frozen=True)
class FSMTransition:
    """A deterministic transition between two FSM states."""

    transition_id: str
    source_state: str
    target_state: str
    event: str
    condition: str
    action: str
    requirement_id: str
    coverage_item_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "source_state": self.source_state,
            "target_state": self.target_state,
            "event": self.event,
            "condition": self.condition,
            "action": self.action,
            "requirement_id": self.requirement_id,
            "coverage_item_id": self.coverage_item_id,
        }


@dataclass(frozen=True)
class FSMCoverageItem:
    """Coverage target for states, transitions, or paths in an FSM model."""

    coverage_item_id: str
    requirement_id: str
    description: str
    strategy: str = "ALL_TRANSITIONS"
    target_type: str = "transition"
    target_id: str = ""
    covered_states: list[str] = field(default_factory=list)
    covered_transitions: list[str] = field(default_factory=list)
    coverage_type: str = "transition"
    technique: str = field(default=FSM_TECHNIQUE, init=False)
    standard_ref: str = FSM_STANDARD_REF

    def to_dict(self) -> dict[str, Any]:
        return {
            "coverage_item_id": self.coverage_item_id,
            "requirement_id": self.requirement_id,
            "strategy": self.strategy,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "description": self.description,
            "covered_states": list(self.covered_states),
            "covered_transitions": list(self.covered_transitions),
            "coverage_type": self.coverage_type,
            "technique": self.technique,
            "standard_ref": self.standard_ref,
        }


@dataclass(frozen=True)
class FSMModel:
    """A parsed finite-state-machine model with stable IDs."""

    model_id: str
    requirement_id: str
    states: list[FSMState]
    transitions: list[FSMTransition]
    initial_state: str
    name: str = "Finite State Machine"
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "requirement_id": self.requirement_id,
            "name": self.name,
            "description": self.description,
            "initial_state": self.initial_state,
            "states": [state.to_dict() for state in self.states],
            "transitions": [transition.to_dict() for transition in self.transitions],
        }


@dataclass(frozen=True)
class FSMTestCase:
    """A test case generated from one or more FSM transitions."""

    test_id: str
    requirement_id: str
    coverage_item_ids: list[str]
    title: str
    preconditions: list[str]
    steps: list[str]
    expected_results: list[str]
    covered_states: list[str]
    covered_transitions: list[str]
    technique: str = field(default=FSM_TECHNIQUE, init=False)
    status: str = "Draft"
    standard_ref: str = FSM_STANDARD_REF

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_id,
            "requirement_id": self.requirement_id,
            "coverage_item_ids": list(self.coverage_item_ids),
            "title": self.title,
            "preconditions": list(self.preconditions),
            "steps": list(self.steps),
            "expected_results": list(self.expected_results),
            "covered_states": list(self.covered_states),
            "covered_transitions": list(self.covered_transitions),
            "technique": self.technique,
            "status": self.status,
            "standard_ref": self.standard_ref,
        }


@dataclass(frozen=True)
class FSMGenerationResult:
    """Complete deterministic FSM generation output."""

    success: bool
    model: FSMModel
    coverage_items: list[FSMCoverageItem] = field(default_factory=list)
    test_cases: list[FSMTestCase] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "model": self.model.to_dict(),
            "coverage_items": [item.to_dict() for item in self.coverage_items],
            "test_cases": [case.to_dict() for case in self.test_cases],
            "metadata": dict(self.metadata),
            "errors": list(self.errors),
        }
