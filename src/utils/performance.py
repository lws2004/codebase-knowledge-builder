"""性能工具模块，提供并行处理和性能优化相关功能。"""

import concurrent.futures
import time
from typing import Callable, List, Optional, TypeVar

from tqdm import tqdm

from .logger import log_and_notify

T = TypeVar("T")
R = TypeVar("R")


def parallel_process(
    items: List[T],
    process_func: Callable[[T], R],
    max_workers: Optional[int] = None,
    chunk_size: int = 1,
    show_progress: bool = True,
    desc: str = "Processing",
) -> List[R]:
    """并行处理项目列表

    Args:
        items: 待处理项列表
        process_func: 处理函数，接受一个项目并返回处理结果
        max_workers: 最大工作线程数，默认为None（使用系统默认值）
        chunk_size: 分块大小，默认为1
        show_progress: 是否显示进度条，默认为True
        desc: 进度条描述，默认为"Processing"

    Returns:
        处理结果列表
    """
    if not items:
        return []

    # 计算合适的工作线程数
    if max_workers is None:
        # 默认使用CPU核心数的2倍，因为大多数任务是I/O密集型的
        import os

        cpu_count = os.cpu_count()
        max_workers = (cpu_count * 2) if cpu_count is not None else 4

    # 限制最大工作线程数，避免创建过多线程
    max_workers = min(max_workers, len(items))

    results = []
    errors = []

    # 使用线程池并行执行处理函数
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_item = {executor.submit(process_func, item): i for i, item in enumerate(items)}

        # 创建进度条
        pbar = None
        if show_progress:
            pbar = tqdm(total=len(items), desc=desc)

        # 处理结果
        for future in concurrent.futures.as_completed(future_to_item):
            idx = future_to_item[future]
            try:
                result = future.result()
                # 保持原始顺序
                results.append((idx, result))
            except Exception as exc:
                error_msg = f"处理项目 {idx} 时出错: {exc}"
                log_and_notify(error_msg, "error")
                errors.append((idx, error_msg))
                # 添加错误结果，保持结果列表长度与输入列表一致
                results.append((idx, None))
            finally:
                if pbar:
                    pbar.update(1)

        # 关闭进度条
        if pbar:
            pbar.close()

    # 如果有错误，记录错误数量
    if errors:
        log_and_notify(f"并行处理完成，但有 {len(errors)} 个错误", "warning")

    # 按原始顺序排序结果
    results.sort(key=lambda x: x[0])
    return [r[1] for r in results]


def chunk_list(items: List[T], chunk_size: int) -> List[List[T]]:
    """将列表分割成指定大小的块

    Args:
        items: 要分割的列表
        chunk_size: 块大小

    Returns:
        分割后的块列表
    """
    if chunk_size <= 0:
        chunk_size = 1
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def process_with_rate_limit(
    items: List[T],
    process_func: Callable[[T], R],
    rate_limit: int = 10,  # 每秒请求数
    max_workers: Optional[int] = None,
    show_progress: bool = True,
    desc: str = "Processing with rate limit",
) -> List[R]:
    """使用速率限制并行处理项目列表

    适用于需要调用API等有速率限制的场景

    Args:
        items: 待处理项列表
        process_func: 处理函数，接受一个项目并返回处理结果
        rate_limit: 每秒最大请求数，默认为10
        max_workers: 最大工作线程数，默认为None（使用系统默认值）
        show_progress: 是否显示进度条，默认为True
        desc: 进度条描述，默认为"Processing with rate limit"

    Returns:
        处理结果列表
    """
    if not items:
        return []

    # 计算合适的工作线程数，不超过速率限制
    if max_workers is None:
        max_workers = min(rate_limit, len(items))
    else:
        max_workers = min(max_workers, rate_limit, len(items))

    results = []
    errors = []

    # 计算请求间隔时间（秒）
    interval = 1.0 / rate_limit

    # 使用信号量控制并发数
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 创建进度条
        pbar = None
        if show_progress:
            pbar = tqdm(total=len(items), desc=desc)

        # 提交所有任务
        future_to_item = {}
        for i, item in enumerate(items):
            # 添加延迟以符合速率限制
            if i > 0 and i % max_workers == 0:
                time.sleep(interval * max_workers)
            future = executor.submit(process_func, item)
            future_to_item[future] = i

        # 处理结果
        for future in concurrent.futures.as_completed(future_to_item):
            idx = future_to_item[future]
            try:
                result = future.result()
                # 保持原始顺序
                results.append((idx, result))
            except Exception as exc:
                error_msg = f"处理项目 {idx} 时出错: {exc}"
                log_and_notify(error_msg, "error")
                errors.append((idx, error_msg))
                # 添加错误结果，保持结果列表长度与输入列表一致
                results.append((idx, None))
            finally:
                if pbar:
                    pbar.update(1)

        # 关闭进度条
        if pbar:
            pbar.close()

    # 如果有错误，记录错误数量
    if errors:
        log_and_notify(f"速率限制并行处理完成，但有 {len(errors)} 个错误", "warning")

    # 按原始顺序排序结果
    results.sort(key=lambda x: x[0])
    return [r[1] for r in results]
