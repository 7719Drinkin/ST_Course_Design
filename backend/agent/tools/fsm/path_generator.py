from __future__ import annotations

from collections import deque

from .models import FSMModel, FSMTransition


def generate_transition_paths(model: FSMModel, max_depth: int = 6) -> list[list[FSMTransition]]:
    """Generate deterministic transition paths from the model initial state.

    The BFS explores paths in transition_id order, records a path whenever it
    covers at least one previously uncovered transition, and avoids repeating a
    transition inside the same path to prevent loop explosion. Unreachable
    transitions are intentionally omitted so coverage analysis can report them
    as gaps.
    """

    if max_depth <= 0:
        return []

    adjacency = _build_adjacency(model)
    target_transition_ids = {transition.transition_id for transition in model.transitions}
    covered_transition_ids: set[str] = set()
    paths: list[list[FSMTransition]] = []
    queue: deque[tuple[str, list[FSMTransition]]] = deque([(model.initial_state, [])])
    visited: set[tuple[str, tuple[str, ...]]] = {(model.initial_state, ())}

    while queue and covered_transition_ids != target_transition_ids:
        current_state, path = queue.popleft()
        path_transition_ids = tuple(transition.transition_id for transition in path)

        if path:
            newly_covered = set(path_transition_ids) - covered_transition_ids
            if newly_covered:
                paths.append(path)
                covered_transition_ids.update(newly_covered)
                if covered_transition_ids == target_transition_ids:
                    break

        if len(path) >= max_depth:
            continue

        used_in_path = set(path_transition_ids)
        for transition in adjacency.get(current_state, []):
            if transition.transition_id in used_in_path:
                continue
            next_path = path + [transition]
            next_signature = (
                transition.target_state,
                tuple(item.transition_id for item in next_path),
            )
            if next_signature in visited:
                continue
            visited.add(next_signature)
            queue.append((transition.target_state, next_path))

    return paths


def _build_adjacency(model: FSMModel) -> dict[str, list[FSMTransition]]:
    adjacency: dict[str, list[FSMTransition]] = {}
    for transition in sorted(model.transitions, key=lambda item: item.transition_id):
        adjacency.setdefault(transition.source_state, []).append(transition)
    return adjacency
