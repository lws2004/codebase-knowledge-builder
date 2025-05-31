"""性能监控工具，用于监控并发处理性能"""

import asyncio
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from .logger import log_and_notify


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""

    timestamp: float
    cpu_usage: float
    memory_usage: float
    active_tasks: int
    completed_tasks: int
    failed_tasks: int
    avg_response_time: float
    throughput: float  # 任务/秒
    error_rate: float  # 错误率


@dataclass
class TaskMetrics:
    """任务指标"""

    task_id: str
    start_time: float
    end_time: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None

    @property
    def duration(self) -> float:
        """任务持续时间"""
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self, max_history: int = 1000, monitoring_interval: float = 5.0):
        """初始化性能监控器

        Args:
            max_history: 最大历史记录数
            monitoring_interval: 监控间隔（秒）
        """
        self.max_history = max_history
        self.monitoring_interval = monitoring_interval

        # 性能数据
        self.metrics_history: deque = deque(maxlen=max_history)
        self.active_tasks: Dict[str, TaskMetrics] = {}
        self.completed_tasks: deque = deque(maxlen=max_history)

        # 统计数据
        self.total_tasks = 0
        self.total_completed = 0
        self.total_failed = 0
        self.start_time = time.time()

        # 线程安全
        self._lock = threading.Lock()
        self._monitoring_task: Optional[asyncio.Task] = None
        self._stop_monitoring = False

        # 系统资源监控
        if HAS_PSUTIL:
            self.process = psutil.Process(os.getpid())
        else:
            self.process = None

        log_and_notify("性能监控器初始化完成", "info")

    def start_task(self, task_id: str) -> None:
        """开始监控任务"""
        with self._lock:
            task_metrics = TaskMetrics(task_id=task_id, start_time=time.time())
            self.active_tasks[task_id] = task_metrics
            self.total_tasks += 1

    def end_task(self, task_id: str, success: bool = True, error_message: Optional[str] = None) -> None:
        """结束任务监控"""
        with self._lock:
            if task_id in self.active_tasks:
                task_metrics = self.active_tasks.pop(task_id)
                task_metrics.end_time = time.time()
                task_metrics.success = success
                task_metrics.error_message = error_message

                self.completed_tasks.append(task_metrics)

                if success:
                    self.total_completed += 1
                else:
                    self.total_failed += 1

    def get_current_metrics(self) -> PerformanceMetrics:
        """获取当前性能指标"""
        with self._lock:
            # 系统资源使用率
            if self.process is not None:
                cpu_usage = self.process.cpu_percent()
                memory_info = self.process.memory_info()
                memory_usage = memory_info.rss / 1024 / 1024  # MB
            else:
                cpu_usage = 0.0
                memory_usage = 0.0

            # 任务统计
            active_count = len(self.active_tasks)

            # 计算平均响应时间
            if self.completed_tasks:
                recent_tasks = list(self.completed_tasks)[-100:]  # 最近100个任务
                avg_response_time = sum(task.duration for task in recent_tasks) / len(recent_tasks)
            else:
                avg_response_time = 0.0

            # 计算吞吐量
            elapsed_time = time.time() - self.start_time
            throughput = self.total_completed / elapsed_time if elapsed_time > 0 else 0.0

            # 计算错误率
            error_rate = self.total_failed / self.total_tasks if self.total_tasks > 0 else 0.0

            return PerformanceMetrics(
                timestamp=time.time(),
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                active_tasks=active_count,
                completed_tasks=self.total_completed,
                failed_tasks=self.total_failed,
                avg_response_time=avg_response_time,
                throughput=throughput,
                error_rate=error_rate,
            )

    def record_metrics(self) -> None:
        """记录当前指标"""
        metrics = self.get_current_metrics()
        self.metrics_history.append(metrics)

    async def start_monitoring(self) -> None:
        """开始异步监控"""
        if self._monitoring_task is not None:
            return

        self._stop_monitoring = False
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        log_and_notify("开始性能监控", "info")

    async def stop_monitoring(self) -> None:
        """停止监控"""
        self._stop_monitoring = True
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
        log_and_notify("停止性能监控", "info")

    async def _monitoring_loop(self) -> None:
        """监控循环"""
        while not self._stop_monitoring:
            try:
                self.record_metrics()
                await asyncio.sleep(self.monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log_and_notify(f"性能监控出错: {str(e)}", "error")
                await asyncio.sleep(self.monitoring_interval)

    def get_performance_report(self) -> Dict[str, Any]:
        """生成性能报告"""
        current_metrics = self.get_current_metrics()

        # 计算历史统计
        if self.metrics_history:
            history = list(self.metrics_history)
            avg_cpu = sum(m.cpu_usage for m in history) / len(history)
            avg_memory = sum(m.memory_usage for m in history) / len(history)
            peak_cpu = max(m.cpu_usage for m in history)
            peak_memory = max(m.memory_usage for m in history)
            peak_active_tasks = max(m.active_tasks for m in history)
        else:
            avg_cpu = avg_memory = peak_cpu = peak_memory = peak_active_tasks = 0

        return {
            "current": {
                "cpu_usage": current_metrics.cpu_usage,
                "memory_usage": current_metrics.memory_usage,
                "active_tasks": current_metrics.active_tasks,
                "throughput": current_metrics.throughput,
                "error_rate": current_metrics.error_rate,
                "avg_response_time": current_metrics.avg_response_time,
            },
            "totals": {
                "total_tasks": self.total_tasks,
                "completed_tasks": self.total_completed,
                "failed_tasks": self.total_failed,
                "uptime": time.time() - self.start_time,
            },
            "averages": {"avg_cpu_usage": avg_cpu, "avg_memory_usage": avg_memory},
            "peaks": {
                "peak_cpu_usage": peak_cpu,
                "peak_memory_usage": peak_memory,
                "peak_active_tasks": peak_active_tasks,
            },
        }

    def log_performance_summary(self) -> None:
        """记录性能摘要"""
        report = self.get_performance_report()

        log_and_notify(
            f"性能摘要 - 总任务: {report['totals']['total_tasks']}, "
            f"完成: {report['totals']['completed_tasks']}, "
            f"失败: {report['totals']['failed_tasks']}, "
            f"吞吐量: {report['current']['throughput']:.2f} 任务/秒, "
            f"错误率: {report['current']['error_rate']:.2%}, "
            f"CPU: {report['current']['cpu_usage']:.1f}%, "
            f"内存: {report['current']['memory_usage']:.1f}MB",
            "info",
        )


# 全局性能监控器实例
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    global _performance_monitor

    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()

    return _performance_monitor


def start_task_monitoring(task_id: str) -> None:
    """开始任务监控"""
    monitor = get_performance_monitor()
    monitor.start_task(task_id)


def end_task_monitoring(task_id: str, success: bool = True, error_message: Optional[str] = None) -> None:
    """结束任务监控"""
    monitor = get_performance_monitor()
    monitor.end_task(task_id, success, error_message)


class TaskMonitoringContext:
    """任务监控上下文管理器"""

    def __init__(self, task_id: str):  # noqa: D107
        self.task_id = task_id
        self.success = True
        self.error_message = None

    def __enter__(self):  # noqa: D105
        start_task_monitoring(self.task_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # noqa: D105
        _ = exc_tb  # 标记为已使用，避免警告
        if exc_type is not None:
            self.success = False
            self.error_message = str(exc_val)

        end_task_monitoring(self.task_id, self.success, self.error_message)
        return False  # 不抑制异常


def monitor_task(task_id: str):
    """任务监控装饰器"""

    def decorator(func: Callable):
        if asyncio.iscoroutinefunction(func):

            async def async_wrapper(*args, **kwargs):
                with TaskMonitoringContext(task_id):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            def sync_wrapper(*args, **kwargs):
                with TaskMonitoringContext(task_id):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator
