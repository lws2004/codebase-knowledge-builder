"""准备 RAG 数据节点，用于准备检索增强生成 (RAG) 数据。"""

import asyncio
import os
from typing import Any, Dict, List, Optional

from pocketflow import AsyncNode
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


class AsyncPrepareRAGDataNode(AsyncNode):
    """准备 RAG 数据节点（异步），用于准备检索增强生成 (RAG) 数据"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化准备 RAG 数据节点 (异步)

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
        log_and_notify("初始化 AsyncPrepareRAGDataNode", "info")

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取代码结构和仓库路径

        Args:
            shared: 共享存储

        Returns:
            包含代码结构和仓库路径的字典
        """
        log_and_notify("AsyncPrepareRAGDataNode: 准备阶段开始", "info")

        # 从共享存储中获取代码结构
        code_structure = shared.get("code_structure")
        if not code_structure or not code_structure.get("success", False):
            error_msg = "共享存储中缺少有效代码结构 (AsyncPrepareRAGDataNode)"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 从共享存储中获取仓库路径
        repo_path = shared.get("repo_path")
        if not repo_path or not os.path.exists(repo_path):
            error_msg = f"仓库路径无效或不存在: {repo_path}"
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

    async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，异步准备 RAG 数据

        Args:
            prep_res: 准备阶段的结果

        Returns:
            RAG 数据
        """
        log_and_notify("AsyncPrepareRAGDataNode: 执行阶段开始", "info")

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

            if not files:
                log_and_notify("AsyncPrepareRAGDataNode: 未找到符合条件的文件进行处理", "warning")
                return {"files": [], "file_contents": {}, "chunks": [], "success": True}

            log_and_notify(f"AsyncPrepareRAGDataNode: 将异步读取 {len(files)} 个文件", "info")
            file_contents = await self._read_files_async(repo_path, files)

            # 分块文件内容
            chunks = self._chunk_files(file_contents, max_chunk_size, chunk_overlap)

            log_and_notify(
                f"AsyncPrepareRAGDataNode: RAG 数据准备完成: {len(files)} 个文件, {len(chunks)} 个块", "info"
            )

            return {"files": files, "file_contents": file_contents, "chunks": chunks, "success": True}
        except Exception as e:
            error_msg = f"AsyncPrepareRAGDataNode: 准备 RAG 数据失败: {str(e)}"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg, "success": False}

    async def post_async(self, shared: Dict[str, Any], _: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将 RAG 数据存储到共享存储中

        Args:
            shared: 共享存储
            _: 准备阶段的结果（未使用）
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        log_and_notify("AsyncPrepareRAGDataNode: 后处理阶段开始", "info")

        # 检查执行阶段是否出错
        if not exec_res.get("success", False):
            error_msg = exec_res.get("error", "AsyncPrepareRAGDataNode: 未知执行错误")
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
            f"AsyncPrepareRAGDataNode: RAG 数据已存入共享存储. "
            f"文件: {len(exec_res.get('files', []))}, 块: {len(exec_res.get('chunks', []))}",
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
        for file_path, _ in all_files.items():
            # 检查文件扩展名
            ext = file_path.split(".")[-1].lower() if "." in file_path else ""

            if ext in exclude_extensions:
                continue

            if include_extensions and ext not in include_extensions:
                continue

            files.append(file_path)

            # 检查是否达到最大文件数
            if len(files) >= max_files:
                log_and_notify(f"AsyncPrepareRAGDataNode: 达到最大文件数 {max_files}，停止获取文件。", "warning")
                break

        return files

    async def _read_files_async(self, repo_path: str, files: List[str]) -> Dict[str, str]:
        """异步读取文件内容，使用 Pocket Flow 风格的并发实现

        Args:
            repo_path: 仓库路径
            files: 文件列表

        Returns:
            文件内容字典 {file_path: content}
        """
        from .async_parallel_flow import AsyncParallelBatchFlow

        # 创建一个处理单个文件的异步节点
        class FileReader(AsyncNode):
            def __init__(self, parent_node: AsyncPrepareRAGDataNode, repo_path: str):
                super().__init__()
                self.parent_node = parent_node
                self.repo_path = repo_path

            async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
                # 从 shared 中获取文件路径
                return shared

            async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
                # 读取单个文件
                file_path = prep_res["file_path"]
                full_path = os.path.join(self.repo_path, file_path)

                try:
                    # 使用 asyncio.to_thread 在单独的线程中运行同步文件读取
                    content = await asyncio.to_thread(self.parent_node._read_sync, full_path)
                    return {"file_path": file_path, "content": content, "success": True}
                except FileNotFoundError:
                    log_and_notify(f"AsyncPrepareRAGDataNode: 文件未找到: {full_path}", "warning")
                    return {"file_path": file_path, "success": False, "error": "file_not_found"}
                except Exception as e:
                    log_and_notify(f"AsyncPrepareRAGDataNode: 读取文件时出错 {full_path}: {e}", "error")
                    return {"file_path": file_path, "success": False, "error": str(e)}

            async def post_async(
                self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]
            ) -> str:
                # 直接返回 "default"，结果已经在 exec_res 中
                return "default"

        # 为每个文件创建参数字典
        file_params = [{"file_path": file_path} for file_path in files]

        # 创建并行批处理流程
        batch_flow = AsyncParallelBatchFlow(flow=FileReader(self, repo_path))

        # 执行批处理
        results = await batch_flow.exec_async(file_params)

        # 处理结果
        file_contents = {}
        for result in results:
            if isinstance(result, dict) and result.get("success", False):
                file_path = result.get("file_path")
                content = result.get("content")
                if file_path and content is not None:
                    file_contents[file_path] = content

        return file_contents

    # Synchronous helper function for reading file content, to be used with to_thread
    def _read_sync(self, full_path: str) -> str:
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception:
            # Let the caller handle logging if needed, or re-raise
            # log_and_notify(f"Sync read failed for {full_path}: {e}", "error")
            # Avoid double logging if called from async wrapper
            raise  # Re-raise exception to be caught by the async wrapper

    def _chunk_files(
        self, file_contents: Dict[str, str], max_chunk_size: int, chunk_overlap: int
    ) -> List[Dict[str, Any]]:
        """分块文件内容

        Args:
            file_contents: 文件内容字典
            max_chunk_size: 最大块大小
            chunk_overlap: 块重叠大小

        Returns:
            块列表
        """
        chunks = []

        for file_path, content in file_contents.items():
            if not isinstance(content, str):  # Skip if read failed and content is not string
                log_and_notify(f"AsyncPrepareRAGDataNode: 跳过分块，文件内容不是字符串: {file_path}", "warning")
                continue
            if not content.strip():  # Skip empty files
                log_and_notify(f"AsyncPrepareRAGDataNode: 跳过分块，文件内容为空: {file_path}", "debug")
                continue

            start = 0
            while start < len(content):
                end = start + max_chunk_size
                chunk_text = content[start:end]
                chunks.append({"file_path": file_path, "text": chunk_text, "start_index": start})

                next_start = start + max_chunk_size - chunk_overlap
                # If overlap is large or chunk is small, ensure we make progress
                if next_start <= start:
                    start += max_chunk_size  # Move past the current chunk if overlap logic fails
                else:
                    start = next_start

                # Break if we are past the content length (or very close)
                if start >= len(content):
                    break

        return chunks
