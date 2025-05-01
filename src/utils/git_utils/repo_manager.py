"""Git 仓库管理器，提供 Git 仓库的基本操作。"""
import os
import shutil
import tempfile
from typing import List, Optional

from git import GitCommandError, Repo

from ..logger import log_and_notify


class GitRepoManager:
    """Git 仓库管理器，提供 Git 仓库的基本操作"""

    def __init__(self, repo_url: str, local_path: Optional[str] = None, branch: str = "main"):
        """初始化 Git 仓库管理器

        Args:
            repo_url: Git 仓库 URL
            local_path: 本地仓库路径，如果为 None 则使用临时目录
            branch: 要检出的分支
        """
        self.repo_url = repo_url
        self.branch = branch
        self.temp_dir = None

        # 如果未提供本地路径，创建临时目录
        if local_path is None:
            self.temp_dir = tempfile.mkdtemp(prefix="git_repo_")
            self.local_path = self.temp_dir
        else:
            self.local_path = local_path

        self.repo = None
        log_and_notify(f"初始化 Git 仓库管理器: {repo_url} -> {self.local_path}", "info")

    def clone(self) -> bool:
        """克隆仓库到本地

        Returns:
            是否成功克隆
        """
        try:
            if os.path.exists(os.path.join(self.local_path, ".git")):
                log_and_notify(f"仓库已存在于 {self.local_path}，打开现有仓库", "info")
                self.repo = Repo(self.local_path)
                return True

            log_and_notify(f"克隆仓库 {self.repo_url} 到 {self.local_path}", "info")
            self.repo = Repo.clone_from(self.repo_url, self.local_path, branch=self.branch)
            return True
        except GitCommandError as e:
            log_and_notify(f"克隆仓库失败: {str(e)}", "error", notify=True)
            return False

    def checkout(self, branch: str) -> bool:
        """检出指定分支

        Args:
            branch: 分支名称

        Returns:
            是否成功检出
        """
        if self.repo is None:
            log_and_notify("仓库未初始化，无法检出分支", "error")
            return False

        try:
            log_and_notify(f"检出分支: {branch}", "info")
            self.repo.git.checkout(branch)
            self.branch = branch
            return True
        except GitCommandError as e:
            log_and_notify(f"检出分支失败: {str(e)}", "error")
            return False

    def get_file_content(self, file_path: str, ref: str = "HEAD") -> Optional[str]:
        """获取指定文件的内容

        Args:
            file_path: 文件路径
            ref: Git 引用，默认为 HEAD

        Returns:
            文件内容，如果文件不存在则返回 None
        """
        if self.repo is None:
            log_and_notify("仓库未初始化，无法获取文件内容", "error")
            return None

        try:
            return self.repo.git.show(f"{ref}:{file_path}")
        except GitCommandError:
            return None

    def get_file_list(self, path: str = ".", ref: str = "HEAD") -> List[str]:
        """获取指定路径下的文件列表

        Args:
            path: 相对路径，默认为仓库根目录
            ref: Git 引用，默认为 HEAD

        Returns:
            文件路径列表
        """
        if self.repo is None:
            log_and_notify("仓库未初始化，无法获取文件列表", "error")
            return []

        try:
            # 获取指定引用的文件列表
            if path == "":
                path = "."
            files = self.repo.git.ls_tree("-r", "--name-only", ref, path).splitlines()
            return [f for f in files if path == "." or f.startswith(path)]
        except GitCommandError as e:
            log_and_notify(f"获取文件列表失败: {str(e)}", "error")
            return []

    def cleanup(self) -> None:
        """清理临时目录"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            log_and_notify(f"清理临时目录: {self.temp_dir}", "info")
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None
            self.repo = None
