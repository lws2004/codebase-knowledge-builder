"""格式化输出节点，用于格式化输出文档。"""

import os
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
        description="默认模板",
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

        # 检查是否有组合后的内容
        if "combined_content" not in shared:
            error_msg = "没有找到组合后的内容"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 获取组合后的内容
        combined_content = shared["combined_content"]

        # 获取文件结构
        file_structure = shared.get("file_structure", {})

        # 获取仓库结构
        repo_structure = shared.get("repo_structure", {})

        # 获取仓库名称
        repo_name = shared.get("repo_name", "docs")

        # 确保仓库结构中包含仓库名称
        if isinstance(repo_structure, dict):
            repo_structure["repo_name"] = repo_name

        # 获取输出目录
        output_dir = shared.get("output_dir", "docs_output")

        # 获取仓库信息
        repo_url = shared.get("repo_url", "")
        repo_branch = shared.get("repo_branch", "main")

        # 获取目标语言
        target_language = shared.get("language", "zh")

        return {
            "combined_content": combined_content,
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
            "template": self.config.template or self.config.default_template,
            "shared": shared,  # 传递共享存储，以便在exec阶段使用
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
        combined_content = prep_res["combined_content"]
        file_structure = prep_res["file_structure"]
        repo_structure = prep_res["repo_structure"]
        output_dir = prep_res["output_dir"]
        output_format = prep_res["output_format"]
        add_toc = prep_res["add_toc"]
        add_nav_links = prep_res["add_nav_links"]
        add_emojis = prep_res["add_emojis"]
        justdoc_compatible = prep_res["justdoc_compatible"]
        template = prep_res["template"]
        # Extract repo_url and repo_branch from prep_res
        repo_url = prep_res.get("repo_url", "")
        repo_branch = prep_res.get("repo_branch", "main")

        # 打印调试信息
        print(f"格式化输出文档，输出目录: {output_dir}")
        print(f"组合内容长度: {len(combined_content)}")

        try:
            # 解析内容为结构化数据
            log_and_notify("开始解析内容为结构化数据", "info")
            content_dict = self._parse_content(combined_content)

            # 确保repo_name正确设置
            repo_name = repo_structure.get("repo_name", "requests")
            content_dict["repo_name"] = repo_name

            # 打印解析后的内容键
            print(f"解析后的内容键: {list(content_dict.keys())}")
            print(f"仓库名称: {repo_name}")

            # 从共享存储中获取已生成的文档内容
            self._merge_generated_content(prep_res.get("shared", {}), content_dict)

            # 格式化 Markdown
            log_and_notify("开始格式化 Markdown", "info")
            formatted_content = format_markdown(
                content_dict, template=template, toc=add_toc, nav_links=add_nav_links, add_emojis=add_emojis
            )

            # 将原始内容添加到content_dict，以便在没有解析出内容时使用
            content_dict["combined_content"] = combined_content

            # 拆分内容为多个文件
            log_and_notify("开始拆分内容为多个文件", "info")
            output_files = split_content_into_files(
                content_dict,
                output_dir,
                file_structure=file_structure,
                repo_structure=repo_structure,
                justdoc_compatible=justdoc_compatible,
                repo_url=repo_url,
                branch=repo_branch,
            )

            # 如果输出格式不是 Markdown，转换为其他格式
            if output_format != "markdown":
                log_and_notify(f"开始转换为 {output_format} 格式", "info")
                output_files = self._convert_to_other_format(output_files, output_format)

            # 检查是否生成了文件
            if not output_files:
                log_and_notify("警告: 没有生成任何文件", "warning")
                # 尝试直接保存原始内容
                index_path = os.path.join(output_dir, repo_name, "index.md")
                os.makedirs(os.path.dirname(index_path), exist_ok=True)
                with open(index_path, "w", encoding="utf-8") as f:
                    f.write(f"---\ntitle: 文档首页\n---\n\n# 文档首页\n\n{combined_content}")
                output_files = [index_path]
                log_and_notify(f"已将原始内容保存到 {index_path}", "info")

            return {
                "formatted_content": formatted_content,
                "output_files": output_files,
                "output_dir": output_dir,
                "output_format": output_format,
                "success": True,
            }
        except Exception as e:
            error_msg = f"格式化输出失败: {str(e)}"
            log_and_notify(error_msg, "error", notify=True)
            import traceback

            print(f"格式化输出异常: {traceback.format_exc()}")
            return {"success": False, "error": error_msg}

    def post(self, shared: Dict[str, Any], _prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，更新共享存储

        Args:
            shared: 共享存储
            _prep_res: 准备阶段的结果（未使用）
            exec_res: 执行结果
        """
        if exec_res.get("success", False):
            # 更新共享存储
            shared["formatted_content"] = exec_res["formatted_content"]
            shared["output_files"] = exec_res["output_files"]
            shared["output_dir"] = exec_res["output_dir"]
            shared["output_format"] = exec_res["output_format"]

            log_and_notify(f"格式化输出完成，生成了 {len(exec_res['output_files'])} 个文件", "info", notify=True)
            return "default"
        elif "error" in exec_res:
            shared["error"] = exec_res["error"]
            log_and_notify(f"格式化输出失败: {exec_res['error']}", "error", notify=True)
            return "error"

        # 默认返回
        return "default"

    def _extract_section(self, content: str, section_names: List[str], flags: int = re.MULTILINE | re.DOTALL) -> str:
        """从内容中提取指定部分

        Args:
            content: 内容
            section_names: 部分名称列表
            flags: 正则表达式标志

        Returns:
            提取的内容
        """
        pattern = r"##\s+(?:" + "|".join(section_names) + r")(.+?)(?=##\s+|$)"
        match = re.search(pattern, content, flags)
        return match.group(1).strip() if match else ""

    def _initialize_content_dict(self) -> Dict[str, str]:
        """初始化内容字典

        Returns:
            初始化的内容字典
        """
        return {
            "title": "代码库文档",
            "introduction": "",
            "architecture": "",
            "core_modules": "",
            "examples": "",
            "faq": "",
            "references": "",
            "repo_name": "requests",  # 默认使用requests作为仓库名称
            "overall_architecture": "",  # 整体架构
            "core_modules_summary": "",  # 核心模块概述
            "glossary": "",  # 术语表
            "evolution_narrative": "",  # 演变历史
        }

    def _extract_title(self, content: str) -> str:
        """提取标题

        Args:
            content: 内容

        Returns:
            标题
        """
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        return title_match.group(1) if title_match else "代码库文档"

    def _check_empty_content(self, content_dict: Dict[str, str], content: str) -> Dict[str, str]:
        """检查内容是否为空，如果为空则使用整个内容

        Args:
            content_dict: 内容字典
            content: 原始内容

        Returns:
            更新后的内容字典
        """
        if not any(
            [
                content_dict["introduction"],
                content_dict["architecture"],
                content_dict["core_modules"],
                content_dict["examples"],
                content_dict["glossary"],
                content_dict["evolution_narrative"],
            ]
        ):
            # 将整个内容作为架构文档
            content_dict["overall_architecture"] = content

        return content_dict

    def _parse_content(self, content: str) -> Dict[str, Any]:
        """解析内容为结构化数据

        Args:
            content: 内容

        Returns:
            结构化数据
        """
        # 初始化结构化数据
        content_dict = self._initialize_content_dict()

        # 提取标题
        content_dict["title"] = self._extract_title(content)

        # 提取各个部分
        content_dict["introduction"] = self._extract_section(content, ["简介", "介绍", "概述"])

        # 提取架构
        architecture = self._extract_section(content, ["架构", "系统架构", "设计"])
        content_dict["architecture"] = architecture
        content_dict["overall_architecture"] = architecture

        # 提取核心模块
        core_modules = self._extract_section(content, ["核心模块", "模块", "组件"])
        content_dict["core_modules"] = core_modules
        content_dict["core_modules_summary"] = core_modules

        # 提取示例
        content_dict["examples"] = self._extract_section(content, ["示例", "使用示例", "用法"])

        # 提取常见问题
        content_dict["faq"] = self._extract_section(content, ["常见问题", "FAQ", "问题"])

        # 提取参考资料
        content_dict["references"] = self._extract_section(content, ["参考资料", "参考", "引用"])

        # 提取术语表
        content_dict["glossary"] = self._extract_section(content, ["术语表", "术语", "名词解释"])

        # 提取演变历史
        content_dict["evolution_narrative"] = self._extract_section(content, ["演变历史", "历史", "发展历程"])

        # 如果内容为空，尝试直接使用整个内容
        return self._check_empty_content(content_dict, content)

    def _merge_generated_content(self, shared: Dict[str, Any], content_dict: Dict[str, Any]) -> None:
        """从共享存储中合并已生成的文档内容

        Args:
            shared: 共享存储
            content_dict: 内容字典
        """
        # 打印共享存储中的键，帮助调试
        print(f"共享存储中的键: {list(shared.keys())}")

        # 合并整体架构文档
        if "overall_architecture" in shared and shared["overall_architecture"].get("success", False):
            content_dict["overall_architecture"] = shared["overall_architecture"].get("content", "")
            content_dict["architecture"] = shared["overall_architecture"].get("content", "")
            print(f"合并了整体架构文档，长度: {len(content_dict['overall_architecture'])}")
        else:
            # 尝试从文件中读取
            try:
                output_dir = shared.get("output_dir", "docs_output")
                repo_name = shared.get("repo_name", "requests")
                file_path = os.path.join(output_dir, repo_name, "overall_architecture.md")
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        content_dict["overall_architecture"] = content
                        content_dict["architecture"] = content
                        print(f"从文件读取了整体架构文档，长度: {len(content)}")
            except Exception as e:
                print(f"读取整体架构文档失败: {str(e)}")

        # 合并术语表文档
        if "glossary" in shared and shared["glossary"].get("success", False):
            content_dict["glossary"] = shared["glossary"].get("content", "")
            print(f"合并了术语表文档，长度: {len(content_dict['glossary'])}")
        else:
            # 尝试从文件中读取
            try:
                output_dir = shared.get("output_dir", "docs_output")
                repo_name = shared.get("repo_name", "requests")
                file_path = os.path.join(output_dir, repo_name, "glossary.md")
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        content_dict["glossary"] = content
                        print(f"从文件读取了术语表文档，长度: {len(content)}")
            except Exception as e:
                print(f"读取术语表文档失败: {str(e)}")

        # 合并时间线文档
        if "timeline" in shared and shared["timeline"].get("success", False):
            content_dict["evolution_narrative"] = shared["timeline"].get("content", "")
            print(f"合并了时间线文档，长度: {len(content_dict['evolution_narrative'])}")
        else:
            # 尝试从文件中读取
            try:
                output_dir = shared.get("output_dir", "docs_output")
                repo_name = shared.get("repo_name", "requests")
                file_path = os.path.join(output_dir, repo_name, "timeline.md")
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        content_dict["evolution_narrative"] = content
                        print(f"从文件读取了时间线文档，长度: {len(content)}")
            except Exception as e:
                print(f"读取时间线文档失败: {str(e)}")

        # 合并速览文档
        if "quick_look" in shared and shared["quick_look"].get("success", False):
            content_dict["introduction"] = shared["quick_look"].get("content", "")
            print(f"合并了速览文档，长度: {len(content_dict['introduction'])}")
        else:
            # 尝试从文件中读取
            try:
                output_dir = shared.get("output_dir", "docs_output")
                repo_name = shared.get("repo_name", "requests")
                file_path = os.path.join(output_dir, repo_name, "quick_look.md")
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        content_dict["introduction"] = content
                        print(f"从文件读取了速览文档，长度: {len(content)}")
            except Exception as e:
                print(f"读取速览文档失败: {str(e)}")

        # 合并依赖关系文档
        if "dependency" in shared and shared["dependency"].get("success", False):
            content_dict["dependencies"] = shared["dependency"].get("content", "")
            print(f"合并了依赖关系文档，长度: {len(content_dict['dependencies'])}")
        else:
            # 尝试从文件中读取
            try:
                output_dir = shared.get("output_dir", "docs_output")
                repo_name = shared.get("repo_name", "requests")
                file_path = os.path.join(output_dir, repo_name, "dependency.md")
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        content_dict["dependencies"] = content
                        print(f"从文件读取了依赖关系文档，长度: {len(content)}")
            except Exception as e:
                print(f"读取依赖关系文档失败: {str(e)}")

        # 合并API文档
        if "api_docs" in shared and shared["api_docs"].get("success", False):
            content_dict["api"] = shared["api_docs"].get("content", "")
            print(f"合并了API文档，长度: {len(content_dict['api'])}")
        else:
            # 尝试从文件中读取
            try:
                output_dir = shared.get("output_dir", "docs_output")
                repo_name = shared.get("repo_name", "requests")
                file_path = os.path.join(output_dir, repo_name, "api.md")
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        content_dict["api"] = content
                        print(f"从文件读取了API文档，长度: {len(content)}")
            except Exception as e:
                print(f"读取API文档失败: {str(e)}")

        # 合并模块详情文档
        if "module_details" in shared and shared["module_details"].get("success", False):
            module_docs = shared["module_details"].get("docs", [])
            if module_docs:
                content_dict["modules"] = module_docs
                # 提取核心模块概述
                core_modules_summary = []
                for module_doc in module_docs:
                    if "name" in module_doc and "description" in module_doc:
                        core_modules_summary.append(f"- **{module_doc['name']}**: {module_doc['description']}")
                if core_modules_summary:
                    content_dict["core_modules"] = "\n".join(core_modules_summary)
                    content_dict["core_modules_summary"] = "\n".join(core_modules_summary)
                    print(f"合并了模块详情文档，模块数: {len(module_docs)}")
        else:
            # 尝试从文件中读取模块索引
            try:
                output_dir = shared.get("output_dir", "docs_output")
                repo_name = shared.get("repo_name", "requests")
                file_path = os.path.join(output_dir, repo_name, "modules", "index.md")
                if os.path.exists(file_path):
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        # 提取模块列表
                        module_matches = re.findall(
                            r"\| ([^\|]+) \| `([^\`]+)` \| \[([^\]]+)\]\(([^\)]+)\) \|", content
                        )
                        if module_matches:
                            module_docs = []
                            core_modules_summary = []
                            for module_name, module_path, doc_title, doc_link in module_matches:
                                module_doc = {
                                    "name": module_name.strip(),
                                    "path": module_path.strip(),
                                    "description": f"查看 {doc_title.strip()} 文档",
                                }
                                module_docs.append(module_doc)
                                core_modules_summary.append(f"- **{module_name.strip()}**: {module_path.strip()}")

                            if module_docs:
                                content_dict["modules"] = module_docs
                                content_dict["core_modules"] = "\n".join(core_modules_summary)
                                content_dict["core_modules_summary"] = "\n".join(core_modules_summary)
                                print(f"从文件读取了模块索引，模块数: {len(module_docs)}")
            except Exception as e:
                print(f"读取模块索引失败: {str(e)}")

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
