"""模块质量检查节点，用于检查模块文档的质量。"""
import re
from typing import Any, Dict, List, Optional, Tuple

from pocketflow import Node
from pydantic import BaseModel, Field

from ..utils.llm_wrapper.llm_client import LLMClient
from ..utils.logger import log_and_notify


class ModuleQualityCheckNodeConfig(BaseModel):
    """ModuleQualityCheckNode 配置"""
    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("qwen/qwen3-30b-a3b:free", description="LLM 模型")
    auto_fix: bool = Field(True, description="是否自动修复")
    check_aspects: List[str] = Field(
        ["completeness", "accuracy", "readability", "formatting"],
        description="检查方面"
    )
    quality_check_prompt_template: str = Field(
        """
        你是一个文档质量评估专家。请评估以下模块文档的质量，并提供改进建议。

        文档内容:
        {content}

        请从以下几个方面评估文档质量:
        1. 完整性 (Completeness): 文档是否涵盖了模块的所有重要方面，包括功能、接口、用法等
        2. 准确性 (Accuracy): 文档中的信息是否准确，是否与代码一致
        3. 可读性 (Readability): 文档是否易于阅读和理解，语言是否清晰简洁
        4. 格式化 (Formatting): 文档的格式是否规范，是否使用了适当的标题、列表、代码块等

        对于每个方面，请给出1-10的评分，并提供具体的改进建议。
        然后，给出一个总体评分 (1-10)。

        如果文档质量不佳，请提供修复后的内容。

        请按以下格式输出:
        ```json
        {
          "completeness": {
            "score": 评分,
            "comments": "评论和建议"
          },
          "accuracy": {
            "score": 评分,
            "comments": "评论和建议"
          },
          "readability": {
            "score": 评分,
            "comments": "评论和建议"
          },
          "formatting": {
            "score": 评分,
            "comments": "评论和建议"
          },
          "overall": 总体评分,
          "needs_fix": true/false,
          "fix_suggestions": "具体的修复建议"
        }
        ```

        ## 修复后的内容

        如果文档需要修复，请在这里提供修复后的完整内容:

        ```markdown
        修复后的文档内容
        ```
        """,
        description="质量检查提示模板"
    )

