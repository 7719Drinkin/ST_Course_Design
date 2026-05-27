from __future__ import annotations


class StageName:
    """Public stage names used by runner, pipeline, and API adapters."""

    INPUT_VALIDATION = "input_validation"
    PARSE_REQUIREMENTS = "parse_requirements"
    ANALYZE_RISK = "analyze_risk"
    IDENTIFY_COVERAGE = "identify_coverage"
    ASSIGN_STRATEGY = "assign_strategy"
    GENERATE_TESTS = "generate_tests"
    GENERATE_FSM = "generate_fsm"
    FINAL_VALIDATION = "final_validation"
    AGENT_RUNNER = "agent_runner"


STAGE_TITLES = {
    StageName.PARSE_REQUIREMENTS: "Requirement parsing",
    StageName.ANALYZE_RISK: "Risk analysis",
    StageName.IDENTIFY_COVERAGE: "Coverage identification",
    StageName.ASSIGN_STRATEGY: "Technique assignment",
    StageName.GENERATE_TESTS: "Test design and case generation",
    StageName.GENERATE_FSM: "FSM modeling",
    StageName.FINAL_VALIDATION: "Final validation",
}
