"""
交互式问答节点，用于处理用户的交互式问题。
"""
import re
import json
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from pocketflow import Node

from ..utils.logger import log_and_notify
from ..utils.llm_client import LLMClient


class InteractiveQANodeConfig(BaseModel):
    """InteractiveQANode 配置"""
    retry_count: int = Field(3, ge=1, le=10, description="重试次数")
    quality_threshold: float = Field(0.7, ge=0, le=1.0, description="质量阈值")
    model: str = Field("${LLM_MODEL:-gpt-4}", description="LLM 模型")
    qa_prompt_template: str = Field(
        """
        你是一个代码库专家，熟悉这个代码库的所有细节。请根据以下信息回答用户的问题。

        代码库信息:
        {code_info}

        相关上下文:
        {context}

        用户问题:
        {question}

        请提供准确、全面的回答，包括相关代码引用和解释。如果无法回答，请说明原因。
        """,
        description="问答提示模板"
    )
    max_context_chunks: int = Field(5, ge=1, le=20, description="最大上下文块数")


class InteractiveQANode(Node):
    """交互式问答节点，用于处理用户的交互式问题"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化交互式问答节点

        Args:
            config: 节点配置
        """
        super().__init__()
        config_model = InteractiveQANodeConfig(**(config or {}))
        self.config = config_model
        log_and_notify("初始化交互式问答节点", "info")

    def prep(self, shared: Dict[str, Any]) -> Dict[str, Any]:
        """准备阶段，收集问答所需的信息

        Args:
            shared: 共享存储

        Returns:
            准备结果
        """
        log_and_notify("开始处理交互式问答", "info")

        # 检查是否有用户问题
        user_query = shared.get("user_query")
        if not user_query:
            log_and_notify("没有用户问题，跳过交互式问答", "info")
            return {"skip": True}

        # 获取 RAG 数据
        vector_index = shared.get("vector_index")
        text_chunks = shared.get("text_chunks")

        if not vector_index or not text_chunks:
            error_msg = "没有找到 RAG 数据"
            log_and_notify(error_msg, "error", notify=True)
            return {"error": error_msg}

        # 获取 LLM 配置
        llm_config = shared.get("llm_config", {})

        # 获取目标语言
        target_language = shared.get("language", "zh")

        # 获取代码库信息
        code_structure = shared.get("code_structure", {})
        core_modules = shared.get("core_modules", {})

        # 获取对话历史
        conversation_history = shared.get("conversation_history", [])

        return {
            "user_query": user_query,
            "vector_index": vector_index,
            "text_chunks": text_chunks,
            "llm_config": llm_config,
            "target_language": target_language,
            "code_structure": code_structure,
            "core_modules": core_modules,
            "conversation_history": conversation_history,
            "retry_count": self.config.retry_count,
            "quality_threshold": self.config.quality_threshold,
            "model": self.config.model,
            "max_context_chunks": self.config.max_context_chunks
        }

    def exec(self, prep_res: Dict[str, Any]) -> Dict[str, Any]:
        """执行阶段，处理用户问题并生成回答

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
        user_query = prep_res["user_query"]
        vector_index = prep_res["vector_index"]
        text_chunks = prep_res["text_chunks"]
        llm_config = prep_res["llm_config"]
        target_language = prep_res["target_language"]
        code_structure = prep_res["code_structure"]
        core_modules = prep_res["core_modules"]
        conversation_history = prep_res["conversation_history"]
        retry_count = prep_res["retry_count"]
        quality_threshold = prep_res["quality_threshold"]
        model = prep_res["model"]
        max_context_chunks = prep_res["max_context_chunks"]

        try:
            # 分析问题类型和意图
            log_and_notify("开始分析问题类型和意图", "info")
            question_type, question_intent = self._analyze_question(user_query, llm_config, model)

            # 检索相关上下文
            log_and_notify("开始检索相关上下文", "info")
            context_chunks = self._retrieve_context(user_query, vector_index, text_chunks, max_context_chunks)

            # 准备代码库信息
            code_info = self._prepare_code_info(code_structure, core_modules)

            # 尝试生成回答
            for attempt in range(retry_count):
                try:
                    log_and_notify(f"尝试生成回答 (尝试 {attempt + 1}/{retry_count})", "info")

                    # 调用 LLM 生成回答
                    answer, quality_score, success = self._generate_answer(
                        user_query,
                        context_chunks,
                        code_info,
                        conversation_history,
                        target_language,
                        llm_config,
                        model
                    )

                    if success and quality_score >= quality_threshold:
                        log_and_notify(f"成功生成回答 (质量分数: {quality_score})", "info")

                        # 更新对话历史
                        updated_history = conversation_history.copy()
                        updated_history.append({"role": "user", "content": user_query})
                        updated_history.append({"role": "assistant", "content": answer})

                        return {
                            "answer": answer,
                            "quality_score": quality_score,
                            "conversation_history": updated_history,
                            "success": True
                        }
                    elif success:
                        log_and_notify(f"回答质量不佳 (分数: {quality_score}), 重试中...", "warning")
                except Exception as e:
                    log_and_notify(f"生成回答失败: {str(e)}, 重试中...", "warning")

            # 如果所有尝试都失败，返回错误
            error_msg = "无法生成高质量回答"
            log_and_notify(error_msg, "error", notify=True)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"处理交互式问答失败: {str(e)}"
            log_and_notify(error_msg, "error", notify=True)
            return {"success": False, "error": error_msg}

    def post(self, shared: Dict[str, Any], exec_res: Dict[str, Any]) -> None:
        """后处理阶段，更新共享存储

        Args:
            shared: 共享存储
            exec_res: 执行结果
        """
        if exec_res.get("skipped", False):
            log_and_notify("跳过交互式问答", "info")
            return

        if exec_res.get("success", False):
            # 更新共享存储
            shared["answer"] = exec_res["answer"]
            shared["conversation_history"] = exec_res["conversation_history"]

            # 添加到自定义回答列表
            if "custom_answers" not in shared:
                shared["custom_answers"] = []

            shared["custom_answers"].append({
                "question": shared["user_query"],
                "answer": exec_res["answer"],
                "quality_score": exec_res["quality_score"]
            })

            log_and_notify("交互式问答处理完成", "info", notify=True)
        elif "error" in exec_res:
            shared["error"] = exec_res["error"]
            log_and_notify(f"交互式问答处理失败: {exec_res['error']}", "error", notify=True)

    def _analyze_question(self, question: str, llm_config: Dict[str, Any], model: str) -> tuple:
        """分析问题类型和意图

        Args:
            question: 问题
            llm_config: LLM 配置
            model: 模型

        Returns:
            问题类型和意图
        """
        try:
            # 创建 LLM 客户端
            llm_client = LLMClient(llm_config)

            # 准备系统提示
            system_prompt = """你是一个问题分析专家。请分析用户问题的类型和意图。
