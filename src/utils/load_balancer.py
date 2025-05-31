"""智能负载均衡器，用于优化并发任务分配"""

import asyncio
import random
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TypeVar

from .logger import log_and_notify

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class WorkerStats:
    """工作器统计信息"""

    worker_id: str
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_execution_time: float = 0.0
    last_task_time: float = 0.0
    avg_execution_time: float = 0.0
    success_rate: float = 1.0
    load_score: float = 0.0  # 负载评分，越低越好


class LoadBalancer:
    """智能负载均衡器"""

    def __init__(self, max_workers: int = 8, balancing_strategy: str = "least_loaded"):
        """初始化负载均衡器

        Args:
            max_workers: 最大工作器数量
            balancing_strategy: 负载均衡策略 ('least_loaded', 'round_robin', 'weighted')
        """
        self.max_workers = max_workers
        self.balancing_strategy = balancing_strategy

        # 工作器管理
        self.workers: Dict[str, WorkerStats] = {}
        self.worker_semaphores: Dict[str, asyncio.Semaphore] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()

        # 统计信息
        self.total_tasks = 0
        self.round_robin_index = 0
        self._lock = threading.Lock()

        # 初始化工作器
        self._initialize_workers()

        log_and_notify(f"负载均衡器初始化完成，策略: {balancing_strategy}，工作器数量: {max_workers}", "info")

    def _initialize_workers(self):
        """初始化工作器"""
        for i in range(self.max_workers):
            worker_id = f"worker_{i}"
            self.workers[worker_id] = WorkerStats(worker_id=worker_id)
            self.worker_semaphores[worker_id] = asyncio.Semaphore(1)  # 每个工作器同时只处理一个任务

    def _calculate_load_score(self, worker: WorkerStats) -> float:
        """计算工作器负载评分"""
        # 基础负载：活跃任务数
        base_load = worker.active_tasks

        # 性能因子：平均执行时间（越长负载越高）
        performance_factor = worker.avg_execution_time / 10.0  # 归一化

        # 成功率因子：成功率越低负载越高
        success_factor = (1.0 - worker.success_rate) * 5.0

        # 时间因子：最近任务时间越近负载越高
        time_factor = max(0, 10.0 - (time.time() - worker.last_task_time)) / 10.0

        return base_load + performance_factor + success_factor + time_factor

    def _update_worker_stats(self, worker_id: str, execution_time: float, success: bool):
        """更新工作器统计信息"""
        with self._lock:
            worker = self.workers[worker_id]
            worker.active_tasks = max(0, worker.active_tasks - 1)
            worker.last_task_time = time.time()

            if success:
                worker.completed_tasks += 1
            else:
                worker.failed_tasks += 1

            # 更新平均执行时间
            total_tasks = worker.completed_tasks + worker.failed_tasks
            if total_tasks > 0:
                worker.total_execution_time += execution_time
                worker.avg_execution_time = worker.total_execution_time / total_tasks
                worker.success_rate = worker.completed_tasks / total_tasks

            # 更新负载评分
            worker.load_score = self._calculate_load_score(worker)

    def _select_worker_least_loaded(self) -> str:
        """选择负载最低的工作器"""
        # 更新所有工作器的负载评分
        for worker in self.workers.values():
            worker.load_score = self._calculate_load_score(worker)

        # 选择负载评分最低的工作器
        return min(self.workers.keys(), key=lambda w: self.workers[w].load_score)

    def _select_worker_round_robin(self) -> str:
        """轮询选择工作器"""
        worker_ids = list(self.workers.keys())
        worker_id = worker_ids[self.round_robin_index % len(worker_ids)]
        self.round_robin_index += 1
        return worker_id

    def _select_worker_weighted(self) -> str:
        """基于权重选择工作器"""
        # 计算权重（成功率高、执行时间短的工作器权重高）
        weights = []
        worker_ids = list(self.workers.keys())

        for worker_id in worker_ids:
            worker = self.workers[worker_id]
            # 权重 = 成功率 / (平均执行时间 + 1) / (活跃任务数 + 1)
            weight = worker.success_rate / (worker.avg_execution_time + 1) / (worker.active_tasks + 1)
            weights.append(weight)

        # 加权随机选择
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(worker_ids)

        rand_val = random.uniform(0, total_weight)
        cumulative_weight = 0

        for i, weight in enumerate(weights):
            cumulative_weight += weight
            if rand_val <= cumulative_weight:
                return worker_ids[i]

        return worker_ids[-1]  # 备选

    def select_worker(self) -> str:
        """根据策略选择工作器"""
        if self.balancing_strategy == "least_loaded":
            return self._select_worker_least_loaded()
        elif self.balancing_strategy == "round_robin":
            return self._select_worker_round_robin()
        elif self.balancing_strategy == "weighted":
            return self._select_worker_weighted()
        else:
            return self._select_worker_least_loaded()  # 默认策略

    async def execute_task(
        self, task_func: Callable[[T], R], task_arg: T, timeout: Optional[float] = None
    ) -> Optional[R]:
        """执行单个任务"""
        worker_id = self.select_worker()
        semaphore = self.worker_semaphores[worker_id]

        # 更新工作器状态
        with self._lock:
            self.workers[worker_id].active_tasks += 1
            self.total_tasks += 1

        start_time = time.time()
        success = True
        result = None

        try:
            async with semaphore:
                # 在线程池中执行任务
                loop = asyncio.get_event_loop()
                if timeout:
                    result = await asyncio.wait_for(loop.run_in_executor(None, task_func, task_arg), timeout=timeout)
                else:
                    result = await loop.run_in_executor(None, task_func, task_arg)

        except asyncio.TimeoutError:
            log_and_notify(f"任务超时，工作器: {worker_id}", "warning")
            success = False
        except Exception as e:
            log_and_notify(f"任务执行失败，工作器: {worker_id}，错误: {str(e)}", "error")
            success = False

        finally:
            execution_time = time.time() - start_time
            self._update_worker_stats(worker_id, execution_time, success)

        return result

    async def execute_batch(
        self, task_func: Callable[[T], R], task_args: List[T], timeout: Optional[float] = None
    ) -> List[Optional[R]]:
        """批量执行任务"""
        if not task_args:
            return []

        log_and_notify(f"开始负载均衡批处理: {len(task_args)} 个任务", "info")

        # 创建任务
        tasks = [self.execute_task(task_func, arg, timeout) for arg in task_args]

        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(None)
            else:
                processed_results.append(result)

        return processed_results

    def get_stats(self) -> Dict[str, Any]:
        """获取负载均衡器统计信息"""
        with self._lock:
            worker_stats = {}
            for worker_id, worker in self.workers.items():
                worker_stats[worker_id] = {
                    "active_tasks": worker.active_tasks,
                    "completed_tasks": worker.completed_tasks,
                    "failed_tasks": worker.failed_tasks,
                    "avg_execution_time": worker.avg_execution_time,
                    "success_rate": worker.success_rate,
                    "load_score": worker.load_score,
                }

            return {
                "total_tasks": self.total_tasks,
                "strategy": self.balancing_strategy,
                "max_workers": self.max_workers,
                "workers": worker_stats,
            }

    def log_stats(self):
        """记录统计信息"""
        stats = self.get_stats()

        total_completed = sum(w["completed_tasks"] for w in stats["workers"].values())
        total_failed = sum(w["failed_tasks"] for w in stats["workers"].values())
        total_active = sum(w["active_tasks"] for w in stats["workers"].values())

        avg_success_rate = sum(w["success_rate"] for w in stats["workers"].values()) / len(stats["workers"])

        log_and_notify(
            f"负载均衡器统计 - 总任务: {stats['total_tasks']}, "
            f"完成: {total_completed}, 失败: {total_failed}, "
            f"活跃: {total_active}, 平均成功率: {avg_success_rate:.2%}",
            "info",
        )


# 全局负载均衡器实例
_load_balancer: Optional[LoadBalancer] = None


def get_load_balancer(max_workers: int = 8, strategy: str = "least_loaded") -> LoadBalancer:
    """获取全局负载均衡器实例"""
    global _load_balancer

    if _load_balancer is None:
        _load_balancer = LoadBalancer(max_workers=max_workers, balancing_strategy=strategy)

    return _load_balancer


def reset_load_balancer():
    """重置全局负载均衡器"""
    global _load_balancer
    _load_balancer = None
