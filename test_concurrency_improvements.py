#!/usr/bin/env python3
"""
测试并发处理能力提升效果
"""

import asyncio
import random
import time

from src.utils.concurrency_manager import get_concurrency_manager
from src.utils.load_balancer import get_load_balancer
from src.utils.performance_monitor import TaskMonitoringContext, get_performance_monitor


def simulate_llm_call(task_id: str) -> str:
    """模拟LLM调用"""
    # 模拟不同的处理时间
    processing_time = random.uniform(0.5, 3.0)
    time.sleep(processing_time)

    # 模拟偶尔的失败
    if random.random() < 0.1:  # 10% 失败率
        raise Exception(f"模拟LLM调用失败: {task_id}")

    return f"LLM响应 for {task_id}"


def simulate_file_processing(file_path: str) -> str:
    """模拟文件处理"""
    processing_time = random.uniform(0.1, 1.0)
    time.sleep(processing_time)

    if random.random() < 0.05:  # 5% 失败率
        raise Exception(f"文件处理失败: {file_path}")

    return f"处理完成: {file_path}"


async def test_concurrency_manager():
    """测试并发管理器"""
    print("\n🔧 测试并发管理器...")

    # 获取并发管理器
    config = {
        "max_concurrent_llm_calls": 8,
        "batch_size": 15,
        "adaptive_batch_size": True,
        "performance_monitoring": True,
        "circuit_breaker_threshold": 5,
    }

    manager = get_concurrency_manager(config)

    # 创建测试任务
    tasks = [f"task_{i}" for i in range(50)]

    print(f"📊 开始处理 {len(tasks)} 个任务...")
    start_time = time.time()

    # 使用并发管理器处理任务
    results = await manager.process_batch_async(items=tasks, process_func=simulate_llm_call, max_concurrency=8)

    end_time = time.time()
    execution_time = end_time - start_time

    # 统计结果
    successful_results = [r for r in results if r is not None]
    success_rate = len(successful_results) / len(tasks)
    throughput = len(successful_results) / execution_time

    print("✅ 并发管理器测试完成:")
    print(f"   - 执行时间: {execution_time:.2f}秒")
    print(f"   - 成功率: {success_rate:.2%}")
    print(f"   - 吞吐量: {throughput:.2f} 任务/秒")

    # 获取性能指标
    metrics = manager.get_metrics()
    print(f"   - 平均响应时间: {metrics.avg_execution_time:.2f}秒")
    print(f"   - 总吞吐量: {metrics.throughput:.2f} 任务/秒")


async def test_load_balancer():
    """测试负载均衡器"""
    print("\n⚖️ 测试负载均衡器...")

    # 获取负载均衡器
    balancer = get_load_balancer(max_workers=6, strategy="least_loaded")

    # 创建测试任务
    files = [f"file_{i}.py" for i in range(30)]

    print(f"📊 开始处理 {len(files)} 个文件...")
    start_time = time.time()

    # 使用负载均衡器处理任务
    results = await balancer.execute_batch(task_func=simulate_file_processing, task_args=files, timeout=5.0)

    end_time = time.time()
    execution_time = end_time - start_time

    # 统计结果
    successful_results = [r for r in results if r is not None]
    success_rate = len(successful_results) / len(files)
    throughput = len(successful_results) / execution_time

    print("✅ 负载均衡器测试完成:")
    print(f"   - 执行时间: {execution_time:.2f}秒")
    print(f"   - 成功率: {success_rate:.2%}")
    print(f"   - 吞吐量: {throughput:.2f} 任务/秒")

    # 显示负载均衡统计
    balancer.log_stats()