问题类型可以是：架构相关、API相关、实现细节、使用方法、故障排除等。
问题意图可以是：寻求解释、寻求示例、寻求比较、寻求建议等。
请以 JSON 格式返回结果，包含 type 和 intent 字段。"""

            # 准备用户提示
            user_prompt = f"请分析以下问题的类型和意图：\n\n{question}"

            # 调用 LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response = llm_client.completion(
                messages=messages,
                temperature=0.3,
                model=model,
                trace_name="分析问题类型和意图"
            )

            # 获取响应内容
            response_content = llm_client.get_completion_content(response)

            # 解析 JSON 响应
            try:
                # 提取 JSON 部分
                json_match = re.search(r'```json\n(.*?)\n```', response_content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response_content

                # 解析 JSON
                result = json.loads(json_str)

                return result.get("type", "unknown"), result.get("intent", "unknown")
            except Exception as e:
                log_and_notify(f"解析问题分析结果失败: {str(e)}", "warning")
                return "unknown", "unknown"
        except Exception as e:
            log_and_notify(f"分析问题类型和意图失败: {str(e)}", "warning")
            return "unknown", "unknown"

    def _retrieve_context(self, question: str, vector_index: Any, text_chunks: List[str], max_chunks: int) -> str:
        """检索相关上下文

        Args:
            question: 问题
            vector_index: 向量索引
            text_chunks: 文本块
            max_chunks: 最大块数

        Returns:
            上下文
        """
        # 这里应该实现向量检索逻辑
        # 由于我们没有实际的向量索引实现，这里只是一个模拟
        log_and_notify("检索相关上下文（模拟）", "info")

        # 模拟检索结果
        # 在实际实现中，应该使用向量检索找到最相关的文本块
        context_chunks = []

        # 简单模拟：查找包含问题关键词的文本块
        keywords = question.lower().split()
        for chunk in text_chunks:
            chunk_lower = chunk.lower()
            if any(keyword in chunk_lower for keyword in keywords):
                context_chunks.append(chunk)
                if len(context_chunks) >= max_chunks:
                    break

        # 如果没有找到相关块，使用前几个块
        if not context_chunks and text_chunks:
            context_chunks = text_chunks[:max_chunks]

        return "\n\n---\n\n".join(context_chunks)

    def _prepare_code_info(self, code_structure: Dict[str, Any], core_modules: Dict[str, Any]) -> str:
        """准备代码库信息

        Args:
            code_structure: 代码结构
            core_modules: 核心模块

        Returns:
            代码库信息
        """
        # 简化代码结构
        simplified_structure = {}
        for file_path, file_info in code_structure.items():
            if isinstance(file_info, dict):
                simplified_structure[file_path] = {
                    "type": file_info.get("type", "unknown"),
                    "classes": list(file_info.get("classes", {}).keys()),
                    "functions": list(file_info.get("functions", {}).keys())
                }

        # 简化核心模块
        simplified_modules = {}
        for module_name, module_info in core_modules.items():
            if isinstance(module_info, dict):
                simplified_modules[module_name] = {
                    "path": module_info.get("path", ""),
                    "description": module_info.get("description", ""),
                    "type": module_info.get("type", "module")
                }

        # 组合信息
        code_info = {
            "structure": simplified_structure,
            "core_modules": simplified_modules
        }

        return json.dumps(code_info, indent=2, ensure_ascii=False)

    def _generate_answer(
        self,
        question: str,
        context: str,
        code_info: str,
        conversation_history: List[Dict[str, str]],
        target_language: str,
        llm_config: Dict[str, Any],
        model: str
    ) -> tuple:
        """生成回答

        Args:
            question: 问题
            context: 上下文
            code_info: 代码库信息
            conversation_history: 对话历史
            target_language: 目标语言
            llm_config: LLM 配置
            model: 模型

        Returns:
            回答、质量分数和成功标志
        """
        try:
            # 创建 LLM 客户端
            llm_client = LLMClient(llm_config)

            # 准备系统提示
            system_prompt = f"""你是一个代码库专家，熟悉这个代码库的所有细节。
