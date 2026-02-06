import logging
from datetime import datetime

import yfinance as yf
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class YFinanceNewsInput(BaseModel):
    """Input model for fetching stock news and financial data."""

    ticker: str = Field(
        description="The stock ticker symbol (Yahoo Finance format, e.g., NVDA, AAPL). "
        "Note: strip '.US' suffix if present."
    )


class YFinanceNewsTool(BaseTool):
    """Fetches latest news, earnings dates, and key financial data for a stock using Yahoo Finance."""

    name: str = "YFinance News Tool"
    description: str = (
        "Retrieves latest company news, upcoming/recent earnings dates, "
        "and key financial metrics for a given stock ticker. "
        "Useful for fundamental analysis and news-driven decision making. "
        "Input ticker should be Yahoo Finance format (e.g., NVDA, AAPL, TSLA)."
    )
    args_schema: type[BaseModel] = YFinanceNewsInput

    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        """Convert LongBridge-style ticker (NVDA.US) to Yahoo Finance format (NVDA)."""
        if ticker.endswith(".US"):
            return ticker[:-3]
        return ticker

    def _get_news(self, ticker: str) -> list[dict]:
        """Fetch recent news articles for the stock."""
        try:
            stock = yf.Ticker(ticker)
            news = stock.news
            if not news:
                return []

            articles = []
            for item in news[:10]:  # Limit to 10 most recent
                content = item.get("content", {})
                article = {
                    "title": content.get("title", "N/A"),
                    "summary": content.get("summary", ""),
                    "publish_time": content.get("pubDate", ""),
                    "provider": content.get("provider", {}).get("displayName", "N/A"),
                }
                # Only include articles with meaningful content
                if article["title"] != "N/A":
                    articles.append(article)
            return articles
        except Exception as e:
            logging.error(f"Error fetching news for {ticker}: {e}")
            return []

    def _get_earnings_info(self, ticker: str) -> dict:
        """Fetch earnings dates and recent financial highlights."""
        try:
            stock = yf.Ticker(ticker)
            result = {
                "upcoming_earnings": None,
                "recent_earnings": [],
                "key_metrics": {},
            }

            # Earnings dates
            try:
                earnings_dates = stock.earnings_dates
                if earnings_dates is not None and not earnings_dates.empty:
                    now = datetime.now()
                    future_dates = earnings_dates[
                        earnings_dates.index > now.strftime("%Y-%m-%d")
                    ]
                    past_dates = earnings_dates[
                        earnings_dates.index <= now.strftime("%Y-%m-%d")
                    ]

                    if not future_dates.empty:
                        next_date = future_dates.index[-1]
                        result["upcoming_earnings"] = {
                            "date": str(next_date.date())
                            if hasattr(next_date, "date")
                            else str(next_date),
                            "eps_estimate": self._safe_float(
                                future_dates.iloc[-1].get("EPS Estimate")
                            ),
                        }

                    if not past_dates.empty:
                        for i in range(min(4, len(past_dates))):
                            row = past_dates.iloc[i]
                            result["recent_earnings"].append(
                                {
                                    "date": str(past_dates.index[i].date())
                                    if hasattr(past_dates.index[i], "date")
                                    else str(past_dates.index[i]),
                                    "eps_estimate": self._safe_float(
                                        row.get("EPS Estimate")
                                    ),
                                    "reported_eps": self._safe_float(
                                        row.get("Reported EPS")
                                    ),
                                    "surprise_pct": self._safe_float(
                                        row.get("Surprise(%)")
                                    ),
                                }
                            )
            except Exception as e:
                logging.warning(f"Could not fetch earnings dates for {ticker}: {e}")

            # Key financial metrics from info
            try:
                info = stock.info
                metrics_keys = [
                    "marketCap",
                    "trailingPE",
                    "forwardPE",
                    "trailingEps",
                    "forwardEps",
                    "dividendYield",
                    "revenueGrowth",
                    "earningsGrowth",
                    "profitMargins",
                    "returnOnEquity",
                    "currentPrice",
                    "targetMeanPrice",
                    "recommendationKey",
                    "numberOfAnalystOpinions",
                ]
                for key in metrics_keys:
                    val = info.get(key)
                    if val is not None:
                        result["key_metrics"][key] = val
            except Exception as e:
                logging.warning(f"Could not fetch info for {ticker}: {e}")

            return result
        except Exception as e:
            logging.error(f"Error fetching earnings info for {ticker}: {e}")
            return {"upcoming_earnings": None, "recent_earnings": [], "key_metrics": {}}

    @staticmethod
    def _safe_float(val) -> float | None:
        """Safely convert a value to float, returning None for NaN/None."""
        if val is None:
            return None
        try:
            import math

            f = float(val)
            return None if math.isnan(f) else round(f, 4)
        except (ValueError, TypeError):
            return None

    def _run(self, ticker: str) -> str:
        """Fetch news and financial data, return as formatted string."""
        yf_ticker = self._normalize_ticker(ticker)
        logging.info(
            f"Fetching news and financial data for {yf_ticker} (original: {ticker})"
        )

        news = self._get_news(yf_ticker)
        earnings = self._get_earnings_info(yf_ticker)

        # Build output
        sections = []
        sections.append(f"=== Company Research: {ticker} ({yf_ticker}) ===\n")

        # News section
        sections.append("--- Latest News ---")
        if news:
            for i, article in enumerate(news, 1):
                sections.append(
                    f"{i}. [{article['provider']}] {article['title']}\n"
                    f"   Published: {article['publish_time']}\n"
                    f"   Summary: {article['summary'][:200] if article['summary'] else 'N/A'}"
                )
        else:
            sections.append("No recent news found.")

        # Earnings section
        sections.append("\n--- Earnings Information ---")
        if earnings["upcoming_earnings"]:
            e = earnings["upcoming_earnings"]
            sections.append(
                f"Next Earnings Date: {e['date']}"
                f" | EPS Estimate: {e['eps_estimate'] or 'N/A'}"
            )
        else:
            sections.append("No upcoming earnings date found.")

        if earnings["recent_earnings"]:
            sections.append("Recent Earnings History:")
            for e in earnings["recent_earnings"]:
                surprise = (
                    f"{e['surprise_pct']}%" if e["surprise_pct"] is not None else "N/A"
                )
                sections.append(
                    f"  {e['date']}: EPS Est={e['eps_estimate'] or 'N/A'}, "
                    f"Reported={e['reported_eps'] or 'N/A'}, Surprise={surprise}"
                )

        # Key metrics section
        sections.append("\n--- Key Financial Metrics ---")
        if earnings["key_metrics"]:
            for k, v in earnings["key_metrics"].items():
                sections.append(f"  {k}: {v}")
        else:
            sections.append("No financial metrics available.")

        return "\n".join(sections)
