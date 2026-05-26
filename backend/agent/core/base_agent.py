from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from ..prompts.prompt_builder import PromptBuilder
from ..tools.clients.llm_client import LLMClient
from .agent_context import AgentContext
from .agent_result import AgentResult
from .models import PromptRecord


class BaseAgent(ABC):
    """所有角色 Agent 的基类，统一管理 LLM 调用和 prompt 记录。"""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        """注入可替换的 LLMClient/PromptBuilder，便于测试和后续扩展。"""

        self.llm_client = llm_client or LLMClient()
        self.prompt_builder = prompt_builder or PromptBuilder()

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResult:
        """执行单个 Agent 步骤，并把结果写回共享上下文。"""

        raise NotImplementedError

    async def _run_json_prompt(
        self,
        prompt_name: str,
        variables: dict[str, Any],
        context: AgentContext,
        record_prompt: bool = True,
    ) -> dict[str, Any]:
        """构造 prompt、记录透明度信息、调用 LLM 并解析 JSON。

        如果首次 JSON 解析或模型调用失败，会追加一个最小 repair prompt
        再试一次。只重试一次，避免模型异常时无限循环。
        """

        prompt = self.prompt_builder.build(prompt_name, variables)
        if record_prompt:
            context.prompts_used.append(
                self._build_prompt_record(prompt_name, prompt, variables)
            )
        try:
            return await self.llm_client.generate_json(prompt)
        except Exception:
            repair_prompt = (
                f"{prompt}\n\n"
                "Your previous output was invalid JSON. Return the same result again "
                "as valid JSON only. Do not include markdown fences."
            )
            if record_prompt:
                context.prompts_used.append(
                    self._build_prompt_record(
                        f"{prompt_name}_repair",
                        repair_prompt,
                        variables,
                    )
                )
            return await self.llm_client.generate_json(repair_prompt)

    async def _run_validated_json_prompt(
        self,
        prompt_name: str,
        variables: dict[str, Any],
        context: AgentContext,
        output_key: str,
        validator: Callable[[Any], Any],
    ) -> Any:
        """执行 Prompt 并立即把 LLM JSON 转成强类型模型。

        这个方法把“LLM 原始 dict -> Pydantic 模型”的边界固定在 role agent 内，
        后续 pipeline 和 finalizer 就不会再接触裸 dict。
        """

        payload = await self._run_json_prompt(prompt_name, variables, context)
        return validator(payload.get(output_key))

    def _build_prompt_record(
        self,
        prompt_name: str,
        prompt: str,
        variables: dict[str, Any],
    ) -> PromptRecord:
        """生成 prompts_used 记录，并尽量附上 item/spec 追踪信息。"""

        record: dict[str, str] = {"name": prompt_name, "prompt": prompt}

        coverage_item = variables.get("coverage_item")
        if isinstance(coverage_item, dict):
            coverage_item_id = coverage_item.get("coverage_item_id")
            if coverage_item_id:
                record["coverage_item_id"] = str(coverage_item_id)

        test_design_spec = variables.get("test_design_spec")
        if isinstance(test_design_spec, dict):
            spec_id = test_design_spec.get("spec_id")
            if spec_id:
                record["spec_id"] = str(spec_id)

        return PromptRecord.model_validate(record)
