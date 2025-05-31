"""
高级并发管理器，用于优化并发处理性能
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
import threading
import queue
from collections import defaultdict

from .logger import log_and_notify

T = TypeVar('T')
R = TypeVar('R')


@dataclass
class ConcurrencyMetrics:
    """并发性能指标"""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_execution_time: float = 0.0
    peak_concurrency: int = 0
    current_concurrency: int = 0
    throughput: float = 0.0  # 任务/秒
    start_time: float = 0.0


class CircuitBreaker:
    """熔断器，防止系统过载"""
    
    def __init__(self, failure_threshold: int = 10, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._lock = threading.Lock()
    
    def call(self, func: Callable, *args, **kwargs):
        """通过熔断器调用函数"""
        with self._lock:
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "HALF_OPEN"
                    log_and_notify("熔断器进入半开状态", "info")
                else:
                    raise Exception("熔断器开启，拒绝请求")
            
            try:
                result = func(*args, **kwargs)
                if self.state == "HALF_OPEN":
                    self.state = "CLOSED"
                    self.failure_count = 0
                    log_and_notify("熔断器恢复正常", "info")
                return result
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = "OPEN"
                    log_and_notify(f"熔断器开启，失败次数: {self.failure_count}", "warning")
                
                raise e


class AdaptiveBatchProcessor:
    """自适应批处理器"""
    
    def __init__(self, initial_batch_size: int = 10, min_batch_size: int = 2, max_batch_size: int = 50):
        self.current_batch_size = initial_batch_size
        self.min_batch_size = min_batch_size
        self.max_batch_size = max_batch_size
        self.performance_history = []
        self.adjustment_factor = 0.2
    
    def adjust_batch_size(self, execution_time: float, success_rate: float):
        """根据性能调整批处理大小"""
        # 记录性能数据
        self.performance_history.append({
            'batch_size': self.current_batch_size,
            'execution_time': execution_time,
            'success_rate': success_rate,
            'throughput': self.current_batch_size / execution_time if execution_time > 0 else 0
        })
        
        # 保留最近10次的性能数据
        if len(self.performance_history) > 10:
            self.performance_history.pop(0)
        
        # 如果数据不足，不调整
        if len(self.performance_history) < 3:
            return
        
        # 计算平均性能
        recent_performance = self.performance_history[-3:]
        avg_throughput = sum(p['throughput'] for p in recent_performance) / len(recent_performance)
        avg_success_rate = sum(p['success_rate'] for p in recent_performance) / len(recent_performance)
        
        # 调整策略
        if avg_success_rate < 0.8:  # 成功率低，减少批处理大小
            new_size = max(self.min_batch_size, int(self.current_batch_size * (1 - self.adjustment_factor)))
            log_and_notify(f"成功率低({avg_success_rate:.2f})，减少批处理大小: {self.current_batch_size} -> {new_size}", "info")
        elif avg_success_rate > 0.95 and avg_throughput > 0:  # 性能良好，尝试增加批处理大小
            new_size = min(self.max_batch_size, int(self.current_batch_size * (1 + self.adjustment_factor)))
            log_and_notify(f"性能良好，增加批处理大小: {self.current_batch_size} -> {new_size}", "info")
        else:
            new_size = self.current_batch_size
        
        self.current_batch_size = new_size
    
    def get_batch_size(self) -> int:
        """获取当前批处理大小"""
        return self.current_batch_size


class ConcurrencyManager:
    """高级并发管理器"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.metrics = ConcurrencyMetrics()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=config.get('circuit_breaker_threshold', 10),
            recovery_timeout=60
        )
        self.adaptive_processor = AdaptiveBatchProcessor(
            initial_batch_size=config.get('batch_size', 10),
            min_batch_size=2,
            max_batch_size=config.get('batch_size', 10) * 3
        )
        self._active_tasks = 0
        self._lock = threading.Lock()
        self._task_queue = queue.Queue()
        self._performance_monitor_enabled = config.get('performance_monitoring', False)
        
        # 初始化指标
        self.metrics.start_time = time.time()
    
    def _update_metrics(self, task_count: int, execution_time: float, success_count: int):
        """更新性能指标"""
        with self._lock:
            self.metrics.total_tasks += task_count
            self.metrics.completed_tasks += success_count
            self.metrics.failed_tasks += (task_count - success_count)
            
            # 更新平均执行时间
            if self.metrics.completed_tasks > 0:
                total_time = self.metrics.avg_execution_time * (self.metrics.completed_tasks - success_count) + execution_time
                self.metrics.avg_execution_time = total_time / self.metrics.completed_tasks
            
            # 更新吞吐量
            elapsed_time = time.time() - self.metrics.start_time
            if elapsed_time > 0:
                self.metrics.throughput = self.metrics.completed_tasks / elapsed_time
    
    async def process_batch_async(
        self,
        items: List[T],
        process_func: Callable[[T], R],
        max_concurrency: Optional[int] = None
    ) -> List[Optional[R]]:
        """异步批处理"""
        if not items:
            return []
        
        max_concurrency = max_concurrency or self.config.get('max_concurrent_llm_calls', 8)
        batch_size = self.adaptive_processor.get_batch_size()
        
        log_and_notify(f"开始异步批处理: {len(items)} 个任务，批大小: {batch_size}，最大并发: {max_concurrency}", "info")
        
        start_time = time.time()
        results = []
        success_count = 0
        
        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def process_item_with_semaphore(item: T) -> Optional[R]:
            async with semaphore:
                try:
                    # 在线程池中执行同步函数
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, self.circuit_breaker.call, process_func, item)
                    return result
                except Exception as e:
                    log_and_notify(f"处理任务失败: {str(e)}", "warning")
                    return None
        
        # 分批处理
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            # 创建任务
            tasks = [process_item_with_semaphore(item) for item in batch]
            
            # 执行批次
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            for result in batch_results:
                if isinstance(result, Exception):
                    results.append(None)
                else:
                    results.append(result)
                    if result is not None:
                        success_count += 1
        
        execution_time = time.time() - start_time
        success_rate = success_count / len(items) if items else 0
        
        # 更新指标
        self._update_metrics(len(items), execution_time, success_count)
        
        # 调整批处理大小
        if self.config.get('adaptive_batch_size', False):
            self.adaptive_processor.adjust_batch_size(execution_time, success_rate)
        
        if self._performance_monitor_enabled:
            log_and_notify(
                f"批处理完成: 成功率 {success_rate:.2f}, 执行时间 {execution_time:.2f}s, "
                f"吞吐量 {self.metrics.throughput:.2f} 任务/秒", "info"
            )
        
        return results
    
    def get_metrics(self) -> ConcurrencyMetrics:
        """获取性能指标"""
        return self.metrics
    
    def reset_metrics(self):
        """重置性能指标"""
        with self._lock:
            self.metrics = ConcurrencyMetrics()
            self.metrics.start_time = time.time()


# 全局并发管理器实例
_concurrency_manager: Optional[ConcurrencyManager] = None


def get_concurrency_manager(config: Optional[Dict[str, Any]] = None) -> ConcurrencyManager:
    """获取全局并发管理器实例"""
    global _concurrency_manager
    
    if _concurrency_manager is None:
        if config is None:
            # 使用默认配置
            from .env_manager import get_node_config
            config = get_node_config('parallel_processing')
        
        _concurrency_manager = ConcurrencyManager(config)
        log_and_notify("并发管理器初始化完成", "info")
    
    return _concurrency_manager


def reset_concurrency_manager():
    """重置全局并发管理器"""
    global _concurrency_manager
    _concurrency_manager = None
