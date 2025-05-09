"""Git 历史分析节点，用于分析 Git 仓库的提交历史。"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional, cast

from pocketflow import AsyncNode
from pydantic import BaseModel, Field

from ..utils.git_utils import GitHistoryAnalyzer
from ..utils.llm_wrapper import LLMClient
from ..utils.logger import log_and_notify


class AnalyzeHistoryNodeConfig(BaseModel):
    """AnalyzeHistoryNode 配置"""

    max_commits: int = Field(100, description="最大分析的提交数量")
    include_file_history: bool = Field(True, description="是否包含文件历史")
    analyze_contributors: bool = Field(True, description="是否分析贡献者")
    summary_prompt_template: str = Field(
        """
        你是一个代码库历史分析专家。请分析以下 Git 提交历史，并提供一个全面的总结。

        提交历史:
        {commit_history}

        贡献者信息:
        {contributors}

        请提供以下内容:
        1. 代码库的总体发展历程和主要里程碑
        2. 主要贡献者及其贡献领域
        3. 代码库的主要模块和组件（基于提交信息推断）
        4. 代码库的开发模式和协作方式
        5. 任何其他有价值的见解

        请以 Markdown 格式输出，使用适当的标题、列表和强调。
        """,
        description="历史总结提示模板",
    )


class AsyncAnalyzeHistoryNode(AsyncNode):
    """Git 历史分析节点（异步），用于分析 Git 仓库的提交历史"""

    llm_client: Optional[LLMClient] = None

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化 Git 历史分析节点 (异步)

        Args:
            config: 节点配置
        """
        super().__init__()
        from ..utils.env_manager import get_node_config

        default_config = get_node_config("analyze_history")
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)
        self.config = AnalyzeHistoryNodeConfig(**merged_config)
        log_and_notify("初始化 AsyncAnalyzeHistoryNode", "info")

    async def prep_async(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取仓库路径

        Args:
            shared: 共享存储

        Returns:
            包含仓库路径的字典
        """
        log_and_notify("AsyncAnalyzeHistoryNode: 准备阶段开始", "info")

        repo_path = shared.get("repo_path")
        if not repo_path:
            error_msg = "共享存储中缺少仓库路径"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        if not os.path.exists(repo_path):
            error_msg = f"仓库路径不存在: {repo_path}"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        if not os.path.exists(os.path.join(repo_path, ".git")):
            error_msg = f"路径不是 Git 仓库: {repo_path}"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        branch = shared.get("branch", "main")
        llm_config_shared = shared.get("llm_config")  # Get config, might be None

        if llm_config_shared:  # Proceed only if llm_config exists in shared
            try:
                self.llm_client = LLMClient(config=llm_config_shared)
                log_and_notify("AsyncAnalyzeHistoryNode: LLMClient initialized for history summary.", "info")
            except Exception as e:
                log_and_notify(
                    f"AsyncAnalyzeHistoryNode: LLMClient initialization failed: {e}. Summarization will be skipped.",
                    "warning",
                )
                self.llm_client = None  # Ensure it's None if init fails
        else:
            log_and_notify(
                "AsyncAnalyzeHistoryNode: No LLM config in shared state. History summarization will be skipped.", "info"
            )
            self.llm_client = None

        return {
            "repo_path": repo_path,
            "branch": branch,
            # "llm_config" is no longer directly passed if client is instance var
            "max_commits": self.config.max_commits,
            "include_file_history": self.config.include_file_history,
            "analyze_contributors": self.config.analyze_contributors,
            "target_language": shared.get("language", "zh"),  # For summary prompt
        }

    async def exec_async(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，异步分析 Git 仓库历史

        Args:
            prep_res: 准备阶段的结果

        Returns:
            分析结果
        """
        log_and_notify("AsyncAnalyzeHistoryNode: 执行阶段开始", "info")

        if "error" in prep_res:
            return {"error": prep_res["error"], "success": False}

        repo_path = prep_res["repo_path"]
        branch = prep_res["branch"]
        max_commits = prep_res["max_commits"]
        include_file_history = prep_res["include_file_history"]
        analyze_contributors = prep_res["analyze_contributors"]
        target_language = prep_res["target_language"]

        try:
            analyzer = GitHistoryAnalyzer(repo_path)

            log_and_notify(f"AsyncAnalyzeHistoryNode: 开始异步获取提交历史，最大数量: {max_commits}", "info")
            commit_history = await asyncio.to_thread(analyzer.get_commit_history, max_count=max_commits, branch=branch)
            result = {"commit_history": commit_history, "commit_count": len(commit_history), "success": True}

            if analyze_contributors:
                log_and_notify("AsyncAnalyzeHistoryNode: 开始异步分析贡献者", "info")
                contributors = await asyncio.to_thread(analyzer.analyze_contributors)
                result["contributors"] = contributors
                result["contributor_count"] = len(contributors)

            if include_file_history:
                log_and_notify("AsyncAnalyzeHistoryNode: 开始异步获取重要文件的历史", "info")
                important_files = await asyncio.to_thread(
                    self._get_important_files, commit_history
                )  # Assuming _get_important_files might do I/O or be heavy
                file_histories = {}
                file_history_tasks = []
                for file_path in important_files[:10]:  # Limit for performance
                    task = asyncio.to_thread(analyzer.get_file_history, file_path, max_count=20)
                    file_history_tasks.append((file_path, task))

                for file_path, task in file_history_tasks:
                    file_history_detail = await task
                    if file_history_detail:
                        file_histories[file_path] = file_history_detail
                result["file_histories"] = file_histories

            if self.llm_client and commit_history:
                log_and_notify("AsyncAnalyzeHistoryNode: 开始异步使用 LLM 生成历史总结", "info")
                contributors_list = cast(List[Dict[str, Any]], result.get("contributors", []))
                summary = await self._generate_history_summary_async(commit_history, contributors_list, target_language)
                result["history_summary"] = summary

            return result
        except Exception as e:
            error_msg = f"AsyncAnalyzeHistoryNode: 分析 Git 历史失败: {str(e)}"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg, "success": False}

    async def post_async(self, shared: Dict[str, Any], _prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将分析结果存储到共享存储中

        Args:
            shared: 共享存储
            _prep_res: 准备阶段的结果（未使用）
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        # 记录未使用的参数，避免IDE警告
        _ = _prep_res
        log_and_notify("AsyncAnalyzeHistoryNode: 后处理阶段开始", "info")

        if not exec_res.get("success", False):
            error_msg = exec_res.get("error", "AsyncAnalyzeHistoryNode: 未知执行错误")
            log_and_notify(f"Git 历史分析失败: {error_msg}", "error", notify=True)
            shared["history_analysis"] = {"error": error_msg, "success": False}
            return "error"

        shared["history_analysis"] = {
            "commit_count": exec_res.get("commit_count", 0),
            "contributor_count": exec_res.get("contributor_count", 0),
            "first_commit_date": exec_res.get("first_commit_date"),
            "last_commit_date": exec_res.get("last_commit_date"),
            "history_summary": exec_res.get("history_summary", ""),
            "success": True,
        }
        log_and_notify(
            f"AsyncAnalyzeHistoryNode: 历史分析完成并存入共享存储. "
            f"提交: {exec_res.get('commit_count', 0)}, "
            f"贡献者: {exec_res.get('contributor_count', 0)}",
            "info",
            notify=True,
        )
        return "default"

    def _get_important_files(self, commit_history: List[Dict[str, Any]]) -> List[str]:
        """从提交历史中获取重要文件 (同步 helper, called via to_thread if needed)

        Args:
            commit_history: 提交历史
        Returns:
            重要文件列表
        """
        # 从提交消息中提取文件名
        # 这是一个简化的实现，实际上应该更复杂
        file_mentions: Dict[str, int] = {}

        # 从提交消息中提取文件名
        for commit in commit_history:
            if isinstance(commit, dict) and "message" in commit:
                message = commit.get("message", "")
                # 简单地查找可能的文件名（包含.的单词）
                words = message.split()
                for word in words:
                    if "." in word and "/" in word:  # 可能是文件路径
                        # 清理单词，移除标点符号
                        clean_word = word.strip(",.;:()[]{}\"'")
                        if clean_word:
                            file_mentions[clean_word] = file_mentions.get(clean_word, 0) + 1

        # 如果没有从消息中找到文件，返回一些常见的文件名
        if not file_mentions:
            return ["README.md", "setup.py", "requirements.txt", "main.py", "src/main.py"]

        # 按提及频率排序
        sorted_files = sorted(file_mentions.items(), key=lambda item: item[1], reverse=True)
        # 使用下划线表示未使用的变量，避免IDE警告
        return [f_path for f_path, _ in sorted_files][:10]  # 限制为前10个

    async def _generate_history_summary_async(
        self, commit_history: List[Dict[str, Any]], contributors: List[Dict[str, Any]], target_language: str
    ) -> str:
        """使用 LLM 生成历史总结 (异步)

        Args:
            commit_history: 提交历史
            contributors: 贡献者信息
            target_language: 目标语言

        Returns:
            历史总结字符串
        """
        if not self.llm_client:
            log_and_notify("LLMClient未初始化，无法生成历史总结", "error")
            return ""

        # Prepare prompt context
        commit_history_str = json.dumps(commit_history[:20], indent=2)  # Limit history length for prompt
        contributors_str = json.dumps(contributors, indent=2)
        prompt_str = self.config.summary_prompt_template.format(
            commit_history=commit_history_str, contributors=contributors_str
        )

        system_prompt = f"你是一个代码库历史分析专家，请用{target_language}语言回答。"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt_str},
        ]

        try:
            # Use the model configured within self.llm_client
            raw_response = await self.llm_client.acompletion(messages=messages, trace_name="生成历史总结")
            if not raw_response:
                log_and_notify("AsyncAnalyzeHistoryNode: LLM 返回空响应 (历史总结)", "error")
                return ""
            content = self.llm_client.get_completion_content(raw_response)
            return content
        except Exception as e:
            log_and_notify(f"AsyncAnalyzeHistoryNode: 生成历史总结失败: {str(e)}", "error")
            return ""
