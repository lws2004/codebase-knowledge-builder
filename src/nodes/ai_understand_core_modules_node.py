"""
AI 理解核心模块节点，用于使用 AI 理解代码库的核心模块。
"""
import os
import json
import re
from typing import Dict, Any, List, Optional
from pocketflow import Node
from pydantic import BaseModel, Field

from ..utils.logger import log_and_notify
from ..utils.llm_wrapper import LLMClient

class AIUnderstandCoreModulesNodeConfig(BaseModel):
    """AIUnderstandCoreModulesNode 配置"""
    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("${LLM_MODEL:-gpt-4}", description="LLM 模型")
    language_detection: bool = Field(True, description="是否检测语言")
    terminology_extraction: bool = Field(True, description="是否提取术语")
    core_modules_prompt_template: str = Field(
        """
        你是一个代码库分析专家。请分析以下代码库结构，并识别核心模块和它们之间的关系。

        代码库结构:
        {code_structure}

        依赖关系:
        {dependencies}

        请提供以下内容:
        1. 核心模块列表，每个模块包括:
           - 模块名称
           - 模块路径
           - 模块功能描述
           - 模块重要性评分 (1-10)
           - 模块依赖关系
        2. 整体架构概述
        3. 模块之间的关系

        以 JSON 格式输出，格式如下:
        ```json
        {{
          "core_modules": [
            {{
              "name": "模块名称",
              "path": "模块路径",
              "description": "模块功能描述",
              "importance": 评分,
              "dependencies": ["依赖模块1", "依赖模块2"]
            }}
          ],
          "architecture": "整体架构概述",
          "module_relationships": [
            "模块A 依赖 模块B",
            "模块C 调用 模块D"
          ]
        }}
        ```
        """,
        description="核心模块提示模板"
    )

