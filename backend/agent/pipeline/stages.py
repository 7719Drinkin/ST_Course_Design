from __future__ import annotations


class StageName:
    """Public stage keys used across runner and pipeline."""

    INPUT_VALIDATION = "input_validation"
    PARSE_REQUIREMENTS = "parse_requirements"
    ANALYZE_RISK = "analyze_risk"
    IDENTIFY_COVERAGE = "identify_coverage"
    ASSIGN_STRATEGY = "assign_strategy"
    GENERATE_TESTS = "generate_tests"
    GENERATE_FSM = "generate_fsm"
    GENERATE_ORACLE = "generate_oracle"
    FINAL_VALIDATION = "final_validation"
    AGENT_RUNNER = "agent_runner"


STAGE_TITLES = {
    StageName.INPUT_VALIDATION: "输入校验",
    StageName.PARSE_REQUIREMENTS: "需求解析",
    StageName.ANALYZE_RISK: "风险分析",
    StageName.IDENTIFY_COVERAGE: "覆盖目标识别",
    StageName.ASSIGN_STRATEGY: "测试技术分配",
    StageName.GENERATE_TESTS: "测试设计与用例生成",
    StageName.GENERATE_FSM: "FSM 建模",
    StageName.GENERATE_ORACLE: "Oracle 预期结果生成",
    StageName.FINAL_VALIDATION: "最终校验",
    StageName.AGENT_RUNNER: "流程编排",
}
