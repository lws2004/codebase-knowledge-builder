"""Git 历史分析器，用于分析 Git 仓库的提交历史。"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from git import Repo

from ..logger import log_and_notify


class GitHistoryAnalyzer:
    """Git 历史分析器，用于分析 Git 仓库的提交历史"""

    def __init__(self, repo_path: str):
        """初始化 Git 历史分析器

        Args:
            repo_path: Git 仓库路径
        """
        self.repo_path = repo_path
        try:
            self.repo = Repo(repo_path)
            log_and_notify(f"初始化 Git 历史分析器: {repo_path}", "info")
        except Exception as e:
            log_and_notify(f"初始化 Git 历史分析器失败: {str(e)}", "error", notify=True)
            self.repo = None

    def get_commit_history(self, max_count: int = 100, branch: str = "main") -> List[Dict[str, Any]]:
        """获取提交历史

        Args:
            max_count: 最大提交数量
            branch: 分支名称

        Returns:
            提交历史列表
        """
        if self.repo is None:
            log_and_notify("仓库未初始化，无法获取提交历史", "error")
            return []

        try:
            log_and_notify(f"获取分支 {branch} 的提交历史，最大数量: {max_count}", "info")
            commits = list(self.repo.iter_commits(branch, max_count=max_count))

            history = []
            for commit in commits:
                history.append({
                    "hash": commit.hexsha,
                    "short_hash": commit.hexsha[:7],
                    "author": f"{commit.author.name} <{commit.author.email}>",
                    "date": datetime.fromtimestamp(commit.committed_date).isoformat(),
                    "message": commit.message.strip(),
                    "stats": {
                        "files": len(commit.stats.files),
                        "insertions": commit.stats.total["insertions"],
                        "deletions": commit.stats.total["deletions"],
                    }
                })

            return history
        except Exception as e:
            log_and_notify(f"获取提交历史失败: {str(e)}", "error")
            return []

    def get_commit_details(self, commit_hash: str) -> Optional[Dict[str, Any]]:
        """获取提交详情

        Args:
            commit_hash: 提交哈希

        Returns:
            提交详情，如果提交不存在则返回 None
        """
        if self.repo is None:
            log_and_notify("仓库未初始化，无法获取提交详情", "error")
            return None

        try:
            commit = self.repo.commit(commit_hash)
            log_and_notify(f"获取提交详情: {commit_hash[:7]}", "info")

            # 获取文件变更
            file_changes = []
            for file_path, stats in commit.stats.files.items():
                file_changes.append({
                    "path": file_path,
                    "insertions": stats["insertions"],
                    "deletions": stats["deletions"],
                    "changes": stats["lines"],
                })

            return {
                "hash": commit.hexsha,
                "short_hash": commit.hexsha[:7],
                "author": f"{commit.author.name} <{commit.author.email}>",
                "date": datetime.fromtimestamp(commit.committed_date).isoformat(),
                "message": commit.message.strip(),
                "stats": {
                    "files": len(commit.stats.files),
                    "insertions": commit.stats.total["insertions"],
                    "deletions": commit.stats.total["deletions"],
                },
                "file_changes": file_changes,
            }
        except Exception as e:
            log_and_notify(f"获取提交详情失败: {str(e)}", "error")
            return None

    def get_file_history(self, file_path: str, max_count: int = 50) -> List[Dict[str, Any]]:
        """获取文件的提交历史

        Args:
            file_path: 文件路径
            max_count: 最大提交数量

        Returns:
            文件的提交历史列表
        """
        if self.repo is None:
            log_and_notify("仓库未初始化，无法获取文件历史", "error")
            return []

        try:
            log_and_notify(f"获取文件历史: {file_path}，最大数量: {max_count}", "info")

            # 获取文件的提交历史
            commits = list(self.repo.iter_commits(paths=file_path, max_count=max_count))

            history = []
            for commit in commits:
                history.append({
                    "hash": commit.hexsha,
                    "short_hash": commit.hexsha[:7],
                    "author": f"{commit.author.name} <{commit.author.email}>",
                    "date": datetime.fromtimestamp(commit.committed_date).isoformat(),
                    "message": commit.message.strip(),
                })

            return history
        except Exception as e:
            log_and_notify(f"获取文件历史失败: {str(e)}", "error")
            return []

    def analyze_contributors(self) -> List[Dict[str, Any]]:
        """分析贡献者信息

        Returns:
            贡献者信息列表
        """
        if self.repo is None:
            log_and_notify("仓库未初始化，无法分析贡献者", "error")
            return []

        try:
            log_and_notify("分析仓库贡献者", "info")

            # 使用 Git 命令获取贡献者信息
            shortlog = self.repo.git.shortlog("-sne", "--all")

            contributors = []
            for line in shortlog.splitlines():
                parts = line.strip().split("\t")
                if len(parts) == 2:
                    commits = int(parts[0].strip())
                    author_info = parts[1].strip()

                    # 解析作者信息
                    name = author_info
                    email = ""
                    if "<" in author_info and ">" in author_info:
                        name = author_info.split("<")[0].strip()
                        email = author_info.split("<")[1].split(">")[0].strip()

                    contributors.append({
                        "name": name,
                        "email": email,
                        "commits": commits,
                    })

            return contributors
        except Exception as e:
            log_and_notify(f"分析贡献者失败: {str(e)}", "error")
            return []
