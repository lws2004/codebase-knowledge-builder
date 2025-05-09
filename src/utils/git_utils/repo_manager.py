"""Git 仓库管理器，提供 Git 仓库的基本操作。"""

import hashlib
import json
import os
import shutil
import tempfile
import time
from typing import List, Optional, cast

from git import GitCommandError, Repo

from ..config_loader import ConfigLoader
from ..logger import log_and_notify


class GitRepoManager:
    """Git 仓库管理器，提供 Git 仓库的基本操作"""

    # 缓存目录
    CACHE_DIR = ".cache/git_repos"
    repo: Optional[Repo]  # 添加类型注解

    def __init__(self, repo_url: str, local_path: Optional[str] = None, branch: str = "main", use_cache: bool = True):
        """初始化 Git 仓库管理器

        Args:
            repo_url: Git 仓库 URL
            local_path: 本地仓库路径，如果为 None 则使用临时目录
            branch: 要检出的分支
            use_cache: 是否使用缓存
        """
        self.repo_url = repo_url
        self.branch = branch
        self.temp_dir = None
        self.use_cache = use_cache

        # 如果未提供本地路径，创建临时目录
        if local_path is None:
            self.temp_dir = tempfile.mkdtemp(prefix="git_repo_")
            self.local_path = self.temp_dir
        else:
            self.local_path = local_path

        # 获取缓存配置
        config_loader = ConfigLoader()
        self.cache_ttl = config_loader.get("git.cache_ttl", 86400)  # 默认24小时

        self.repo = None
        log_and_notify(
            f"初始化 Git 仓库管理器: {repo_url} -> {self.local_path}, 缓存: {'启用' if use_cache else '禁用'}", "info"
        )

    def _get_repo_hash(self) -> str:
        """获取仓库的唯一哈希值，用于缓存标识

        Returns:
            仓库哈希值
        """
        # 使用仓库URL和分支生成唯一哈希
        repo_id = f"{self.repo_url}#{self.branch}"
        return hashlib.md5(repo_id.encode()).hexdigest()

    def _get_cache_path(self) -> str:
        """获取缓存路径

        Returns:
            缓存路径
        """
        # 确保缓存目录存在
        os.makedirs(self.CACHE_DIR, exist_ok=True)

        # 使用仓库哈希作为缓存目录名
        repo_hash = self._get_repo_hash()
        return os.path.join(self.CACHE_DIR, repo_hash)

    def _get_cache_meta_path(self) -> str:
        """获取缓存元数据路径

        Returns:
            缓存元数据路径
        """
        return os.path.join(self._get_cache_path(), "meta.json")

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效

        Returns:
            缓存是否有效
        """
        if not self.use_cache:
            return False

        cache_path = self._get_cache_path()
        meta_path = self._get_cache_meta_path()

        # 检查缓存目录和元数据文件是否存在
        if not os.path.exists(cache_path) or not os.path.exists(meta_path):
            return False

        try:
            # 读取元数据
            with open(meta_path, "r") as f:
                meta = json.load(f)

            # 检查缓存时间是否过期
            cache_time = meta.get("time", 0)
            current_time = time.time()

            # 如果缓存未过期，返回True
            if current_time - cache_time < self.cache_ttl:
                return True
        except Exception as e:
            log_and_notify(f"读取缓存元数据失败: {str(e)}", "error")

        return False

    def _update_cache(self) -> bool:
        """更新缓存

        Returns:
            是否成功更新缓存
        """
        if not self.use_cache or not self.repo:
            return False

        try:
            cache_path = self._get_cache_path()
            meta_path = self._get_cache_meta_path()

            # 如果缓存目录已存在，先删除
            if os.path.exists(cache_path):
                shutil.rmtree(cache_path)

            # 创建缓存目录
            os.makedirs(cache_path, exist_ok=True)

            # 复制仓库到缓存目录
            if self.local_path != cache_path:
                # 使用git clone --mirror命令创建裸仓库缓存
                mirror_path = os.path.join(cache_path, "mirror")
                os.makedirs(mirror_path, exist_ok=True)
                self.repo.git.clone("--mirror", self.local_path, mirror_path)

            # 创建元数据
            meta = {"repo_url": self.repo_url, "branch": self.branch, "time": time.time()}

            # 保存元数据
            with open(meta_path, "w") as f:
                json.dump(meta, f)

            log_and_notify(f"更新仓库缓存: {self.repo_url} -> {cache_path}", "info")
            return True
        except Exception as e:
            log_and_notify(f"更新缓存失败: {str(e)}", "error")
            return False

    def _use_cache(self) -> bool:
        """使用缓存

        Returns:
            是否成功使用缓存
        """
        if not self._is_cache_valid():
            return False

        try:
            cache_path = self._get_cache_path()
            mirror_path = os.path.join(cache_path, "mirror")

            # 确保目标目录存在
            os.makedirs(self.local_path, exist_ok=True)

            # 从缓存克隆到目标目录
            log_and_notify(f"从缓存克隆仓库: {mirror_path} -> {self.local_path}", "info")
            self.repo = Repo.clone_from(mirror_path, self.local_path, branch=self.branch)

            # 设置远程URL
            self.repo.git.remote("set-url", "origin", self.repo_url)

            return True
        except Exception as e:
            log_and_notify(f"使用缓存失败: {str(e)}", "error")
            return False

    def clone(self) -> bool:
        """克隆仓库到本地，优先使用缓存

        Returns:
            是否成功克隆
        """
        try:
            # 检查目标目录是否已经是一个Git仓库
            if os.path.exists(os.path.join(self.local_path, ".git")):
                log_and_notify(f"仓库已存在于 {self.local_path}，打开现有仓库", "info")
                self.repo = Repo(self.local_path)
                return True

            # 尝试使用缓存
            if self.use_cache and self._use_cache():
                log_and_notify(f"成功使用缓存克隆仓库: {self.repo_url}", "info")
                return True

            # 如果缓存无效或使用缓存失败，直接克隆
            log_and_notify(f"克隆仓库 {self.repo_url} 到 {self.local_path}", "info")
            self.repo = Repo.clone_from(self.repo_url, self.local_path, branch=self.branch)

            # 更新缓存
            if self.use_cache:
                self._update_cache()

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
            return cast(str, self.repo.git.show(f"{ref}:{file_path}"))
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
