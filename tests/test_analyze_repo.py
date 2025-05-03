"""测试分析仓库流程模块"""

import os
import sys
from unittest.mock import MagicMock, patch

# 确保当前目录在 Python 路径中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.nodes.analyze_repo_flow import AnalyzeRepoFlow


class TestAnalyzeRepoFlow:
    """测试分析仓库流程类"""

    def setup_method(self):
        """每个测试方法前的准备工作"""
        # 模拟配置
        self.config = {
            "parse_code": {"max_files": 100},
            "ai_understand": {"retry_count": 1},
            "analyze_history": {"max_commits": 50},
            "prepare_rag": {"chunk_size": 1000},
        }

    @patch("src.nodes.analyze_repo_flow.ParseCodeBatchNode")
    @patch("src.nodes.analyze_repo_flow.AIUnderstandCoreModulesNode")
    @patch("src.nodes.analyze_repo_flow.AnalyzeHistoryNode")
    @patch("src.nodes.analyze_repo_flow.PrepareRAGDataNode")
    def test_init(self, mock_prepare_rag, mock_analyze_history, mock_ai_understand, mock_parse_code):
        """测试初始化"""
        # 创建模拟节点实例
        mock_parse_code.return_value = MagicMock()
        mock_ai_understand.return_value = MagicMock()
        mock_analyze_history.return_value = MagicMock()
        mock_prepare_rag.return_value = MagicMock()

        # 初始化流程
        analyze_repo_flow = AnalyzeRepoFlow(self.config)

        # 验证节点是否被正确创建
        mock_parse_code.assert_called_once_with(self.config["parse_code"])
        mock_ai_understand.assert_called_once_with(self.config["ai_understand"])
        mock_analyze_history.assert_called_once_with(self.config["analyze_history"])
        mock_prepare_rag.assert_called_once_with(self.config["prepare_rag"])

        # 验证流程是否被创建
        assert analyze_repo_flow.flow is not None

    @patch("src.nodes.analyze_repo_flow.Flow")
    @patch("src.nodes.analyze_repo_flow.ParseCodeBatchNode")
    @patch("src.nodes.analyze_repo_flow.AIUnderstandCoreModulesNode")
    @patch("src.nodes.analyze_repo_flow.AnalyzeHistoryNode")
    @patch("src.nodes.analyze_repo_flow.PrepareRAGDataNode")
    def test_create_flow(self, mock_prepare_rag, mock_analyze_history, mock_ai_understand, mock_parse_code, mock_flow):
        """测试创建流程"""
        # 创建模拟节点实例
        mock_parse_code_instance = MagicMock()
        mock_ai_understand_instance = MagicMock()
        mock_analyze_history_instance = MagicMock()
        mock_prepare_rag_instance = MagicMock()

        mock_parse_code.return_value = mock_parse_code_instance
        mock_ai_understand.return_value = mock_ai_understand_instance
        mock_analyze_history.return_value = mock_analyze_history_instance
        mock_prepare_rag.return_value = mock_prepare_rag_instance

        # 初始化流程
        analyze_repo_flow = AnalyzeRepoFlow(self.config)

        # 验证节点连接
        mock_parse_code_instance.__rshift__.assert_any_call(mock_ai_understand_instance)
        mock_parse_code_instance.__rshift__.assert_any_call(mock_prepare_rag_instance)
        mock_parse_code_instance.__rshift__.assert_any_call(mock_analyze_history_instance)

        # 验证流程创建
        mock_flow.assert_called_once_with(start=mock_parse_code_instance)

    @patch("src.nodes.analyze_repo_flow.log_and_notify")
    def test_run_missing_repo_path(self, mock_log_notify):
        """测试运行时缺少仓库路径"""
        # 初始化流程
        analyze_repo_flow = AnalyzeRepoFlow(self.config)

        # 模拟流程的run方法
        analyze_repo_flow.flow = MagicMock()

        # 运行流程，但不提供仓库路径
        shared = {}
        result = analyze_repo_flow.run(shared)

        # 验证结果
        assert result["success"] is False
        assert "error" in result
        assert "缺少仓库路径" in result["error"]

        # 验证日志调用
        mock_log_notify.assert_any_call("开始运行分析仓库流程", "info")

    @patch("src.nodes.analyze_repo_flow.log_and_notify")
    def test_run_success(self, mock_log_notify):
        """测试成功运行"""
        # 初始化流程
        analyze_repo_flow = AnalyzeRepoFlow(self.config)

        # 模拟流程的run方法
        analyze_repo_flow.flow = MagicMock()

        # 运行流程
        shared = {
            "repo_path": "/path/to/repo",
            "code_structure": {"files": 10},
            "core_modules": {"module1": "description1"},
            "history_analysis": {"commits": 50},
            "rag_data": {"chunks": 100},
        }
        result = analyze_repo_flow.run(shared)

        # 验证结果
        assert result["success"] is True
        assert "code_structure" in result
        assert "core_modules" in result
        assert "history_analysis" in result
        assert "rag_data" in result

        # 验证日志调用
        mock_log_notify.assert_any_call("开始运行分析仓库流程", "info")
        mock_log_notify.assert_any_call("分析仓库流程完成", "info", notify=True)
