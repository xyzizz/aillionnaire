"""分析结果存储模块。

按日期将每日分析结果保存为 JSON 文件，支持加载历史数据用于回测。

存储路径: results/{ticker}/{YYYY-MM-DD}.json
"""

import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# 默认存储根目录（项目根目录下的 results 文件夹）
DEFAULT_RESULTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "results",
)


def _sanitize_ticker(ticker: str) -> str:
    """将 ticker 转为安全的文件夹名（替换 . 为 _）。"""
    return ticker.replace(".", "_")


def save_result(
    ticker: str,
    result: dict,
    result_date: date | None = None,
    results_dir: str | None = None,
) -> str:
    """保存单只股票的分析结果。

    Args:
        ticker: 股票代码，如 NVDA.US
        result: 分析结果字典，包含 decision、report、raw_analysis 等
        result_date: 结果日期，默认为今天
        results_dir: 存储根目录，默认为项目根目录下的 results

    Returns:
        保存的文件路径
    """
    if result_date is None:
        result_date = date.today()
    if results_dir is None:
        results_dir = DEFAULT_RESULTS_DIR

    safe_ticker = _sanitize_ticker(ticker)
    ticker_dir = Path(results_dir) / safe_ticker
    ticker_dir.mkdir(parents=True, exist_ok=True)

    file_path = ticker_dir / f"{result_date.isoformat()}.json"

    # 添加元数据
    data = {
        "ticker": ticker,
        "date": result_date.isoformat(),
        "saved_at": datetime.now().isoformat(),
        **result,
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"Analysis result saved: {file_path}")
    return str(file_path)


def load_result(
    ticker: str,
    result_date: date,
    results_dir: str | None = None,
) -> dict | None:
    """加载指定日期的分析结果。

    Args:
        ticker: 股票代码
        result_date: 目标日期
        results_dir: 存储根目录

    Returns:
        分析结果字典，文件不存在则返回 None
    """
    if results_dir is None:
        results_dir = DEFAULT_RESULTS_DIR

    safe_ticker = _sanitize_ticker(ticker)
    file_path = Path(results_dir) / safe_ticker / f"{result_date.isoformat()}.json"

    if not file_path.exists():
        logger.warning(f"No result found for {ticker} on {result_date}")
        return None

    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


def load_history(
    ticker: str,
    start_date: date | None = None,
    end_date: date | None = None,
    last_n_days: int | None = None,
    results_dir: str | None = None,
) -> list[dict]:
    """加载指定时间范围的历史分析结果，用于回测。

    Args:
        ticker: 股票代码
        start_date: 开始日期（含），与 end_date 配合使用
        end_date: 结束日期（含），默认为今天
        last_n_days: 最近 N 天，与 start_date/end_date 互斥
        results_dir: 存储根目录

    Returns:
        按日期排序的分析结果列表
    """
    if results_dir is None:
        results_dir = DEFAULT_RESULTS_DIR

    safe_ticker = _sanitize_ticker(ticker)
    ticker_dir = Path(results_dir) / safe_ticker

    if not ticker_dir.exists():
        logger.warning(f"No results directory for {ticker}")
        return []

    # Determine date range
    if last_n_days is not None:
        end_date = date.today()
        start_date = end_date - timedelta(days=last_n_days)
    else:
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = date.min

    results = []
    for json_file in sorted(ticker_dir.glob("*.json")):
        try:
            file_date = date.fromisoformat(json_file.stem)
            if start_date <= file_date <= end_date:
                with open(json_file, encoding="utf-8") as f:
                    results.append(json.load(f))
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Skipping invalid file {json_file}: {e}")
            continue

    logger.info(f"Loaded {len(results)} historical results for {ticker}")
    return results
