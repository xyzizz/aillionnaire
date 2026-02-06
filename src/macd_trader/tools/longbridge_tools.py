import datetime
import logging

import pandas as pd
from crewai.tools import BaseTool
from longbridge.openapi import AdjustType, Candlestick, Config, Period, QuoteContext
from pydantic import BaseModel, Field
from ta.trend import MACD

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


lb_config = Config.from_env()
lb_ctx = QuoteContext(lb_config)


class LBQuoteHistoryInput(BaseModel):
    """Input model for fetching historical stock data."""

    ticker: str = Field(
        description="The stock ticker symbol to fetch data for. E.g., AAPL.US"
    )


class LongBridgeMACDTool(BaseTool):
    name: str = "QuoteMACDTool"
    description: str = "Retrieves historical stock data and calculates MACD technical indicators for stock trend analysis."
    args_schema: type[BaseModel] = LBQuoteHistoryInput

    def get_history(self, ticker: str, start, end) -> pd.DataFrame:
        """Fetches historical data for the specified stock ticker."""
        history: list[Candlestick] = lb_ctx.history_candlesticks_by_date(
            symbol=ticker,
            period=Period.Day,
            adjust_type=AdjustType.NoAdjust,
            start=start,
            end=end,
        )
        df = pd.DataFrame(
            [(candle.close, candle.timestamp) for candle in history],
            columns=["Close", "timestamp"],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
        return df

    def get_macd(self, ticker: str) -> tuple[list[dict], str]:
        """Calculates the MACD indicator for a given stock ticker and returns the latest values."""
        hist = self.get_history(
            ticker,
            start=datetime.date.today() - datetime.timedelta(days=90),
            end=datetime.date.today(),
        )
        if hist.empty:
            return f"Could not calculate MACD for {ticker} due to data fetching issues."

        try:
            # Calculate MACD
            macd = MACD(hist["Close"])
            hist["MACD"] = macd.macd()
            hist["MACD_Signal"] = macd.macd_signal()
            hist["MACD_Hist"] = macd.macd_diff()  # Histogram

            # Get the latest values
            latest_data = hist.iloc[-1]
            latest_timestamp = hist.index[-1]
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

            hist["timestamp"] = hist.index
            hist_list = hist.to_dict(orient="records")
            latest_info = (
                f"Latest MACD data for {ticker} ({latest_timestamp}):\n"
                f"  Close Price: ${latest_data['Close']:.2f}\n"
                f"  MACD Line: {macd_value:.4f}\n"
                f"  Signal Line: {signal_value:.4f}\n"
                f"  MACD Histogram: {hist_value:.4f}"
            )
            return hist_list, latest_info

        except Exception as e:
            logging.error(f"Error calculating MACD for {ticker}: {e}")
            return f"Error calculating MACD for {ticker}: {e}"

    def _run(self, ticker: str, mode: str = "macd") -> tuple[list[dict], str]:
        """
        Runs the specified tool function (get_macd).
        """
        return self.get_macd(ticker)