async def test_performance_monitoring():
    """测试性能监控"""
    print("\n📊 测试性能监控...")

    monitor = get_performance_monitor()

    # 开始监控
    await monitor.start_monitoring()

    # 模拟一些任务
    async def simulate_tasks():
        for i in range(20):
            task_id = f"monitor_task_{i}"
            with TaskMonitoringContext(task_id):
                # 模拟任务处理
                await asyncio.sleep(random.uniform(0.1, 0.5))
                if random.random() < 0.1:  # 10% 失败率
                    raise Exception(f"任务失败: {task_id}")

    try:
        await simulate_tasks()
    except:
        pass  # 忽略模拟的错误

    # 等待一段时间收集数据
    await asyncio.sleep(2)

    # 停止监控
    await monitor.stop_monitoring()

    # 生成性能报告
    report = monitor.get_performance_report()
    print("✅ 性能监控测试完成:")
    print(f"   - 总任务数: {report['totals']['total_tasks']}")
    print(f"   - 完成任务: {report['totals']['completed_tasks']}")
    print(f"   - 失败任务: {report['totals']['failed_tasks']}")
    print(f"   - 当前吞吐量: {report['current']['throughput']:.2f} 任务/秒")
    print(f"   - 错误率: {report['current']['error_rate']:.2%}")
    print(f"   - 平均响应时间: {report['current']['avg_response_time']:.3f}秒")


def test_traditional_processing():
    """测试传统串行处理（对比基准）"""
    print("\n🐌 测试传统串行处理（基准对比）...")

    tasks = [f"baseline_task_{i}" for i in range(20)]

    print(f"📊 开始串行处理 {len(tasks)} 个任务...")
    start_time = time.time()

    results = []
    for task in tasks:
        try:
            result = simulate_llm_call(task)
            results.append(result)
        except Exception:
            results.append(None)

    end_time = time.time()
    execution_time = end_time - start_time

    successful_results = [r for r in results if r is not None]
    success_rate = len(successful_results) / len(tasks)
    throughput = len(successful_results) / execution_time

    print("✅ 串行处理测试完成:")
    print(f"   - 执行时间: {execution_time:.2f}秒")
    print(f"   - 成功率: {success_rate:.2%}")
    print(f"   - 吞吐量: {throughput:.2f} 任务/秒")

    return execution_time, throughput


async def test_optimized_processing():
    """测试优化后的并发处理"""
    print("\n🚀 测试优化后的并发处理...")

    config = {
        "max_concurrent_llm_calls": 8,
        "batch_size": 15,
        "adaptive_batch_size": True,
        "performance_monitoring": True,
    }

    manager = get_concurrency_manager(config)
    tasks = [f"optimized_task_{i}" for i in range(20)]

    print(f"📊 开始并发处理 {len(tasks)} 个任务...")
    start_time = time.time()

    results = await manager.process_batch_async(items=tasks, process_func=simulate_llm_call, max_concurrency=8)

    end_time = time.time()
    execution_time = end_time - start_time

    successful_results = [r for r in results if r is not None]
    success_rate = len(successful_results) / len(tasks)
    throughput = len(successful_results) / execution_time

    print("✅ 并发处理测试完成:")
    print(f"   - 执行时间: {execution_time:.2f}秒")
    print(f"   - 成功率: {success_rate:.2%}")
    print(f"   - 吞吐量: {throughput:.2f} 任务/秒")

    return execution_time, throughput


async def main():
    """主测试函数"""
    print("🎯 并发处理能力提升测试")
    print("=" * 50)

    # 测试各个组件
    await test_concurrency_manager()
    await test_load_balancer()
    await test_performance_monitoring()

    print("\n📈 性能对比测试")
    print("=" * 30)

    # 对比测试
    baseline_time, baseline_throughput = test_traditional_processing()
    optimized_time, optimized_throughput = await test_optimized_processing()

    # 计算改进
    time_improvement = (baseline_time - optimized_time) / baseline_time * 100
    throughput_improvement = (optimized_throughput - baseline_throughput) / baseline_throughput * 100

    print("\n🎉 性能提升总结:")
    print(f"   - 执行时间改进: {time_improvement:.1f}%")
    print(f"   - 吞吐量提升: {throughput_improvement:.1f}%")

    if time_improvement > 0:
        print(f"   ✅ 并发优化成功！处理速度提升了 {time_improvement:.1f}%")
    else:
        print(f"   ⚠️ 需要进一步优化，当前改进: {time_improvement:.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
