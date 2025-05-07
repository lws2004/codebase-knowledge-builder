"""生成内容流程，用于协调各个内容生成节点。"""

from typing import Any, Dict, Optional

from pocketflow import Flow

from ..utils.logger import log_and_notify
from .content_quality_check_node import ContentQualityCheckNode
from .generate_api_docs_node import GenerateApiDocsNode
from .generate_dependency_node import GenerateDependencyNode
from .generate_glossary_node import GenerateGlossaryNode
from .generate_module_details_node import GenerateModuleDetailsNode
from .generate_overall_architecture_node import GenerateOverallArchitectureNode
from .generate_quick_look_node import GenerateQuickLookNode
from .generate_timeline_node import GenerateTimelineNode
from .module_quality_check_node import ModuleQualityCheckNode


class GenerateContentFlow:
    """生成内容流程，用于协调各个内容生成节点"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化生成内容流程

        Args:
            config: 流程配置
        """
        # 从配置文件获取默认配置
        from ..utils.env_manager import get_node_config

        # 获取各节点配置
        overall_architecture_config = get_node_config("generate_overall_architecture")
        api_docs_config = get_node_config("generate_api_docs")
        timeline_config = get_node_config("generate_timeline")
        dependency_config = get_node_config("generate_dependency")
        glossary_config = get_node_config("generate_glossary")
        quick_look_config = get_node_config("generate_quick_look")
        content_quality_config = get_node_config("content_quality_check")
        module_details_config = get_node_config("generate_module_details")
        module_quality_config = get_node_config("module_quality_check")

        # 合并配置
        if config:
            if "generate_overall_architecture" in config:
                overall_architecture_config.update(config["generate_overall_architecture"])
            if "generate_api_docs" in config:
                api_docs_config.update(config["generate_api_docs"])
            if "generate_timeline" in config:
                timeline_config.update(config["generate_timeline"])
            if "generate_dependency" in config:
                dependency_config.update(config["generate_dependency"])
            if "generate_glossary" in config:
                glossary_config.update(config["generate_glossary"])
            if "generate_quick_look" in config:
                quick_look_config.update(config["generate_quick_look"])
            if "content_quality_check" in config:
                content_quality_config.update(config["content_quality_check"])
            if "generate_module_details" in config:
                module_details_config.update(config["generate_module_details"])
            if "module_quality_check" in config:
                module_quality_config.update(config["module_quality_check"])

        # 创建节点
        self.overall_architecture_node = GenerateOverallArchitectureNode(overall_architecture_config)
        self.api_docs_node = GenerateApiDocsNode(api_docs_config)
        self.timeline_node = GenerateTimelineNode(timeline_config)
        self.dependency_node = GenerateDependencyNode(dependency_config)
        self.glossary_node = GenerateGlossaryNode(glossary_config)
        self.quick_look_node = GenerateQuickLookNode(quick_look_config)
        self.content_quality_node = ContentQualityCheckNode(content_quality_config)
        self.module_details_node = GenerateModuleDetailsNode(module_details_config)
        self.module_quality_node = ModuleQualityCheckNode(module_quality_config)

        # 创建流程
        self.flow = self._create_flow()

        log_and_notify("初始化生成内容流程", "info")

    def _create_flow(self) -> Flow:
        """创建流程

        Returns:
            流程
        """
        # 使用顺序执行而不是并行执行
        # 创建一个简单的顺序流程，并为错误情况添加终止路径
        self.overall_architecture_node >> self.api_docs_node
        self.overall_architecture_node - "error" >> None

        self.api_docs_node >> self.timeline_node
        self.api_docs_node - "error" >> None

        self.timeline_node >> self.dependency_node
        self.timeline_node - "error" >> None

        self.dependency_node >> self.glossary_node
        self.dependency_node - "error" >> None

        self.glossary_node >> self.quick_look_node
        self.glossary_node - "error" >> None

        self.quick_look_node >> self.content_quality_node
        self.quick_look_node - "error" >> None

        # 连接节点 - 模块详细内容生成
        self.content_quality_node >> self.module_details_node
        self.content_quality_node - "error" >> None

        self.module_details_node >> self.module_quality_node
        self.module_details_node - "error" >> None

        # 最后一个节点 module_quality_node 如果出错，也应该能优雅停止
        # 假设它也可能返回 "error"
        self.module_quality_node - "error" >> None

        # 创建流程，使用第一个节点作为启动节点
        return Flow(start=self.overall_architecture_node)

    def run(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """运行流程

        Args:
            shared: 共享存储

        Returns:
            流程结果
        """
        log_and_notify("开始运行生成内容流程", "info")

        # 检查共享存储中是否有必要的数据
        if "code_structure" not in shared:
            error_msg = "共享存储中缺少代码结构"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg, "success": False}

        if "core_modules" not in shared:
            error_msg = "共享存储中缺少核心模块"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg, "success": False}

        # 运行流程
        self.flow.run(shared)

        # 检查流程是否成功
        if "error" in shared:
            return {"error": shared["error"], "success": False}

        # 收集结果
        result = {
            "architecture_doc": shared.get("architecture_doc", {}),
            "api_docs": shared.get("api_docs", {}),
            "timeline_doc": shared.get("timeline_doc", {}),
            "dependency_doc": shared.get("dependency_doc", {}),
            "glossary_doc": shared.get("glossary_doc", {}),
            "quick_look_doc": shared.get("quick_look_doc", {}),
            "module_details": shared.get("module_details", {}),
            "success": True,
        }

        log_and_notify("生成内容流程完成", "info", notify=True)

        return result
