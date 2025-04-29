"""
内容质量检查节点，用于检查生成内容的质量。
"""
import os
import re
from typing import Dict, Any, List, Optional
from pocketflow import Node
from pydantic import BaseModel, Field

from ..utils.logger import log_and_notify
from ..utils.llm_wrapper import LLMClient

class ContentQualityCheckNodeConfig(BaseModel):
    """ContentQualityCheckNode 配置"""
    retry_count: int = Field(2, ge=1, le=5, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("${LLM_MODEL:-gpt-4}", description="LLM 模型")
    auto_fix: bool = Field(True, description="是否自动修复")
    check_aspects: List[str] = Field(
        ["completeness", "accuracy", "readability", "formatting"],
        description="检查方面"
    )
    quality_check_prompt_template: str = Field(
        """
        你是一个内容质量检查专家。请评估以下文档的质量，并提供改进建议。

        文档内容:
        {content}

        请从以下方面评估文档质量:
        1. 完整性: 文档是否涵盖了所有必要的信息？是否有明显的遗漏？
        2. 准确性: 文档中的信息是否准确？是否有明显的错误或误导性内容？
        3. 可读性: 文档是否易于阅读和理解？是否有复杂或混乱的表述？
        4. 格式化: 文档的格式是否一致和专业？是否正确使用了 Markdown 语法？

        对于每个方面，请给出 1-10 的评分，并提供具体的改进建议。

        如果需要修复，请提供修复后的完整文档。
        """,
        description="质量检查提示模板"
    )

class ContentQualityCheckNode(Node):
    """内容质量检查节点，用于检查生成内容的质量"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化内容质量检查节点
        
        Args:
            config: 节点配置
        """
        super().__init__()
        
        # 从配置文件获取默认配置
        from ..utils.env_manager import get_node_config
        default_config = get_node_config("content_quality_check")
        
        # 合并配置
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)
        
        self.config = ContentQualityCheckNodeConfig(**merged_config)
        log_and_notify("初始化内容质量检查节点", "info")
    
    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取生成内容
        
        Args:
            shared: 共享存储
            
        Returns:
            包含生成内容的字典
        """
        log_and_notify("ContentQualityCheckNode: 准备阶段开始", "info")
        
        # 从共享存储中获取生成内容
        content_key = self._get_content_key(shared)
        if not content_key:
            error_msg = "共享存储中没有找到生成内容"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}
        
        content_data = shared.get(content_key)
        if not content_data:
            error_msg = f"共享存储中缺少 {content_key}"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}
        
        # 检查内容是否有效
        if not content_data.get("success", False):
            error_msg = f"{content_key} 无效"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}
        
        # 获取内容
        content = content_data.get("content", "")
        if not content:
            error_msg = f"{content_key} 中没有内容"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}
        
        # 获取文件路径
        file_path = content_data.get("file_path", "")
        
        # 获取 LLM 配置
        llm_config = shared.get("llm_config", {})
        
        # 获取目标语言
        target_language = shared.get("language", "zh")
        
        return {
            "content": content,
            "file_path": file_path,
            "content_key": content_key,
            "llm_config": llm_config,
            "target_language": target_language,
            "retry_count": self.config.retry_count,
            "quality_threshold": self.config.quality_threshold,
            "model": self.config.model,
            "auto_fix": self.config.auto_fix,
            "check_aspects": self.config.check_aspects,
        }
    
    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，检查生成内容的质量
        
        Args:
            prep_res: 准备阶段的结果
            
        Returns:
            检查结果
        """
        log_and_notify("ContentQualityCheckNode: 执行阶段开始", "info")
        
        # 检查准备阶段是否出错
        if "error" in prep_res:
            return {"error": prep_res["error"], "success": False}
        
        content = prep_res["content"]
        file_path = prep_res["file_path"]
        content_key = prep_res["content_key"]
        llm_config = prep_res["llm_config"]
        target_language = prep_res["target_language"]
        retry_count = prep_res["retry_count"]
        quality_threshold = prep_res["quality_threshold"]
        model = prep_res["model"]
        auto_fix = prep_res["auto_fix"]
        check_aspects = prep_res["check_aspects"]
        
        # 准备提示
        prompt = self._create_prompt(content, check_aspects)
        
        # 尝试调用 LLM
        for attempt in range(retry_count):
            try:
                log_and_notify(f"尝试检查内容质量 (尝试 {attempt + 1}/{retry_count})", "info")
                
                # 调用 LLM
                evaluation, fixed_content, quality_score, success = self._call_model(
                    llm_config, prompt, target_language, model
                )
                
                if success:
                    log_and_notify(f"成功检查内容质量 (质量分数: {quality_score['overall']})", "info")
                    
                    # 如果质量低于阈值且启用了自动修复，保存修复后的内容
                    if quality_score["overall"] < quality_threshold and auto_fix and fixed_content:
                        log_and_notify(f"内容质量低于阈值 ({quality_score['overall']} < {quality_threshold})，正在修复", "warning")
                        
                        # 保存修复后的内容
                        if file_path:
                            self._save_fixed_content(fixed_content, file_path)
                            log_and_notify(f"已保存修复后的内容到: {file_path}", "info")
                    
                    return {
                        "evaluation": evaluation,
                        "quality_score": quality_score,
                        "fixed_content": fixed_content if quality_score["overall"] < quality_threshold else None,
                        "content_key": content_key,
                        "needs_fix": quality_score["overall"] < quality_threshold,
                        "success": True
                    }
            except Exception as e:
                log_and_notify(f"LLM 调用失败: {str(e)}, 重试中...", "warning")
        
        # 所有尝试都失败
        error_msg = f"无法检查内容质量，{retry_count} 次尝试后失败"
        log_and_notify(error_msg, "error", notify=True)
        return {"error": error_msg, "success": False}
    
    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将检查结果存储到共享存储中
        
        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res: 执行阶段的结果
            
        Returns:
            下一个节点的动作
        """
        log_and_notify("ContentQualityCheckNode: 后处理阶段开始", "info")
        
        # 检查执行阶段是否出错
        if not exec_res.get("success", False):
            error_msg = exec_res.get("error", "未知错误")
            log_and_notify(f"检查内容质量失败: {error_msg}", "error", notify=True)
            shared["quality_check"] = {"error": error_msg, "success": False}
            return "error"
        
        # 获取内容键
        content_key = exec_res.get("content_key", "")
        
        # 将检查结果存储到共享存储中
        shared["quality_check"] = {
            "evaluation": exec_res.get("evaluation", {}),
            "quality_score": exec_res.get("quality_score", {}),
            "content_key": content_key,
            "needs_fix": exec_res.get("needs_fix", False),
            "success": True
        }
        
        # 如果需要修复且有修复后的内容，更新原始内容
        if exec_res.get("needs_fix", False) and exec_res.get("fixed_content"):
            if content_key in shared and "content" in shared[content_key]:
                shared[content_key]["content"] = exec_res["fixed_content"]
                log_and_notify(f"已更新 {content_key} 的内容", "info")
        
        # 确定下一个动作
        if exec_res.get("needs_fix", False) and not self.config.auto_fix:
            log_and_notify(
                f"内容质量检查完成，需要修复 (质量分数: {exec_res.get('quality_score', {}).get('overall', 0)})",
                "info",
                notify=True
            )
            return "fix"
        else:
            log_and_notify(
                f"内容质量检查完成 (质量分数: {exec_res.get('quality_score', {}).get('overall', 0)})",
                "info",
                notify=True
            )
            return "default"
    
    def _get_content_key(self, shared: Dict[str, Any]) -> Optional[str]:
        """获取内容键
        
        Args:
            shared: 共享存储
            
        Returns:
            内容键
        """
        # 按优先级检查可能的内容键
        possible_keys = [
            "architecture_doc",
            "api_docs",
            "module_details",
            "timeline_doc",
            "dependency_doc",
            "glossary_doc",
            "quick_look_doc"
        ]
        
        for key in possible_keys:
            if key in shared and shared[key].get("success", False):
                return key
        
        return None
    
    def _create_prompt(self, content: str, check_aspects: List[str]) -> str:
        """创建提示
        
        Args:
            content: 内容
            check_aspects: 检查方面
            
        Returns:
            提示
        """
        # 格式化检查方面
        aspects_text = ""
        if "completeness" in check_aspects:
            aspects_text += "1. 完整性: 文档是否涵盖了所有必要的信息？是否有明显的遗漏？\n"
        if "accuracy" in check_aspects:
            aspects_text += "2. 准确性: 文档中的信息是否准确？是否有明显的错误或误导性内容？\n"
        if "readability" in check_aspects:
            aspects_text += "3. 可读性: 文档是否易于阅读和理解？是否有复杂或混乱的表述？\n"
        if "formatting" in check_aspects:
            aspects_text += "4. 格式化: 文档的格式是否一致和专业？是否正确使用了 Markdown 语法？\n"
        
        # 格式化提示
        prompt = self.config.quality_check_prompt_template.format(
            content=content,
            aspects=aspects_text
        )
        
        return prompt
    
    def _call_model(
        self,
        llm_config: Dict[str, Any],
        prompt: str,
        target_language: str,
        model: str
    ) -> tuple:
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
            system_prompt = f"""你是一个内容质量检查专家，擅长评估文档质量并提供改进建议。
