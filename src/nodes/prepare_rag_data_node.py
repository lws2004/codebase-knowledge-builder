"""准备 RAG 数据节点，用于准备检索增强生成 (RAG) 数据。"""

import os
from typing import Any, Dict, List, Optional

from pocketflow import Node
from pydantic import BaseModel, Field

from ..utils.logger import log_and_notify


class PrepareRAGDataNodeConfig(BaseModel):
    """PrepareRAGDataNode 配置"""

    max_chunk_size: int = Field(1000, description="最大块大小")
    chunk_overlap: int = Field(200, description="块重叠大小")
    max_files: int = Field(100, description="最大处理文件数")
    exclude_extensions: List[str] = Field(
        ["jpg", "jpeg", "png", "gif", "svg", "ico", "pdf", "zip", "tar", "gz"], description="排除的文件扩展名"
    )
    include_extensions: List[str] = Field(
        [
            "py",
            "js",
            "ts",
            "java",
            "c",
            "cpp",
            "h",
            "hpp",
            "cs",
            "go",
            "rs",
            "md",
            "txt",
            "json",
            "yml",
            "yaml",
            "toml",
        ],
        description="包含的文件扩展名",
    )


class PrepareRAGDataNode(Node):
    """准备 RAG 数据节点，用于准备检索增强生成 (RAG) 数据"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化准备 RAG 数据节点

        Args:
            config: 节点配置
        """
        super().__init__()

        # 从配置文件获取默认配置
        from ..utils.env_manager import get_node_config

        default_config = get_node_config("prepare_rag_data")

        # 合并配置
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)

        self.config = PrepareRAGDataNodeConfig(**merged_config)
        log_and_notify("初始化准备 RAG 数据节点", "info")

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取代码结构和仓库路径

        Args:
            shared: 共享存储

        Returns:
            包含代码结构和仓库路径的字典
        """
        log_and_notify("PrepareRAGDataNode: 准备阶段开始", "info")

        # 从共享存储中获取代码结构
        code_structure = shared.get("code_structure")
        if not code_structure:
            error_msg = "共享存储中缺少代码结构"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 检查代码结构是否有效
        if not code_structure.get("success", False):
            error_msg = "代码结构无效"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 从共享存储中获取仓库路径
        repo_path = shared.get("repo_path")
        if not repo_path:
            error_msg = "共享存储中缺少仓库路径"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 检查仓库路径是否存在
        if not os.path.exists(repo_path):
            error_msg = f"仓库路径不存在: {repo_path}"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        return {
            "code_structure": code_structure,
            "repo_path": repo_path,
            "max_chunk_size": self.config.max_chunk_size,
            "chunk_overlap": self.config.chunk_overlap,
            "max_files": self.config.max_files,
            "exclude_extensions": self.config.exclude_extensions,
            "include_extensions": self.config.include_extensions,
        }

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，准备 RAG 数据

        Args:
            prep_res: 准备阶段的结果

        Returns:
            RAG 数据
        """
        log_and_notify("PrepareRAGDataNode: 执行阶段开始", "info")

        # 检查准备阶段是否出错
        if "error" in prep_res:
            return {"error": prep_res["error"], "success": False}

        code_structure = prep_res["code_structure"]
        repo_path = prep_res["repo_path"]
        max_chunk_size = prep_res["max_chunk_size"]
        chunk_overlap = prep_res["chunk_overlap"]
        max_files = prep_res["max_files"]
        exclude_extensions = prep_res["exclude_extensions"]
        include_extensions = prep_res["include_extensions"]

        try:
            # 获取文件列表
            files = self._get_files(code_structure, include_extensions, exclude_extensions, max_files)

            # 读取文件内容
            file_contents = self._read_files(repo_path, files)

            # 分块文件内容
            chunks = self._chunk_files(file_contents, max_chunk_size, chunk_overlap)

            log_and_notify(f"准备 RAG 数据完成: {len(files)} 个文件, {len(chunks)} 个块", "info")

            return {"files": files, "file_contents": file_contents, "chunks": chunks, "success": True}
        except Exception as e:
            error_msg = f"准备 RAG 数据失败: {str(e)}"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg, "success": False}

    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将 RAG 数据存储到共享存储中

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        log_and_notify("PrepareRAGDataNode: 后处理阶段开始", "info")

        # 检查执行阶段是否出错
        if not exec_res.get("success", False):
            error_msg = exec_res.get("error", "未知错误")
            log_and_notify(f"准备 RAG 数据失败: {error_msg}", "error", notify=True)
            shared["rag_data"] = {"error": error_msg, "success": False}
            return "error"

        # 将 RAG 数据存储到共享存储中
        shared["rag_data"] = {
            "files": exec_res.get("files", []),
            "file_contents": exec_res.get("file_contents", {}),
            "chunks": exec_res.get("chunks", []),
            "success": True,
        }

        log_and_notify(
            f"准备 RAG 数据完成，处理了 {len(exec_res.get('files', []))} 个文件，"
            f"生成了 {len(exec_res.get('chunks', []))} 个块",
            "info",
            notify=True,
        )

        return "default"

    def _get_files(
        self,
        code_structure: Dict[str, Any],
        include_extensions: List[str],
        exclude_extensions: List[str],
        max_files: int,
    ) -> List[str]:
        """获取文件列表

        Args:
            code_structure: 代码结构
            include_extensions: 包含的文件扩展名
            exclude_extensions: 排除的文件扩展名
            max_files: 最大文件数

        Returns:
            文件列表
        """
        files = []

        # 从代码结构中获取文件
        all_files = code_structure.get("files", {})

        # 过滤文件
        for file_path, file_info in all_files.items():
            # 检查文件扩展名
            ext = file_path.split(".")[-1].lower() if "." in file_path else ""

            if ext in exclude_extensions:
                continue

            if include_extensions and ext not in include_extensions:
                continue

            files.append(file_path)

            # 检查是否达到最大文件数
            if len(files) >= max_files:
                break

        return files

    def _read_files(self, repo_path: str, files: List[str]) -> Dict[str, str]:
        """读取文件内容

        Args:
            repo_path: 仓库路径
            files: 文件列表

        Returns:
            文件内容
        """
        file_contents = {}

        for file_path in files:
            try:
                full_path = os.path.join(repo_path, file_path)

                # 检查文件是否存在
                if not os.path.exists(full_path):
                    log_and_notify(f"文件不存在: {full_path}", "warning")
                    continue

                # 读取文件内容
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                file_contents[file_path] = content
            except Exception as e:
                log_and_notify(f"读取文件失败: {file_path}, 错误: {str(e)}", "warning")

        return file_contents

    def _chunk_files(
        self, file_contents: Dict[str, str], max_chunk_size: int, chunk_overlap: int
    ) -> List[Dict[str, Any]]:
        """分块文件内容

        Args:
            file_contents: 文件内容
            max_chunk_size: 最大块大小
            chunk_overlap: 块重叠大小

        Returns:
            块列表
        """
        chunks = []

        for file_path, content in file_contents.items():
            # 简单的按字符分块
            # 注意：实际应用中应该使用更复杂的分块策略，如按段落或语义分块
            if len(content) <= max_chunk_size:
                # 文件内容小于最大块大小，直接作为一个块
                chunks.append({"file_path": file_path, "content": content, "start": 0, "end": len(content)})
            else:
                # 文件内容大于最大块大小，需要分块
                start = 0
                while start < len(content):
                    end = min(start + max_chunk_size, len(content))

                    # 如果不是最后一个块，尝试在一个合适的位置（如换行符）结束
                    if end < len(content):
                        # 从 end 向前查找换行符
                        pos = content.rfind("\n", start, end)
                        if pos > start:
                            end = pos + 1  # 包含换行符

                    chunks.append({"file_path": file_path, "content": content[start:end], "start": start, "end": end})

                    # 更新起始位置，考虑重叠
                    start = max(start + 1, end - chunk_overlap)

        return chunks
