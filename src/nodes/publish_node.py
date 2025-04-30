"""
发布节点，用于将生成的文档发布到指定平台。
"""
import os
import shutil
import subprocess
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from pocketflow import Node

from ..utils.logger import log_and_notify


class PublishNodeConfig(BaseModel):
    """PublishNode 配置"""
    platforms: List[str] = Field(["github"], description="支持的发布平台")
    github_pages_branch: str = Field("gh-pages", description="GitHub Pages 分支")
    github_pages_dir: str = Field("docs", description="GitHub Pages 目录")
    github_pages_index: str = Field("index.md", description="GitHub Pages 索引文件")
    github_pages_theme: str = Field("jekyll-theme-cayman", description="GitHub Pages 主题")
    github_pages_title: str = Field("代码库文档", description="GitHub Pages 标题")
    github_pages_description: str = Field("自动生成的代码库文档", description="GitHub Pages 描述")


class PublishNode(Node):
    """发布节点，用于将生成的文档发布到指定平台"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化发布节点
        
        Args:
            config: 节点配置
        """
        super().__init__()
        config_model = PublishNodeConfig(**(config or {}))
        self.config = config_model
        log_and_notify("初始化发布节点", "info")

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，收集发布所需的信息
        
        Args:
            shared: 共享存储
            
        Returns:
            准备结果
        """
        log_and_notify("开始准备发布", "info")
        
        # 检查是否需要发布
        publish_target = shared.get("publish_target")
        if not publish_target:
            log_and_notify("没有指定发布目标，跳过发布", "info")
            return {"skip": True}
        
        # 检查发布目标是否支持
        if publish_target not in self.config.platforms:
            error_msg = f"不支持的发布平台: {publish_target}"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}
        
        # 检查是否有输出文件
        if "output_files" not in shared or not shared["output_files"]:
            error_msg = "没有找到输出文件"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}
        
        # 获取输出目录
        output_dir = shared.get("output_dir", "docs_output")
        
        # 获取仓库信息
        repo_url = shared.get("repo_url", "")
        repo_branch = shared.get("repo_branch", "main")
        
        # 获取认证信息
        auth_info = shared.get("auth_info", {})
        
        # 获取发布仓库信息
        publish_repo = shared.get("publish_repo", "")
        
        return {
            "publish_target": publish_target,
            "output_files": shared["output_files"],
            "output_dir": output_dir,
            "repo_url": repo_url,
            "repo_branch": repo_branch,
            "auth_info": auth_info,
            "publish_repo": publish_repo
        }

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，发布文档
        
        Args:
            prep_res: 准备阶段的结果
            
        Returns:
            执行结果
        """
        # 检查是否跳过
        if prep_res.get("skip", False):
            return {"success": True, "skipped": True}
        
        # 检查准备阶段是否有错误
        if "error" in prep_res:
            return {"success": False, "error": prep_res["error"]}
        
        # 获取参数
        publish_target = prep_res["publish_target"]
        output_files = prep_res["output_files"]
        output_dir = prep_res["output_dir"]
        repo_url = prep_res["repo_url"]
        repo_branch = prep_res["repo_branch"]
        auth_info = prep_res["auth_info"]
        publish_repo = prep_res["publish_repo"]
        
        try:
            # 根据发布目标选择发布方法
            if publish_target == "github":
                log_and_notify("开始发布到 GitHub Pages", "info")
                publish_result = self._publish_to_github_pages(
                    output_dir,
                    publish_repo or repo_url,
                    auth_info
                )
            else:
                error_msg = f"不支持的发布平台: {publish_target}"
                log_and_notify(error_msg, "error", notify=True)
                return {"success": False, "error": error_msg}
            
            return publish_result
        except Exception as e:
            error_msg = f"发布失败: {str(e)}"
            log_and_notify(error_msg, "error", notify=True)
            return {"success": False, "error": error_msg}

    def post(self, shared: Dict[str, Any], exec_res: Dict[str, Any]) -> None:
        """后处理阶段，更新共享存储
        
        Args:
            shared: 共享存储
            exec_res: 执行结果
        """
        if exec_res.get("skipped", False):
            log_and_notify("跳过发布", "info")
            return
        
        if exec_res.get("success", False):
            # 更新共享存储
            shared["publish_url"] = exec_res.get("publish_url", "")
            shared["publish_result"] = exec_res.get("publish_result", {})
            
            log_and_notify(f"发布完成，访问地址: {exec_res.get('publish_url', '未知')}", "info", notify=True)
        elif "error" in exec_res:
            shared["error"] = exec_res["error"]
            log_and_notify(f"发布失败: {exec_res['error']}", "error", notify=True)

    def _publish_to_github_pages(self, output_dir: str, repo_url: str, auth_info: Dict[str, Any]) -> Dict[str, Any]:
        """发布到 GitHub Pages
        
        Args:
            output_dir: 输出目录
            repo_url: 仓库 URL
            auth_info: 认证信息
            
        Returns:
            发布结果
        """
        # 这里应该实现实际的 GitHub Pages 发布逻辑
        # 由于我们不能实际执行 Git 操作，这里只是一个模拟
        log_and_notify("发布到 GitHub Pages（模拟）", "info")
        
        # 创建 _config.yml 文件
        config_path = os.path.join(output_dir, "_config.yml")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(f"theme: {self.config.github_pages_theme}\n")
            f.write(f"title: {self.config.github_pages_title}\n")
            f.write(f"description: {self.config.github_pages_description}\n")
        
        # 模拟发布过程
        log_and_notify("1. 克隆仓库", "info")
        log_and_notify("2. 创建或切换到 gh-pages 分支", "info")
        log_and_notify("3. 复制文档文件", "info")
        log_and_notify("4. 提交更改", "info")
        log_and_notify("5. 推送到远程仓库", "info")
        
        # 提取仓库所有者和名称
        repo_parts = repo_url.rstrip("/").split("/")
        repo_owner = repo_parts[-2] if len(repo_parts) >= 2 else "unknown"
        repo_name = repo_parts[-1].replace(".git", "") if repo_parts else "unknown"
        
        # 构建发布 URL
        publish_url = f"https://{repo_owner}.github.io/{repo_name}"
        
        return {
            "success": True,
            "publish_url": publish_url,
            "publish_result": {
                "platform": "github",
                "repo_url": repo_url,
                "branch": self.config.github_pages_branch,
                "files_count": len(os.listdir(output_dir))
            }
        }

    def _create_github_pages_config(self, output_dir: str) -> str:
        """创建 GitHub Pages 配置文件
        
        Args:
            output_dir: 输出目录
            
        Returns:
            配置文件路径
        """
        config_path = os.path.join(output_dir, "_config.yml")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(f"theme: {self.config.github_pages_theme}\n")
            f.write(f"title: {self.config.github_pages_title}\n")
            f.write(f"description: {self.config.github_pages_description}\n")
            f.write("plugins:\n")
            f.write("  - jekyll-relative-links\n")
            f.write("relative_links:\n")
            f.write("  enabled: true\n")
            f.write("  collections: true\n")
            f.write("include:\n")
            f.write("  - README.md\n")
            f.write("  - docs/**/*.md\n")
        
        return config_path
