"""
LLM 客户端，用于调用 LLM API。
"""
import os
import json
from typing import Dict, Any, List, Optional
import litellm
from litellm import completion
from langfuse.client import Langfuse

from .logger import log_and_notify


class LLMClient:
    """LLM 客户端，用于调用 LLM API"""

    def __init__(self, config: Dict[str, Any]):
        """初始化 LLM 客户端
        
        Args:
            config: LLM 配置
        """
        self.config = config
        self.provider = config.get("provider", "openai")
        self.model = config.get("model", "gpt-4")
        self.max_tokens = config.get("max_tokens", 4000)
        self.temperature = config.get("temperature", 0.7)
        
        # 初始化 Langfuse
        langfuse_config = config.get("langfuse", {})
        self.langfuse_enabled = langfuse_config.get("enabled", False)
        if self.langfuse_enabled:
            self.langfuse = Langfuse(
                public_key=langfuse_config.get("public_key", os.getenv("LANGFUSE_PUBLIC_KEY", "")),
                secret_key=langfuse_config.get("secret_key", os.getenv("LANGFUSE_SECRET_KEY", "")),
                host=langfuse_config.get("host", "https://cloud.langfuse.com")
            )
            self.project_name = langfuse_config.get("project_name", "codebase-knowledge-builder")
        else:
            self.langfuse = None
        
        # 配置 litellm
        self._configure_litellm()
    
    def _configure_litellm(self) -> None:
        """配置 litellm"""
        # 设置 API 密钥
        if self.provider == "openai":
            litellm.api_key = os.getenv("OPENAI_API_KEY", "")
            litellm.openai_base_url = self.config.get("openai", {}).get("base_url", "https://api.openai.com/v1")
        elif self.provider == "openrouter":
            litellm.api_key = os.getenv("OPENROUTER_API_KEY", "")
            litellm.openrouter_base_url = self.config.get("openrouter", {}).get("base_url", "https://openrouter.ai/api/v1")
            litellm.openrouter_app_url = self.config.get("openrouter", {}).get("app_url", "http://localhost:3000")
            litellm.openrouter_app_name = self.config.get("openrouter", {}).get("app_name", "Codebase Knowledge Builder")
        elif self.provider == "alibaba":
            litellm.api_key = os.getenv("ALIBABA_API_KEY", "")
            litellm.alibaba_base_url = self.config.get("alibaba", {}).get("base_url", "https://dashscope.aliyuncs.com/api/v1")
        elif self.provider == "volcengine":
            litellm.api_key = os.getenv("VOLCENGINE_API_KEY", "")
            litellm.volcengine_base_url = self.config.get("volcengine", {}).get("base_url", "https://api.volcengine.com/ml/api/v1/services")
            litellm.volcengine_service_id = self.config.get("volcengine", {}).get("service_id", os.getenv("VOLCENGINE_SERVICE_ID", ""))
        elif self.provider == "moonshot":
            litellm.api_key = os.getenv("MOONSHOT_API_KEY", "")
            litellm.moonshot_base_url = self.config.get("moonshot", {}).get("base_url", "https://api.moonshot.cn/v1")
    
    def completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        trace_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """调用 LLM API 生成回答
        
        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度
            max_tokens: 最大 token 数
            trace_name: 跟踪名称
            
        Returns:
            LLM 响应
        """
        # 使用默认值
        model = model or self.model
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens or self.max_tokens
        
        # 准备模型名称
        model_name = model
        if self.provider != "openai" and "/" not in model:
            model_name = f"{self.provider}/{model}"
        
        # 记录调用信息
        log_and_notify(f"调用 LLM API: {model_name}", "info")
        
        # 创建 Langfuse 跟踪
        trace = None
        if self.langfuse_enabled and trace_name:
            trace = self.langfuse.trace(
                name=trace_name,
                project_name=self.project_name,
                metadata={
                    "model": model_name,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
            )
        
        try:
            # 调用 LLM API
            response = completion(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # 记录 Langfuse 生成
            if trace:
                trace.generation(
                    name=trace_name,
                    model=model_name,
                    prompt=json.dumps(messages),
                    completion=response.get("choices", [{}])[0].get("message", {}).get("content", ""),
                    prompt_tokens=response.get("usage", {}).get("prompt_tokens", 0),
                    completion_tokens=response.get("usage", {}).get("completion_tokens", 0),
                    metadata={
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                )
            
            return response
        except Exception as e:
            log_and_notify(f"LLM API 调用失败: {str(e)}", "error")
            
            # 记录 Langfuse 错误
            if trace:
                trace.error(
                    name=trace_name,
                    message=str(e),
                    metadata={
                        "model": model_name,
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                )
            
            raise
    
    def get_completion_content(self, response: Dict[str, Any]) -> str:
        """从 LLM 响应中获取生成的内容
        
        Args:
            response: LLM 响应
            
        Returns:
            生成的内容
        """
        return response.get("choices", [{}])[0].get("message", {}).get("content", "")
