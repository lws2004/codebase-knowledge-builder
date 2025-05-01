"""格式化输出节点，用于格式化输出文档。"""
import re
from typing import Any, Dict, List, Optional

from pocketflow import Node
from pydantic import BaseModel, Field

from ..utils.formatter import format_markdown, split_content_into_files
from ..utils.logger import log_and_notify


class FormatOutputNodeConfig(BaseModel):
    """FormatOutputNode 配置"""
    output_format: str = Field("markdown", description="输出格式")
    add_toc: bool = Field(True, description="是否添加目录")
    add_nav_links: bool = Field(True, description="是否添加导航链接")
    add_emojis: bool = Field(True, description="是否添加 emoji")
    justdoc_compatible: bool = Field(True, description="是否生成 JustDoc 兼容文档")
    template: Optional[str] = Field(None, description="自定义模板")
    default_template: str = Field(
        """# {title}

{toc}

## 简介

{introduction}

## 系统架构

{architecture}

## 核心模块

{core_modules}

## 使用示例

{examples}

## 常见问题

{faq}

## 参考资料

{references}
""",
        description="默认模板"
    )


class FormatOutputNode(Node):
    """格式化输出节点，用于格式化输出文档"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化格式化输出节点

        Args:
            config: 节点配置
        """
        super().__init__()
        config_model = FormatOutputNodeConfig(**(config or {}))
        self.config = config_model
        log_and_notify("初始化格式化输出节点", "info")

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，收集格式化所需的信息

        Args:
            shared: 共享存储

        Returns:
            准备结果
        """
        log_and_notify("开始格式化输出", "info")

        # 检查是否有翻译后的内容
        if "translated_content" not in shared:
            error_msg = "没有找到翻译后的内容"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 获取翻译后的内容
        translated_content = shared["translated_content"]

        # 获取文件结构
        file_structure = shared.get("file_structure", {})

        # 获取仓库结构
        repo_structure = shared.get("repo_structure", {})

        # 获取输出目录
        output_dir = shared.get("output_dir", "docs_output")

        # 获取仓库信息
        repo_url = shared.get("repo_url", "")
        repo_branch = shared.get("repo_branch", "main")

        # 获取目标语言
        target_language = shared.get("language", "zh")

        return {
            "translated_content": translated_content,
            "file_structure": file_structure,
            "repo_structure": repo_structure,
            "output_dir": output_dir,
            "repo_url": repo_url,
            "repo_branch": repo_branch,
            "target_language": target_language,
            "output_format": self.config.output_format,
            "add_toc": self.config.add_toc,
            "add_nav_links": self.config.add_nav_links,
            "add_emojis": self.config.add_emojis,
            "justdoc_compatible": self.config.justdoc_compatible,
            "template": self.config.template or self.config.default_template
        }

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，格式化输出文档

        Args:
            prep_res: 准备阶段的结果

        Returns:
            执行结果
        """
        # 检查准备阶段是否有错误
        if "error" in prep_res:
            return {"success": False, "error": prep_res["error"]}

        # 获取参数
        translated_content = prep_res["translated_content"]
        file_structure = prep_res["file_structure"]
        repo_structure = prep_res["repo_structure"]
        output_dir = prep_res["output_dir"]
        prep_res["repo_url"]
        prep_res["repo_branch"]
        prep_res["target_language"]
        output_format = prep_res["output_format"]
        add_toc = prep_res["add_toc"]
        add_nav_links = prep_res["add_nav_links"]
        add_emojis = prep_res["add_emojis"]
        justdoc_compatible = prep_res["justdoc_compatible"]
        template = prep_res["template"]

        try:
            # 解析内容为结构化数据
            log_and_notify("开始解析内容为结构化数据", "info")
            content_dict = self._parse_content(translated_content)

            # 格式化 Markdown
            log_and_notify("开始格式化 Markdown", "info")
            formatted_content = format_markdown(
                content_dict,
                template=template,
                toc=add_toc,
                nav_links=add_nav_links,
                add_emojis=add_emojis
            )

            # 拆分内容为多个文件
            log_and_notify("开始拆分内容为多个文件", "info")
            output_files = split_content_into_files(
                content_dict,
                output_dir,
                file_structure=file_structure,
                repo_structure=repo_structure,
                justdoc_compatible=justdoc_compatible
            )

            # 如果输出格式不是 Markdown，转换为其他格式
            if output_format != "markdown":
                log_and_notify(f"开始转换为 {output_format} 格式", "info")
                output_files = self._convert_to_other_format(output_files, output_format)

            return {
                "formatted_content": formatted_content,
                "output_files": output_files,
                "output_dir": output_dir,
                "output_format": output_format,
                "success": True
            }
        except Exception as e:
            error_msg = f"格式化输出失败: {str(e)}"
            log_and_notify(error_msg, "error", notify=True)
            return {"success": False, "error": error_msg}

    def post(self, shared: Dict[str, Any], exec_res: Dict[str, Any]) -> None:
        """后处理阶段，更新共享存储

        Args:
            shared: 共享存储
            exec_res: 执行结果
        """
        if exec_res.get("success", False):
            # 更新共享存储
            shared["formatted_content"] = exec_res["formatted_content"]
            shared["output_files"] = exec_res["output_files"]
            shared["output_dir"] = exec_res["output_dir"]
            shared["output_format"] = exec_res["output_format"]

            log_and_notify(f"格式化输出完成，生成了 {len(exec_res['output_files'])} 个文件", "info", notify=True)
        elif "error" in exec_res:
            shared["error"] = exec_res["error"]
            log_and_notify(f"格式化输出失败: {exec_res['error']}", "error", notify=True)

    def _parse_content(self, content: str) -> Dict[str, Any]:
        """解析内容为结构化数据

        Args:
            content: 内容

        Returns:
            结构化数据
        """
        # 简单实现：按标题分割内容
        content_dict = {
            "title": "代码库文档",
            "introduction": "",
            "architecture": "",
            "core_modules": "",
            "examples": "",
            "faq": "",
            "references": ""
        }

        # 查找标题
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            content_dict["title"] = title_match.group(1)

        # 查找简介
        intro_match = re.search(r'##\s+(?:简介|介绍|概述)(.+?)(?=##\s+|$)', content, re.MULTILINE | re.DOTALL)
        if intro_match:
            content_dict["introduction"] = intro_match.group(1).strip()

        # 查找架构
        arch_match = re.search(r'##\s+(?:架构|系统架构|设计)(.+?)(?=##\s+|$)', content, re.MULTILINE | re.DOTALL)
        if arch_match:
            content_dict["architecture"] = arch_match.group(1).strip()

        # 查找核心模块
        modules_match = re.search(r'##\s+(?:核心模块|模块|组件)(.+?)(?=##\s+|$)', content, re.MULTILINE | re.DOTALL)
        if modules_match:
            content_dict["core_modules"] = modules_match.group(1).strip()

        # 查找示例
        examples_match = re.search(r'##\s+(?:示例|使用示例|用法)(.+?)(?=##\s+|$)', content, re.MULTILINE | re.DOTALL)
        if examples_match:
            content_dict["examples"] = examples_match.group(1).strip()

        # 查找常见问题
        faq_match = re.search(r'##\s+(?:常见问题|FAQ|问题)(.+?)(?=##\s+|$)', content, re.MULTILINE | re.DOTALL)
        if faq_match:
            content_dict["faq"] = faq_match.group(1).strip()

        # 查找参考资料
        ref_match = re.search(r'##\s+(?:参考资料|参考|引用)(.+?)(?=##\s+|$)', content, re.MULTILINE | re.DOTALL)
        if ref_match:
            content_dict["references"] = ref_match.group(1).strip()

        return content_dict

    def _convert_to_other_format(self, markdown_files: List[str], output_format: str) -> List[str]:
        """将 Markdown 文件转换为其他格式

        Args:
            markdown_files: Markdown 文件列表
            output_format: 输出格式

        Returns:
            转换后的文件列表
        """
        # 目前仅支持 Markdown 格式，其他格式需要额外实现
        if output_format == "pdf":
            log_and_notify("PDF 转换功能尚未实现，保持 Markdown 格式", "warning")
        elif output_format == "html":
            log_and_notify("HTML 转换功能尚未实现，保持 Markdown 格式", "warning")
        else:
            log_and_notify(f"不支持的输出格式: {output_format}，保持 Markdown 格式", "warning")

        return markdown_files