请用{target_language}语言回答用户的问题，但保持代码、变量名和技术术语的原始形式。
你的回答应该是格式良好的 Markdown，使用适当的标题、列表、表格和代码块。
使用表情符号使回答更加生动，例如在标题前使用适当的表情符号。
如果无法回答，请诚实地说明原因。"""

            # 准备对话历史
            messages = [{"role": "system", "content": system_prompt}]

            # 添加对话历史（最多3轮）
            history_limit = min(len(conversation_history), 6)
            if history_limit > 0:
                for i in range(len(conversation_history) - history_limit, len(conversation_history)):
                    messages.append(conversation_history[i])

            # 准备用户提示
            user_prompt = self.config.qa_prompt_template.format(
                code_info=code_info,
                context=context,
                question=question
            )

            # 添加用户问题
            messages.append({"role": "user", "content": user_prompt})

            # 调用 LLM
            response = llm_client.completion(
                messages=messages,
                temperature=0.5,
                model=model,
                trace_name="生成问答回答"
            )

            # 获取响应内容
            answer = llm_client.get_completion_content(response)

            # 评估质量
            quality_score = self._evaluate_answer_quality(question, answer, context)

            return answer, quality_score, True
        except Exception as e:
            log_and_notify(f"生成回答失败: {str(e)}", "error")
            raise

    def _evaluate_answer_quality(self, question: str, answer: str, context: str) -> float:
        """评估回答质量

        Args:
            question: 问题
            answer: 回答
            context: 上下文

        Returns:
            质量分数
        """
        # 简单实现：检查回答长度、是否包含代码块、是否引用上下文
        score = 0.5  # 基础分数

        # 检查回答长度
        if len(answer) > 100:
            score += 0.1
        if len(answer) > 300:
            score += 0.1

        # 检查是否包含代码块
        if "```" in answer:
            score += 0.1

        # 检查是否引用上下文
        context_keywords = set(context.lower().split())
        answer_keywords = set(answer.lower().split())
        common_keywords = context_keywords.intersection(answer_keywords)
        if len(common_keywords) > 5:
            score += 0.1

        # 检查是否包含问题关键词
        question_keywords = set(question.lower().split())
        common_question_keywords = question_keywords.intersection(answer_keywords)
        if len(common_question_keywords) > 0:
            score += 0.1

        # 确保分数在 0-1 之间
        return max(0.0, min(1.0, score))
