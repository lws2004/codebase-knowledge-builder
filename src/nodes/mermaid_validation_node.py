"""Mermaid 验证节点，用于验证和修复生成文档中的 Mermaid 图表。"""

import os
from typing import Any, Dict, List, Optional

from pocketflow import Node
from pydantic import BaseModel, Field

from ..utils.logger import log_and_notify
from ..utils.mermaid_regenerator import validate_and_regenerate_mermaid


class MermaidValidationNodeConfig(BaseModel):
    """MermaidValidationNode 配置"""

    max_retries: int = Field(3, description="最大重试次数")
    validate_all_files: bool = Field(True, description="是否验证所有生成的文件")
    backup_original: bool = Field(True, description="是否备份原始文件")


class MermaidValidationNode(Node):
    """Mermaid 验证节点，用于验证和修复生成文档中的 Mermaid 图表"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化 Mermaid 验证节点

        Args:
            config: 节点配置
        """
        super().__init__()
        config_model = MermaidValidationNodeConfig(**(config or {}))
        self.config = config_model
        log_and_notify("初始化 Mermaid 验证节点", "info")

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，收集需要验证的文件

        Args:
            shared: 共享存储

        Returns:
            准备结果
        """
        log_and_notify("开始 Mermaid 图表验证", "info")

        # 检查是否有输出文件
        output_files = shared.get("output_files", [])
        if not output_files:
            log_and_notify("没有找到输出文件，跳过 Mermaid 验证", "warning")
            return {"skip": True}

        # 获取 LLM 配置
        llm_config = shared.get("llm_config")
        if not llm_config:
            log_and_notify("没有找到 LLM 配置，无法进行 Mermaid 重新生成", "warning")
            return {"skip": True}

        return {
            "output_files": output_files,
            "llm_config": llm_config,
            "max_retries": self.config.max_retries,
            "validate_all_files": self.config.validate_all_files,
            "backup_original": self.config.backup_original,
        }

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，验证和修复 Mermaid 图表

        Args:
            prep_res: 准备阶段的结果

        Returns:
            执行结果
        """
        # 检查是否跳过
        if prep_res.get("skip", False):
            return {"success": True, "skipped": True, "message": "跳过 Mermaid 验证"}

        output_files = prep_res["output_files"]
        llm_config = prep_res["llm_config"]

        # 初始化 LLM 客户端
        try:
            from ..utils.llm_wrapper.llm_client import LLMClient
            llm_client = LLMClient(llm_config)
        except Exception as e:
            error_msg = f"初始化 LLM 客户端失败: {str(e)}"
            log_and_notify(error_msg, "error")
            return {"success": False, "error": error_msg}

        validated_files = []
        fixed_files = []
        error_files = []

        # 验证每个文件
        for file_path in output_files:
            try:
                log_and_notify(f"验证文件: {file_path}", "info")
                
                # 读取文件内容
                if not os.path.exists(file_path):
                    log_and_notify(f"文件不存在: {file_path}", "warning")
                    error_files.append(file_path)
                    continue

                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # 验证和修复 Mermaid 图表
                fixed_content, was_fixed = validate_and_regenerate_mermaid(
                    content, llm_client, f"文档文件: {os.path.basename(file_path)}"
                )

                if was_fixed:
                    # 备份原始文件
                    if prep_res["backup_original"]:
                        backup_path = file_path + ".backup"
                        with open(backup_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        log_and_notify(f"已备份原始文件到: {backup_path}", "info")

                    # 写入修复后的内容
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(fixed_content)
                    
                    log_and_notify(f"已修复文件中的 Mermaid 图表: {file_path}", "info")
                    fixed_files.append(file_path)
                else:
                    log_and_notify(f"文件中的 Mermaid 图表无需修复: {file_path}", "debug")

                validated_files.append(file_path)

            except Exception as e:
                error_msg = f"验证文件失败 {file_path}: {str(e)}"
                log_and_notify(error_msg, "error")
                error_files.append(file_path)

        # 统计结果
        total_files = len(output_files)
        validated_count = len(validated_files)
        fixed_count = len(fixed_files)
        error_count = len(error_files)

        log_and_notify(
            f"Mermaid 验证完成: 总计 {total_files} 个文件，"
            f"验证 {validated_count} 个，修复 {fixed_count} 个，错误 {error_count} 个",
            "info"
        )

        return {
            "success": True,
            "total_files": total_files,
            "validated_files": validated_files,
            "fixed_files": fixed_files,
            "error_files": error_files,
            "validated_count": validated_count,
            "fixed_count": fixed_count,
            "error_count": error_count,
        }

    def post(self, shared: Dict[str, Any], _prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，更新共享存储

        Args:
            shared: 共享存储
            _prep_res: 准备阶段的结果（未使用）
            exec_res: 执行结果

        Returns:
            下一个节点的标识
        """
        # _prep_res 参数在此方法中未使用，但需要保留以符合接口要求
        _ = _prep_res

        if exec_res.get("success", False):
            # 更新共享存储
            shared["mermaid_validation_result"] = exec_res

            if exec_res.get("skipped", False):
                log_and_notify("Mermaid 验证已跳过", "info")
            else:
                fixed_count = exec_res.get("fixed_count", 0)
                if fixed_count > 0:
                    log_and_notify(f"Mermaid 验证完成，修复了 {fixed_count} 个文件", "info", notify=True)
                else:
                    log_and_notify("Mermaid 验证完成，所有图表语法正确", "info")

            return "default"
        else:
            error_msg = exec_res.get("error", "Mermaid 验证失败")
            shared["error"] = error_msg
            log_and_notify(error_msg, "error", notify=True)
            return "error"


def create_mermaid_validation_node(config: Optional[Dict[str, Any]] = None) -> MermaidValidationNode:
    """创建 Mermaid 验证节点的便捷函数

    Args:
        config: 节点配置

    Returns:
        MermaidValidationNode 实例
    """
    return MermaidValidationNode(config)
