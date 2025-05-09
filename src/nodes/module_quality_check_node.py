"""模块质量检查节点，用于检查模块文档的质量。"""

from typing import Any, Dict, Optional, Tuple

from pocketflow import Node

from ..utils.llm_wrapper.llm_client import LLMClient
from ..utils.logger import log_and_notify
from .module_quality_check_config import ModuleQualityCheckNodeConfig
from .module_quality_check_evaluator import EvaluationResult, ModuleQualityCheckEvaluator


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
        model = prep_res["model"]
        auto_fix = prep_res["auto_fix"]

        # 获取模块列表
        modules = module_details.get("docs", [])
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
                            needs_fix = (
                                evaluation.get("needs_fix", False)
                                or quality_score["overall"] < self.config.quality_threshold
                            )

                            # 记录评估结果
                            module["quality_score"] = quality_score
                            module["evaluation"] = evaluation
                            module["needs_fix"] = needs_fix

                            # 如果需要修复且启用了自动修复且有修复后的内容
                            if needs_fix and auto_fix and fixed_content:
                                log_and_notify("自动修复模块内容", "info")
                                module["content"] = fixed_content
                                module["fixed"] = True
                            else:
                                module["fixed"] = False

                            # 如果需要修复但没有启用自动修复，记录警告
                            if needs_fix and not auto_fix:
                                log_and_notify(
                                    f"模块 {module.get('name', 'unknown')} 需要改进，但自动修复未启用", "warning"
                                )

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

        return {"modules": checked_modules, "overall_score": overall_score, "success": True}

    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将检查结果存储到共享存储中

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果（未使用）
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        # 使用prep_res参数，避免IDE警告
        _ = prep_res
        if not exec_res.get("success", False):
            shared["error"] = exec_res.get("error", "检查模块质量失败")
            return "error"

        # 更新模块详细文档
        shared["module_details"]["docs"] = exec_res["modules"]
        shared["module_details"]["overall_score"] = exec_res["overall_score"]

        # 检查是否有需要修复的模块
        modules_need_fix = [m for m in exec_res["modules"] if m.get("needs_fix", False)]

        # 将检查结果存储到共享存储中
        shared["module_quality_check"] = {
            "overall_score": exec_res["overall_score"],
            "modules_checked": len(exec_res["modules"]),
            "modules_need_fix": len(modules_need_fix),
            "success": True,
        }

        # 确定下一个动作
        if modules_need_fix:
            if self.config.auto_fix:
                # 如果启用了自动修复，检查是否有模块被修复
                modules_fixed = [m for m in modules_need_fix if m.get("fixed", False)]
                if len(modules_fixed) == len(modules_need_fix):
                    log_and_notify(
                        f"模块质量检查完成，已自动修复 {len(modules_fixed)} 个模块 (整体分数: {exec_res['overall_score']})",
                        "info",
                        notify=True,
                    )
                    return "default"
                else:
                    log_and_notify(
                        f"模块质量检查完成，{len(modules_need_fix)} 个模块需要改进，但只有 {len(modules_fixed)} 个被自动修复 (整体分数: {exec_res['overall_score']})",
                        "warning",
                        notify=True,
                    )
                    # 返回需要修复的信号，让生成节点重新生成
                    return "fix"
            else:
                log_and_notify(
                    f"模块质量检查完成，{len(modules_need_fix)} 个模块需要改进 (整体分数: {exec_res['overall_score']})",
                    "warning",
                    notify=True,
                )
                # 返回需要修复的信号，让生成节点重新生成
                return "fix"
        else:
            log_and_notify(
                f"模块质量检查完成，所有模块质量良好 (整体分数: {exec_res['overall_score']})",
                "info",
                notify=True,
            )
            return "default"

    def _create_prompt(self, content: str) -> str:
        """创建提示

        Args:
            content: 模块内容

        Returns:
            提示
        """
        # 格式化提示
        return self.config.quality_check_prompt_template.format(content=content)

    def _call_model(
        self, llm_config: Dict[str, Any], prompt: str, target_language: str, model: str
    ) -> Tuple[EvaluationResult, Optional[str], Dict[str, float], bool]:
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
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]

            response = llm_client.completion(
                messages=messages, temperature=0.3, model=model, trace_name="检查模块质量", max_input_tokens=None
            )

            # 获取响应内容
            content = llm_client.get_completion_content(response)

            # 使用评估器解析结果
            evaluator = ModuleQualityCheckEvaluator()
            evaluation: EvaluationResult = evaluator.parse_evaluation(content)
            fixed_content = evaluator.extract_fixed_content(content)
            quality_score = evaluator.calculate_quality_score(evaluation)

            return evaluation, fixed_content, quality_score, True
        except Exception as e:
            log_and_notify(f"调用 LLM 失败: {str(e)}", "error")
            default_eval: EvaluationResult = {
                "completeness": {"score": 0, "comments": "Error calling model"},
                "accuracy": {"score": 0, "comments": ""},
                "readability": {"score": 0, "comments": ""},
                "formatting": {"score": 0, "comments": ""},
                "overall": 0,
                "needs_fix": False,
                "fix_suggestions": "",
            }
            return default_eval, None, {"overall": 0.0}, False