class ModuleQualityCheckNode(Node):
    """模块质量检查节点，用于检查模块文档的质量"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化模块质量检查节点

        Args:
            config: 节点配置
        """
        super().__init__()

        # 从配置文件获取默认配置
        from ..utils.env_manager import get_node_config
        default_config = get_node_config("module_quality_check")

        # 合并配置
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)

        self.config = ModuleQualityCheckNodeConfig(**merged_config)
        log_and_notify("初始化模块质量检查节点", "info")

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取必要的数据

        Args:
            shared: 共享存储

        Returns:
            准备结果
        """
        # 从共享存储中获取模块详细文档
        module_details = shared.get("module_details")
        if not module_details:
            error_msg = "共享存储中缺少模块详细文档"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 获取 LLM 配置
        llm_config = shared.get("llm_config", {})

        # 获取目标语言
        target_language = shared.get("language", "zh")

        return {
            "module_details": module_details,
            "llm_config": llm_config,
            "target_language": target_language,
            "retry_count": self.config.retry_count,
            "quality_threshold": self.config.quality_threshold,
            "model": self.config.model,
            "auto_fix": self.config.auto_fix,
            "check_aspects": self.config.check_aspects,
        }

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，检查模块文档质量

        Args:
            prep_res: 准备阶段的结果

        Returns:
            执行结果
        """
        # 检查准备阶段是否有错误
        if "error" in prep_res:
            return {"success": False, "error": prep_res["error"]}

        # 获取必要的数据
        module_details = prep_res["module_details"]
        llm_config = prep_res["llm_config"]
        target_language = prep_res["target_language"]
        retry_count = prep_res["retry_count"]
        prep_res["quality_threshold"]
        model = prep_res["model"]
        auto_fix = prep_res["auto_fix"]
        prep_res["check_aspects"]

        # 获取模块列表
        modules = module_details.get("modules", [])
        if not modules:
            error_msg = "模块详细文档中没有模块"
            log_and_notify(error_msg, "error", notify=True)
            return {"success": False, "error": error_msg}

        # 检查每个模块的质量
        checked_modules = []
        for module in modules:
            try:
                log_and_notify(f"检查模块质量: {module.get('name', 'unknown')}", "info")

                # 获取模块内容
                content = module.get("content", "")
                if not content:
                    log_and_notify(f"模块 {module.get('name', 'unknown')} 没有内容，跳过", "warning")
                    checked_modules.append(module)
                    continue

                # 准备提示
                prompt = self._create_prompt(content)

                # 尝试调用 LLM
                for attempt in range(retry_count):
                    try:
                        log_and_notify(f"尝试检查模块质量 (尝试 {attempt + 1}/{retry_count})", "info")

                        # 调用 LLM
                        evaluation, fixed_content, quality_score, success = self._call_model(
                            llm_config, prompt, target_language, model
                        )

                        if success:
                            log_and_notify(f"成功检查模块质量 (质量分数: {quality_score['overall']})", "info")

                            # 检查是否需要修复
                            needs_fix = evaluation.get("needs_fix", False)
                            if needs_fix and auto_fix and fixed_content:
                                log_and_notify("自动修复模块内容", "info")
                                module["content"] = fixed_content
                                module["quality_score"] = quality_score
                                module["evaluation"] = evaluation
                                module["fixed"] = True
                            else:
                                module["quality_score"] = quality_score
                                module["evaluation"] = evaluation
                                module["fixed"] = False

                            checked_modules.append(module)
                            break
                    except Exception as e:
                        log_and_notify(f"LLM 调用失败: {str(e)}, 重试中...", "warning")

                # 如果所有重试都失败，保留原始模块
                if "quality_score" not in module:
                    log_and_notify("无法检查模块质量，保留原始模块", "warning")
                    checked_modules.append(module)
            except Exception as e:
                log_and_notify(f"检查模块质量失败: {str(e)}", "error")
                checked_modules.append(module)

        # 计算整体质量分数
        overall_score = 0.0
        if checked_modules:
            overall_score = sum(
                module.get("quality_score", {}).get("overall", 0)
                for module in checked_modules
                if "quality_score" in module
            ) / len(checked_modules)

        return {
            "modules": checked_modules,
            "overall_score": overall_score,
            "success": True
        }

    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将检查结果存储到共享存储中

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        if not exec_res.get("success", False):
            shared["error"] = exec_res.get("error", "检查模块质量失败")
            return "error"

        # 更新模块详细文档
        shared["module_details"]["modules"] = exec_res["modules"]
        shared["module_details"]["overall_score"] = exec_res["overall_score"]

        log_and_notify(f"模块质量检查完成 (整体分数: {exec_res['overall_score']})", "info", notify=True)
        return "default"

    def _create_prompt(self, content: str) -> str:
        """创建提示

        Args:
            content: 模块内容

        Returns:
            提示
        """
        # 格式化提示
        return self.config.quality_check_prompt_template.format(
            content=content
        )

    def _call_model(
        self,
        llm_config: Dict[str, Any],
        prompt: str,
        target_language: str,
        model: str
    ) -> Tuple[Dict[str, Any], Optional[str], Dict[str, float], bool]:
        """调用 LLM

        Args:
            llm_config: LLM 配置
            prompt: 提示
            target_language: 目标语言
            model: 模型

        Returns:
            评估结果、修复后的内容、质量分数和成功标志
        """
        try:
            # 创建 LLM 客户端
            llm_client = LLMClient(llm_config)

            # 准备系统提示
            system_prompt = f"""你是一个文档质量评估专家，擅长评估文档质量并提供改进建议。
请用{target_language}语言回答，但保持代码、变量名和技术术语的原始形式。
你的评估应该客观公正，基于文档的完整性、准确性、可读性和格式化。
如果文档需要修复，请提供修复后的完整内容。"""

            # 调用 LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]

            response = llm_client.completion(
                messages=messages,
                temperature=0.3,
                model=model,
                trace_name="检查模块质量"
            )

            # 获取响应内容
            content = llm_client.get_completion_content(response)

            # 解析评估结果
            evaluation = self._parse_evaluation(content)

            # 提取修复后的内容
            fixed_content = self._extract_fixed_content(content)

            # 计算质量分数
            quality_score = {
                "completeness": evaluation.get("completeness", {}).get("score", 0) / 10,
                "accuracy": evaluation.get("accuracy", {}).get("score", 0) / 10,
                "readability": evaluation.get("readability", {}).get("score", 0) / 10,
                "formatting": evaluation.get("formatting", {}).get("score", 0) / 10,
                "overall": evaluation.get("overall", 0) / 10
            }

            return evaluation, fixed_content, quality_score, True
        except Exception as e:
            log_and_notify(f"调用 LLM 失败: {str(e)}", "error")
            raise

    def _parse_evaluation(self, content: str) -> Dict[str, Any]:
        """解析评估结果

        Args:
            content: 内容

        Returns:
            评估结果
        """
        # 提取 JSON 部分
        json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if json_match:
            try:
                import json
                return json.loads(json_match.group(1))
            except Exception as e:
                log_and_notify(f"解析 JSON 失败: {str(e)}", "error")

        # 如果无法提取 JSON，尝试手动解析
        result = {
            "completeness": {"score": 0, "comments": ""},
            "accuracy": {"score": 0, "comments": ""},
            "readability": {"score": 0, "comments": ""},
            "formatting": {"score": 0, "comments": ""},
            "overall": 0,
            "needs_fix": False,
            "fix_suggestions": ""
        }

        # 提取完整性评分
        completeness_match = re.search(r"完整性.*?(\d+).*?[评分分数]", content, re.DOTALL)
        if completeness_match:
            result["completeness"]["score"] = int(completeness_match.group(1))

        # 提取准确性评分
        accuracy_match = re.search(r"准确性.*?(\d+).*?[评分分数]", content, re.DOTALL)
        if accuracy_match:
            result["accuracy"]["score"] = int(accuracy_match.group(1))

        # 提取可读性评分
        readability_match = re.search(r"可读性.*?(\d+).*?[评分分数]", content, re.DOTALL)
        if readability_match:
            result["readability"]["score"] = int(readability_match.group(1))

        # 提取格式化评分
        formatting_match = re.search(r"格式化.*?(\d+).*?[评分分数]", content, re.DOTALL)
        if formatting_match:
            result["formatting"]["score"] = int(formatting_match.group(1))

        # 提取总体评分
        overall_match = re.search(r"总体[评分分数].*?(\d+)", content, re.DOTALL)
        if overall_match:
            result["overall"] = int(overall_match.group(1))

        # 判断是否需要修复
        result["needs_fix"] = "需要修复" in content or "建议修复" in content

        # 提取修复建议
        fix_match = re.search(r"修复建议[：:](.*?)(?=##|$)", content, re.DOTALL)
        if fix_match:
            result["fix_suggestions"] = fix_match.group(1).strip()

        return result

    def _extract_fixed_content(self, content: str) -> Optional[str]:
        """提取修复后的内容

        Args:
            content: 内容

        Returns:
            修复后的内容
        """
        # 提取修复后的内容
        fixed_match = re.search(r"```markdown\s*(.*?)\s*```", content, re.DOTALL)
        if fixed_match:
            return fixed_match.group(1).strip()

        # 如果没有明确的修复内容块，尝试提取整个修复后的内容部分
        fixed_section_match = re.search(r"## 修复后的内容\s*\n(.*?)(?:\n##|$)", content, re.DOTALL)
        if fixed_section_match:
            fixed_content = fixed_section_match.group(1).strip()
            # 移除可能的 Markdown 代码块标记
            fixed_content = re.sub(r"^```markdown\s*|\s*```$", "", fixed_content, flags=re.MULTILINE)
            return fixed_content

        return None
