"""模块质量检查评估器，提供评估结果解析和内容提取功能。"""

import json
import re
from typing import Dict, Optional, TypedDict, cast

from ..utils.logger import log_and_notify


class EvaluationCategory(TypedDict):
    score: int
    comments: str


class EvaluationResult(TypedDict):
    completeness: EvaluationCategory
    accuracy: EvaluationCategory
    readability: EvaluationCategory
    formatting: EvaluationCategory
    visualization: EvaluationCategory
    overall: int
    needs_fix: bool
    fix_suggestions: str


class ModuleQualityCheckEvaluator:
    """模块质量检查评估器，提供评估结果解析和内容提取功能"""

    @staticmethod
    def parse_evaluation(content: str) -> EvaluationResult:
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
                # 确保 JSON 结果符合 EvaluationResult 结构，或者进行转换
                # 这里为了简化，我们假设 JSON 结构与 EvaluationResult 匹配
                parsed_json = json.loads(json_match.group(1))
                # 你可能需要添加代码来验证或转换 parsed_json 的结构
                return cast(EvaluationResult, parsed_json)
            except Exception as e:
                log_and_notify(f"解析 JSON 失败: {str(e)}", "error")

        # 如果无法提取 JSON，尝试手动解析
        result: EvaluationResult = {
            "completeness": {"score": 0, "comments": ""},
            "accuracy": {"score": 0, "comments": ""},
            "readability": {"score": 0, "comments": ""},
            "formatting": {"score": 0, "comments": ""},
            "visualization": {"score": 0, "comments": ""},
            "overall": 0,
            "needs_fix": False,
            "fix_suggestions": "",
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

        # 提取可视化评分
        visualization_match = re.search(r"可视化.*?(\d+).*?[评分分数]", content, re.DOTALL)
        if visualization_match:
            result["visualization"]["score"] = int(visualization_match.group(1))

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

    @staticmethod
    def extract_fixed_content(content: str) -> Optional[str]:
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

    @staticmethod
    def calculate_quality_score(evaluation: EvaluationResult) -> Dict[str, float]:
        """计算质量分数

        Args:
            evaluation: 评估结果 (TypedDict)

        Returns:
            质量分数
        """
        return {
            "completeness": evaluation["completeness"]["score"] / 10,
            "accuracy": evaluation["accuracy"]["score"] / 10,
            "readability": evaluation["readability"]["score"] / 10,
            "formatting": evaluation["formatting"]["score"] / 10,
            "visualization": evaluation["visualization"]["score"] / 10,
            "overall": evaluation["overall"] / 10,
        }
