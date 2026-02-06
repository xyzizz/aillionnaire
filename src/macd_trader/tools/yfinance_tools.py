import logging

import pandas as pd
import yfinance as yf
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from ta.trend import MACD

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class StockDataToolsInput(BaseModel):
    ticker: str = Field(
        ..., description="The stock ticker symbol to analyze (e.g., AAPL, MSFT)"
    )
    mode: str = Field(
        default="macd",
        description="Analysis mode: 'macd' for MACD indicator calculation",
    )


class YFinanceMACDTool(BaseTool):
    name: str = "QuoteMACDTool"
    description: str = (
        "Fetches historical stock data and calculates MACD technical indicators. "
        "Input ticker can be Yahoo Finance format (NVDA) or LongBridge format (NVDA.US)."
    )
    args_schema: type[BaseModel] = StockDataToolsInput

    @staticmethod
    def _normalize_ticker(ticker: str) -> str:
        """Convert LongBridge-style ticker (NVDA.US) to Yahoo Finance format (NVDA)."""
        if ticker.endswith(".US"):
            return ticker[:-3]
        return ticker

    def _fetch_data(
        self, stock_ticker: str, period: str = "3mo", interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Retrieves historical stock data from Yahoo Finance API.

        Args:
            stock_ticker: Stock symbol to fetch data for
            period: Historical data timeframe (default: 3 months)
            interval: Data aggregation interval (default: daily)

        Returns:
            DataFrame containing historical price data or empty DataFrame on failure
        """
        stock = yf.Ticker(stock_ticker)
        try:
            # Fetch initial data with requested parameters
            hist = stock.history(period=period, interval=interval)
            if hist.empty:
                logging.warning(
                    f"No history found for {stock_ticker} with period={period}, interval={interval}"
                )
                # Fall back to longer timeframe if initial request returns no data
                hist = stock.history(period="1y", interval="1d")
                if hist.empty:
                    logging.error(
                        f"Could not fetch any historical data for {stock_ticker}"
                    )
                    return pd.DataFrame()
            return hist
        except Exception as e:
            logging.error(f"Error fetching history for {stock_ticker}: {e}")
            return pd.DataFrame()

    def get_stock_price(self, ticker: str) -> str:
        try:
            stock = yf.Ticker(ticker)
            # Get recent historical data for closing price
            hist = stock.history(period="5d", interval="1d")
            if not hist.empty:
                latest_price = hist["Close"].iloc[-1]
                latest_timestamp = hist.index[-1].strftime("%Y-%m-%d %H:%M:%S")
                logging.info(
                    f"Latest price for {ticker}: {latest_price} at {latest_timestamp}"
                )
                return f"The latest closing price for {ticker} is ${latest_price:.2f} as of {latest_timestamp}."
            else:
                # Alternative price sources if historical data unavailable
                info = stock.info
                current_price = (
                    info.get("currentPrice")
                    or info.get("regularMarketPrice")
                    or info.get("previousClose")
                )
                if current_price:
                    logging.info(
                        f"Current price for {ticker} from info: {current_price}"
                    )
                    return f"The current price for {ticker} is ${current_price:.2f}."
                else:
                    logging.warning(
                        f"Could not retrieve latest closing price for {ticker}."
                    )
                    return f"Could not retrieve the latest closing price for {ticker}."
        except Exception as e:
            logging.error(f"Error fetching stock price for {ticker}: {e}")
            return f"Error fetching stock price for {ticker}: {e}"

    def get_macd(self, ticker: str) -> str:
        """
        Calculates and returns MACD technical indicator data for a stock.

        Computes the MACD line, signal line, and histogram values using
        the TA library with default parameters (12,26,9).

        Args:
            ticker: Stock symbol to calculate MACD for

        Returns:
            Tuple of (hist_list, latest_info) with NaN rows filtered out
        """
        yf_ticker = self._normalize_ticker(ticker)
        hist = self._fetch_data(yf_ticker)
        if hist.empty:
            return f"Could not calculate MACD for {ticker} due to data fetching issues."

        try:
            # Calculate MACD indicators using technical analysis library
            macd = MACD(hist["Close"])
            hist["MACD"] = macd.macd()
            hist["MACD_Signal"] = macd.macd_signal()
            hist["MACD_Hist"] = macd.macd_diff()  # Histogram

            # Extract latest indicator values for logging
            latest_data = hist.iloc[-1]
            latest_timestamp = hist.index[-1].strftime("%Y-%m-%d")
            macd_value = latest_data["MACD"]
            signal_value = latest_data["MACD_Signal"]
            hist_value = latest_data["MACD_Hist"]

            if pd.isna(macd_value) or pd.isna(signal_value):
                logging.warning(
                    f"MACD calculation resulted in NaN for {ticker}. Check data period."
                )
                return (
                    f"Could not calculate valid MACD for {ticker}. Insufficient data?"
                )

            logging.info(
                f"MACD for {ticker} ({latest_timestamp}): MACD={macd_value:.2f}, Signal={signal_value:.2f}, Hist={hist_value:.2f}"
            )

            latest_info = (
                f"Latest MACD data for {ticker} ({latest_timestamp}):\n"
                f"  Close Price: ${latest_data['Close']:.2f}\n"
                f"  MACD Line: {macd_value:.4f}\n"
                f"  Signal Line: {signal_value:.4f}\n"
                f"  MACD Histogram: {hist_value:.4f}"
            )

            # Filter out NaN rows and add timestamp column for clean output
            valid = hist.dropna(subset=["MACD", "MACD_Signal", "MACD_Hist"])
            valid["timestamp"] = valid.index.strftime("%Y-%m-%dT%H:%M:%S")
            hist_list = valid[
                ["Close", "MACD", "MACD_Signal", "MACD_Hist", "timestamp"]
            ].to_dict(orient="records")

            return hist_list, latest_info

        except Exception as e:
            logging.error(f"Error calculating MACD for {ticker}: {e}")
            return f"Error calculating MACD for {ticker}: {e}"

    def _run(self, ticker: str, mode: str = "macd") -> str:
        return self.get_macd(ticker)
