from __future__ import annotations

from pathlib import Path


class PromptRegistry:
    """维护 prompt 名称到 markdown 模板文件的映射。"""

    TEMPLATE_FILES = {
        "requirement_parse": "requirement_parse.md",
        "requirement_analysis": "requirement_analysis.md",
        "risk_analysis": "risk_analysis.md",
        "coverage_identification": "coverage_identification.md",
        "technique_assignment": "technique_assignment.md",
        "test_design_spec": "test_design_spec.md",
        "test_case_draft": "test_case_draft.md",
        "fsm_modeling": "fsm_modeling.md",
    }

    def __init__(self, template_dir: Path | None = None) -> None:
        """默认使用当前 prompts/templates 目录。"""

        self.template_dir = template_dir or Path(__file__).resolve().parent / "templates"

    def get_template_path(self, name: str) -> Path:
        """根据逻辑名称返回模板路径，并校验名称和文件存在性。"""

        if name not in self.TEMPLATE_FILES:
            raise KeyError(f"Unknown prompt name: {name}")

        path = self.template_dir / self.TEMPLATE_FILES[name]
        if not path.exists():
            raise FileNotFoundError(f"Prompt template file not found: {path}")
        return path
