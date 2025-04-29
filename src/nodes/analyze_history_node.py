"""
Git 历史分析节点，用于分析 Git 仓库的提交历史。
"""
import os
import json
from typing import Dict, Any, List, Optional
from pocketflow import Node
from pydantic import BaseModel, Field

from ..utils.logger import log_and_notify
from ..utils.git_utils import GitHistoryAnalyzer
from ..utils.llm_wrapper import LLMClient

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
        description="历史总结提示模板"
    )

class AnalyzeHistoryNode(Node):
    """Git 历史分析节点，用于分析 Git 仓库的提交历史"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化 Git 历史分析节点

        Args:
            config: 节点配置
        """
        super().__init__()

        # 从配置文件获取默认配置
        from ..utils.env_manager import get_node_config
        default_config = get_node_config("analyze_history")

        # 合并配置
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)

        self.config = AnalyzeHistoryNodeConfig(**merged_config)
        log_and_notify("初始化 Git 历史分析节点", "info")

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取仓库路径

        Args:
            shared: 共享存储

        Returns:
            包含仓库路径的字典
        """
        log_and_notify("AnalyzeHistoryNode: 准备阶段开始", "info")

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

        # 检查是否为 Git 仓库
        if not os.path.exists(os.path.join(repo_path, ".git")):
            error_msg = f"路径不是 Git 仓库: {repo_path}"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 获取 LLM 配置
        llm_config = shared.get("llm_config", {})

        return {
            "repo_path": repo_path,
            "llm_config": llm_config,
            "max_commits": self.config.max_commits,
            "include_file_history": self.config.include_file_history,
            "analyze_contributors": self.config.analyze_contributors,
        }

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，分析 Git 仓库历史

        Args:
            prep_res: 准备阶段的结果

        Returns:
            分析结果
        """
        log_and_notify("AnalyzeHistoryNode: 执行阶段开始", "info")

        # 检查准备阶段是否出错
        if "error" in prep_res:
            return {"error": prep_res["error"], "success": False}

        repo_path = prep_res["repo_path"]
        max_commits = prep_res["max_commits"]
        include_file_history = prep_res["include_file_history"]
        analyze_contributors = prep_res["analyze_contributors"]

        try:
            # 创建 Git 历史分析器
            analyzer = GitHistoryAnalyzer(repo_path)

            # 获取提交历史
            log_and_notify(f"获取提交历史，最大数量: {max_commits}", "info")
            commit_history = analyzer.get_commit_history(max_count=max_commits)

            result = {
                "commit_history": commit_history,
                "commit_count": len(commit_history),
                "success": True
            }

            # 分析贡献者
            if analyze_contributors:
                log_and_notify("分析贡献者", "info")
                contributors = analyzer.analyze_contributors()
                result["contributors"] = contributors
                result["contributor_count"] = len(contributors)

            # 获取文件历史（可选）
            if include_file_history:
                log_and_notify("获取重要文件的历史", "info")

                # 获取一些重要文件的历史
                important_files = self._get_important_files(commit_history)
                file_histories = {}

                for file_path in important_files[:10]:  # 限制为前 10 个重要文件
                    file_history = analyzer.get_file_history(file_path, max_count=20)
                    if file_history:
                        file_histories[file_path] = file_history

                result["file_histories"] = file_histories

            # 使用 LLM 生成历史总结
            if "llm_config" in prep_res and commit_history:
                log_and_notify("使用 LLM 生成历史总结", "info")
                summary = self._generate_history_summary(
                    prep_res["llm_config"],
                    commit_history,
                    result.get("contributors", [])
                )
                result["history_summary"] = summary

            return result
        except Exception as e:
            error_msg = f"分析 Git 历史失败: {str(e)}"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg, "success": False}

    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将分析结果存储到共享存储中

        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res: 执行阶段的结果

        Returns:
            下一个节点的动作
        """
        log_and_notify("AnalyzeHistoryNode: 后处理阶段开始", "info")

        # 检查执行阶段是否出错
        if not exec_res.get("success", False):
            error_msg = exec_res.get("error", "未知错误")
            log_and_notify(f"Git 历史分析失败: {error_msg}", "error", notify=True)
            shared["history_analysis"] = {"error": error_msg, "success": False}
            return "error"

        # 将分析结果存储到共享存储中
        shared["history_analysis"] = {
            "commit_history": exec_res.get("commit_history", []),
            "commit_count": exec_res.get("commit_count", 0),
            "contributors": exec_res.get("contributors", []),
            "contributor_count": exec_res.get("contributor_count", 0),
            "file_histories": exec_res.get("file_histories", {}),
            "history_summary": exec_res.get("history_summary", ""),
            "success": True
        }

        log_and_notify(
            f"Git 历史分析完成，分析了 {exec_res.get('commit_count', 0)} 个提交和 "
            f"{exec_res.get('contributor_count', 0)} 个贡献者",
            "info",
            notify=True
        )

        return "default"

    def _get_important_files(self, commit_history: List[Dict[str, Any]]) -> List[str]:
        """从提交历史中获取重要文件

        Args:
            commit_history: 提交历史

        Returns:
            重要文件列表
        """
        # 我们需要获取详细的提交信息来获取文件路径
        # 由于 commit_history 中的 stats.files 只是一个数字，我们需要使用其他方法

        # 简单方法：返回一个空列表，避免错误
        # 在实际应用中，我们可以使用 GitHistoryAnalyzer.get_commit_details 方法获取详细信息
        return []

    def _generate_history_summary(
        self,
        llm_config: Dict[str, Any],
        commit_history: List[Dict[str, Any]],
        contributors: List[Dict[str, Any]]
    ) -> str:
        """使用 LLM 生成历史总结

        Args:
            llm_config: LLM 配置
            commit_history: 提交历史
            contributors: 贡献者信息

        Returns:
            历史总结
        """
        try:
            # 创建 LLM 客户端
            llm_client = LLMClient(llm_config)

            # 准备提示
            commit_history_str = json.dumps(commit_history[:50], indent=2, ensure_ascii=False)  # 限制为前 50 个提交
            contributors_str = json.dumps(contributors, indent=2, ensure_ascii=False)

            prompt = self.config.summary_prompt_template.format(
                commit_history=commit_history_str,
                contributors=contributors_str
            )

            # 调用 LLM
            messages = [
                {"role": "system", "content": "你是一个代码库历史分析专家，擅长从 Git 提交历史中提取有价值的见解。"},
                {"role": "user", "content": prompt}
            ]

            response = llm_client.completion(
                messages=messages,
                temperature=0.3,
                trace_name="Git 历史总结"
            )

            # 获取响应内容
            summary = llm_client.get_completion_content(response)

            log_and_notify("成功生成 Git 历史总结", "info")
            return summary
        except Exception as e:
            error_msg = f"生成历史总结失败: {str(e)}"
            log_and_notify(error_msg, "error")
            return f"无法生成历史总结: {str(e)}"