class AIUnderstandCoreModulesNode(Node):
    """AI 理解核心模块节点，用于使用 AI 理解代码库的核心模块"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化 AI 理解核心模块节点
        
        Args:
            config: 节点配置
        """
        super().__init__()
        
        # 从配置文件获取默认配置
        from ..utils.env_manager import get_node_config
        default_config = get_node_config("ai_understand_core_modules")
        
        # 合并配置
        merged_config = default_config.copy()
        if config:
            merged_config.update(config)
        
        self.config = AIUnderstandCoreModulesNodeConfig(**merged_config)
        log_and_notify("初始化 AI 理解核心模块节点", "info")
    
    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，从共享存储中获取代码结构
        
        Args:
            shared: 共享存储
            
        Returns:
            包含代码结构的字典
        """
        log_and_notify("AIUnderstandCoreModulesNode: 准备阶段开始", "info")
        
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
        
        # 获取 LLM 配置
        llm_config = shared.get("llm_config", {})
        
        # 获取目标语言
        target_language = shared.get("language", "zh")
        
        return {
            "code_structure": code_structure,
            "llm_config": llm_config,
            "target_language": target_language,
            "retry_count": self.config.retry_count,
            "quality_threshold": self.config.quality_threshold,
            "model": self.config.model,
        }
    
    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，使用 AI 理解代码库的核心模块
        
        Args:
            prep_res: 准备阶段的结果
            
        Returns:
            理解结果
        """
        log_and_notify("AIUnderstandCoreModulesNode: 执行阶段开始", "info")
        
        # 检查准备阶段是否出错
        if "error" in prep_res:
            return {"error": prep_res["error"], "success": False}
        
        code_structure = prep_res["code_structure"]
        llm_config = prep_res["llm_config"]
        target_language = prep_res["target_language"]
        retry_count = prep_res["retry_count"]
        quality_threshold = prep_res["quality_threshold"]
        model = prep_res["model"]
        
        # 准备依赖关系（这里简化处理，实际应该从代码分析中获取）
        dependencies = "暂无依赖关系信息"
        
        # 准备提示
        prompt = self._create_prompt(code_structure, dependencies)
        
        # 尝试调用 LLM
        for attempt in range(retry_count):
            try:
                log_and_notify(f"尝试理解核心模块 (尝试 {attempt + 1}/{retry_count})", "info")
                
                # 调用 LLM
                parsed_result, quality_score, success = self._call_model(
                    llm_config, prompt, target_language, model
                )
                
                if success and quality_score["overall"] >= quality_threshold:
                    log_and_notify(f"成功理解核心模块 (质量分数: {quality_score['overall']})", "info")
                    return {
                        "core_modules": parsed_result.get("core_modules", []),
                        "architecture": parsed_result.get("architecture", ""),
                        "module_relationships": parsed_result.get("module_relationships", []),
                        "quality_score": quality_score,
                        "success": True
                    }
                elif success:
                    log_and_notify(
                        f"理解质量不佳 (分数: {quality_score['overall']}), 重试中...",
                        "warning"
                    )
            except Exception as e:
                log_and_notify(f"LLM 调用失败: {str(e)}, 重试中...", "warning")
        
        # 所有尝试都失败
        error_msg = f"无法理解核心模块，{retry_count} 次尝试后失败"
        log_and_notify(error_msg, "error", notify=True)
        return {"error": error_msg, "success": False}
    
    def post(self, shared: Dict[str, Any], prep_res: Dict[str, Any], exec_res: Dict[str, Any]) -> str:
        """后处理阶段，将理解结果存储到共享存储中
        
        Args:
            shared: 共享存储
            prep_res: 准备阶段的结果
            exec_res: 执行阶段的结果
            
        Returns:
            下一个节点的动作
        """
        log_and_notify("AIUnderstandCoreModulesNode: 后处理阶段开始", "info")
        
        # 检查执行阶段是否出错
        if not exec_res.get("success", False):
            error_msg = exec_res.get("error", "未知错误")
            log_and_notify(f"理解核心模块失败: {error_msg}", "error", notify=True)
            shared["core_modules"] = {"error": error_msg, "success": False}
            return "error"
        
        # 将理解结果存储到共享存储中
        shared["core_modules"] = {
            "modules": exec_res.get("core_modules", []),
            "architecture": exec_res.get("architecture", ""),
            "relationships": exec_res.get("module_relationships", []),
            "quality_score": exec_res.get("quality_score", {}),
            "success": True
        }
        
        log_and_notify(
            f"成功理解核心模块，识别了 {len(exec_res.get('core_modules', []))} 个核心模块",
            "info",
            notify=True
        )
        
        return "default"
    
    def _create_prompt(self, code_structure: Dict[str, Any], dependencies: str) -> str:
        """创建提示
        
        Args:
            code_structure: 代码结构
            dependencies: 依赖关系
            
        Returns:
            提示
        """
        # 简化代码结构，避免提示过长
        simplified_structure = {
            "file_count": code_structure.get("file_count", 0),
            "directory_count": code_structure.get("directory_count", 0),
            "language_stats": code_structure.get("language_stats", {}),
            "file_types": code_structure.get("file_types", {}),
            "directories": self._simplify_directories(code_structure.get("directories", {})),
        }
        
        # 格式化提示
        return self.config.core_modules_prompt_template.format(
            code_structure=json.dumps(simplified_structure, indent=2, ensure_ascii=False),
            dependencies=dependencies
        )
    
    def _simplify_directories(self, directories: Dict[str, Any]) -> Dict[str, Any]:
        """简化目录结构
        
        Args:
            directories: 目录结构
            
        Returns:
            简化后的目录结构
        """
        result = {}
        
        for path, info in directories.items():
            # 只保留类型和文件列表
            result[path] = {
                "type": info.get("type", "directory"),
                "files": [os.path.basename(f) for f in info.get("files", [])],
                "subdirectories": [os.path.basename(d) for d in info.get("subdirectories", [])],
            }
        
        return result
    
    def _call_model(
        self,
        llm_config: Dict[str, Any],
        prompt: str,
        target_language: str,
        model: str
    ) -> tuple:
        """调用 LLM
        
        Args:
            llm_config: LLM 配置
            prompt: 提示
            target_language: 目标语言
            model: 模型
            
        Returns:
            解析结果、质量分数和成功标志
        """
        try:
            # 创建 LLM 客户端
            llm_client = LLMClient(llm_config)
            
            # 准备系统提示
            system_prompt = f"""你是一个代码库分析专家，擅长从代码结构中识别核心模块和它们之间的关系。
请用{target_language}语言回答，但保持代码、变量名和技术术语的原始形式。
你的回答必须是有效的 JSON 格式。"""
            
            # 调用 LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            response = llm_client.completion(
                messages=messages,
                temperature=0.3,
                model=model,
                trace_name="理解核心模块"
            )
            
            # 获取响应内容
            content = llm_client.get_completion_content(response)
            
            # 解析 JSON
            parsed_result = self._extract_json(content)
            
            # 评估质量
            quality_score = self._evaluate_quality(parsed_result)
            
            return parsed_result, quality_score, True
        except Exception as e:
            log_and_notify(f"调用 LLM 失败: {str(e)}", "error")
            raise
    
    def _extract_json(self, content: str) -> Dict[str, Any]:
        """从内容中提取 JSON
        
        Args:
            content: 内容
            
        Returns:
            解析后的 JSON
        """
        # 尝试提取 JSON 块
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接解析整个内容
            json_str = content
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # 尝试修复常见的 JSON 错误
            # 1. 单引号替换为双引号
            json_str = json_str.replace("'", '"')
            # 2. 移除尾部逗号
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                log_and_notify("无法解析 JSON 响应", "error")
                return {}
    
    def _evaluate_quality(self, result: Dict[str, Any]) -> Dict[str, float]:
        """评估结果质量
        
        Args:
            result: 解析结果
            
        Returns:
            质量分数
        """
        scores = {
            "completeness": 0.0,
            "structure": 0.0,
            "relevance": 0.0,
            "overall": 0.0
        }
        
        # 检查完整性
        core_modules = result.get("core_modules", [])
        has_architecture = bool(result.get("architecture", ""))
        has_relationships = bool(result.get("module_relationships", []))
        
        if core_modules and has_architecture and has_relationships:
            scores["completeness"] = 1.0
        elif core_modules and (has_architecture or has_relationships):
            scores["completeness"] = 0.7
        elif core_modules:
            scores["completeness"] = 0.4
        
        # 检查结构
        valid_modules = 0
        for module in core_modules:
            if all(k in module for k in ["name", "path", "description", "importance"]):
                valid_modules += 1
        
        if core_modules:
            scores["structure"] = valid_modules / len(core_modules)
        
        # 检查相关性（简化处理，实际应该基于代码库内容评估）
        scores["relevance"] = 0.8  # 假设相关性较高
        
        # 计算总体分数
        scores["overall"] = (scores["completeness"] + scores["structure"] + scores["relevance"]) / 3
        
        return scores
