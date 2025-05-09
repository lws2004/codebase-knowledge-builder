"""模块质量检查节点配置，提供配置类和提示模板。"""

from typing import List

from pydantic import BaseModel, Field


class ModuleQualityCheckNodeConfig(BaseModel):
    """ModuleQualityCheckNode 配置"""

    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("", description="LLM 模型，从配置中获取，不应设置默认值")
    auto_fix: bool = Field(True, description="是否自动修复")
    check_aspects: List[str] = Field([], description="检查方面，从配置文件中加载")
    quality_check_prompt_template: str = Field(
        "{content}",  # 简单的占位符，实际模板将从配置文件中加载
        description="质量检查提示模板，从配置文件中加载",
    )
