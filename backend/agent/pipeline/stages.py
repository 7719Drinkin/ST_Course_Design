from __future__ import annotations


class StageName:
    """对外暴露的阶段名统一放在这里，避免不同入口各写一套字符串。"""

    INPUT_VALIDATION = "input_validation"
    PARSE_REQUIREMENTS = "parse_requirements"
    ANALYZE_RISK = "analyze_risk"
    IDENTIFY_COVERAGE = "identify_coverage"
    ASSIGN_STRATEGY = "assign_strategy"
    GENERATE_TESTS = "generate_tests"
    FINAL_VALIDATION = "final_validation"
    AGENT_RUNNER = "agent_runner"


STAGE_TITLES = {
    StageName.PARSE_REQUIREMENTS: "需求解析",
    StageName.ANALYZE_RISK: "风险分析",
    StageName.IDENTIFY_COVERAGE: "覆盖目标识别",
    StageName.ASSIGN_STRATEGY: "测试技术分配",
    StageName.GENERATE_TESTS: "测试设计与用例生成",
    StageName.FINAL_VALIDATION: "最终校验",
}
