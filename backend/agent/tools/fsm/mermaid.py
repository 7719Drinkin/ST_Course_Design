from __future__ import annotations

from .models import FSMModel


def render_mermaid(model: FSMModel) -> str:
    """Render a deterministic Mermaid state diagram for an FSM model."""

    state_names = {state.state_id: state.name.title().replace("_", " ") for state in model.states}
    lines = ["stateDiagram-v2"]
    initial_name = state_names.get(model.initial_state, model.initial_state)
    lines.append(f"    [*] --> {_node_name(initial_name)}")

    for transition in model.transitions:
        source = _node_name(state_names.get(transition.source_state, transition.source_state))
        target = _node_name(state_names.get(transition.target_state, transition.target_state))
        label = _label(transition.transition_id, transition.event, transition.condition)
        lines.append(f"    {source} --> {target} : {label}")

    terminal_state_ids = {state.state_id for state in model.states if state.is_terminal}
    for state_id in sorted(terminal_state_ids):
        state_name = _node_name(state_names.get(state_id, state_id))
        lines.append(f"    {state_name} --> [*]")

    return "\n".join(lines)


def _node_name(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value).strip("_") or "State"


def _label(transition_id: str, event: str, condition: str) -> str:
    text = f"{transition_id} {event}"
    if condition:
        text = f"{text} [{condition}]"
    return text.replace("\n", " ")