请用{target_language}语言回答，但保持代码、变量名和技术术语的原始形式。

请按以下格式提供评估结果:

## 评估结果
- 完整性: [1-10分] - [评价]
- 准确性: [1-10分] - [评价]
- 可读性: [1-10分] - [评价]
- 格式化: [1-10分] - [评价]
- 总体评分: [1-10分]

## 改进建议
[具体的改进建议]

## 修复后的内容
```markdown
[如果需要修复，提供完整的修复后内容]
```

请确保你的评估是客观的，并提供具体的改进建议。如果文档质量已经很好，可以简单说明。"""
            
            # 调用 LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            response = llm_client.completion(
                messages=messages,
                temperature=0.3,
                model=model,
                trace_name="检查内容质量"
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
        evaluation = {
            "completeness": {"score": 0, "comment": ""},
            "accuracy": {"score": 0, "comment": ""},
            "readability": {"score": 0, "comment": ""},
            "formatting": {"score": 0, "comment": ""},
            "overall": 0,
            "suggestions": ""
        }
        
        # 提取完整性评分
        completeness_match = re.search(r"完整性:\s*(\d+)(?:/10)?(?:\s*分)?\s*-\s*(.+?)(?:\n|$)", content)
        if completeness_match:
            evaluation["completeness"]["score"] = int(completeness_match.group(1))
            evaluation["completeness"]["comment"] = completeness_match.group(2).strip()
        
        # 提取准确性评分
        accuracy_match = re.search(r"准确性:\s*(\d+)(?:/10)?(?:\s*分)?\s*-\s*(.+?)(?:\n|$)", content)
        if accuracy_match:
            evaluation["accuracy"]["score"] = int(accuracy_match.group(1))
            evaluation["accuracy"]["comment"] = accuracy_match.group(2).strip()
        
        # 提取可读性评分
        readability_match = re.search(r"可读性:\s*(\d+)(?:/10)?(?:\s*分)?\s*-\s*(.+?)(?:\n|$)", content)
        if readability_match:
            evaluation["readability"]["score"] = int(readability_match.group(1))
            evaluation["readability"]["comment"] = readability_match.group(2).strip()
        
        # 提取格式化评分
        formatting_match = re.search(r"格式化:\s*(\d+)(?:/10)?(?:\s*分)?\s*-\s*(.+?)(?:\n|$)", content)
        if formatting_match:
            evaluation["formatting"]["score"] = int(formatting_match.group(1))
            evaluation["formatting"]["comment"] = formatting_match.group(2).strip()
        
        # 提取总体评分
        overall_match = re.search(r"总体评分:\s*(\d+)(?:/10)?(?:\s*分)?", content)
        if overall_match:
            evaluation["overall"] = int(overall_match.group(1))
        else:
            # 如果没有明确的总体评分，计算平均分
            scores = [
                evaluation["completeness"]["score"],
                evaluation["accuracy"]["score"],
                evaluation["readability"]["score"],
                evaluation["formatting"]["score"]
            ]
            evaluation["overall"] = sum(scores) / len(scores) if scores else 0
        
        # 提取改进建议
        suggestions_match = re.search(r"## 改进建议\s*\n(.*?)(?:\n##|$)", content, re.DOTALL)
        if suggestions_match:
            evaluation["suggestions"] = suggestions_match.group(1).strip()
        
        return evaluation
    
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
    
    def _save_fixed_content(self, content: str, file_path: str) -> None:
        """保存修复后的内容
        
        Args:
            content: 内容
            file_path: 文件路径
        """
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            log_and_notify(f"保存修复后的内容失败: {str(e)}", "error")
