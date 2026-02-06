import logging
import os
import sys
from pathlib import Path

import yaml

from src.macd_trader.crew import TradingCrew
from src.macd_trader.notification import send_batch_notification
from src.macd_trader.result_storage import save_result

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(project_root))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Default stocks config path (project root)
DEFAULT_STOCKS_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "stocks.yaml",
)


def load_stocks_config(config_path: str | None = None) -> list[dict]:
    """Load multi-stock configuration from stocks.yaml.

    Falls back to env vars TARGET_STOCK / TRADE_QUANTITY for backward compatibility.
    """
    if config_path is None:
        config_path = DEFAULT_STOCKS_CONFIG

    if Path(config_path).exists():
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        stocks = config.get("stocks", [])
        if stocks:
            logger.info(f"Loaded {len(stocks)} stocks from {config_path}")
            return stocks

    # Fallback: use environment variables for backward compatibility
    logger.info("No stocks.yaml found, falling back to environment variables.")
    stock_ticker = os.getenv("TARGET_STOCK", "NVDA.US")
    trade_quantity = int(os.getenv("TRADE_QUANTITY", "1"))
    return [
        {
            "ticker": stock_ticker,
            "name": stock_ticker,
            "shares": trade_quantity,
            "avg_cost": 0,
        }
    ]


def extract_decision_from_result(result_text: str) -> str:
    """Try to extract decision (BUY/SELL/HOLD) from crew result."""
    import re

    try:
        # Pattern 1: [BUY] / [SELL] / [HOLD] in report title
        for keyword in ["BUY", "SELL", "HOLD"]:
            if f"[{keyword}]" in result_text:
                return keyword

        # Pattern 2: "decision": "HOLD" in JSON output
        match = re.search(r'"decision"\s*:\s*"(BUY|SELL|HOLD)"', result_text)
        if match:
            return match.group(1)

        # Pattern 3: decision: HOLD (without quotes, in report text)
        match = re.search(
            r"decision\s*[:：]\s*(BUY|SELL|HOLD)", result_text, re.IGNORECASE
        )
        if match:
            return match.group(1).upper()

        # Pattern 4: standalone BUY/SELL/HOLD as a word
        match = re.search(r"\b(BUY|SELL|HOLD)\b", result_text)
        if match:
            return match.group(1)
    except Exception:
        pass
    return "HOLD"


def run_single_stock(stock: dict) -> dict | None:
    """Run the trading crew for a single stock.

    Args:
        stock: dict with keys: ticker, name, shares, avg_cost

    Returns:
        Result dict with ticker, name, decision, report, raw_result; or None on failure
    """
    ticker = stock["ticker"]
    name = stock.get("name", ticker)
    shares = stock.get("shares", 0)
    avg_cost = stock.get("avg_cost", 0)

    logger.info(f"{'=' * 60}")
    logger.info(f"Analyzing {ticker} ({name}) | {shares} shares @ ${avg_cost}")
    logger.info(f"{'=' * 60}")

    inputs = {
        "stock_ticker": ticker,
        "stock_name": name,
        "shares": shares,
        "avg_cost": avg_cost,
    }

    try:
        trading_crew = TradingCrew()
        result = trading_crew.crew().kickoff(inputs=inputs)

        result_text = str(result)
        decision = extract_decision_from_result(result_text)

        logger.info(f"[{ticker}] Analysis complete. Decision: {decision}")

        return {
            "ticker": ticker,
            "name": name,
            "decision": decision,
            "report": result_text,
            "shares": shares,
            "avg_cost": avg_cost,
        }

    except Exception as e:
        logger.error(f"Error analyzing {ticker}: {e}", exc_info=True)
        return None


def run():
    """Main entry point: load config, analyze all stocks, save results, send notification."""
    stocks = load_stocks_config()

    if not stocks:
        logger.error(
            "No stocks configured. Check stocks.yaml or environment variables."
        )
        return

    logger.info(f"Starting analysis for {len(stocks)} stock(s)...")

    # Run analysis for each stock
    reports = []
    for stock in stocks:
        result = run_single_stock(stock)
        if result is not None:
            reports.append(result)

            # Save individual result
            try:
                save_result(
                    ticker=result["ticker"],
                    result={
                        "decision": result["decision"],
                        "report": result["report"],
                        "shares": result["shares"],
                        "avg_cost": result["avg_cost"],
                    },
                )
            except Exception as e:
                logger.error(f"Failed to save result for {result['ticker']}: {e}")

    # Send batch notification
    if reports:
        logger.info(f"Sending notification for {len(reports)} stock(s)...")
        try:
            status = send_batch_notification(reports)
            logger.info(f"Notification status: {status}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}", exc_info=True)
    else:
        logger.warning("No successful analysis results. Skipping notification.")

    logger.info("All analysis complete.")


if __name__ == "__main__":
    run()
