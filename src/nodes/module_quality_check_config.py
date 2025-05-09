"""模块质量检查节点配置，提供配置类和提示模板。"""

from typing import List

from pydantic import BaseModel, Field


class ModuleQualityCheckNodeConfig(BaseModel):
    """ModuleQualityCheckNode 配置"""

    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("", description="LLM 模型，从配置中获取，不应设置默认值")
    auto_fix: bool = Field(True, description="是否自动修复")
    check_aspects: List[str] = Field(["completeness", "accuracy", "readability", "formatting"], description="检查方面")
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
        description="质量检查提示模板",
    )
