import logging
import os

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from src.macd_trader.tools import YFinanceMACDTool
from src.llm import LLM
from src.macd_trader.tools.news_tools import YFinanceNewsTool

logger = logging.getLogger(__name__)

# Initialize tools and LLM
macd_tool = YFinanceMACDTool()
yf_news_tool = YFinanceNewsTool()
llm = LLM.deepseek()

# Optionally load SerperDevTool if SERPER_API_KEY is configured
search_tool = None
if os.getenv("SERPER_API_KEY"):
    try:
        from crewai_tools import SerperDevTool

        search_tool = SerperDevTool()
        logger.info("SerperDevTool loaded successfully.")
    except ImportError:
        logger.warning(
            "crewai_tools not installed. Web search disabled. "
            "Install with: pip install crewai-tools"
        )
else:
    logger.info(
        "SERPER_API_KEY not set. Web search disabled, using YFinance news only."
    )


@CrewBase
class TradingCrew:
    """TradingCrew: 2 Agents + 3 Tasks architecture.

    Agents:
        - market_researcher: searches company news, earnings, financial metrics
        - trading_analyst: fetches MACD data, analyzes signals, makes decisions

    Tasks:
        - research_news_task: gather news and financial data
        - analyze_macd_task: MACD analysis + comprehensive decision
        - generate_report_task: write Chinese investment report
    """

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # --- Agents --- #

    @agent
    def market_researcher(self) -> Agent:
        researcher_tools = [yf_news_tool]
        if search_tool is not None:
            researcher_tools.append(search_tool)
        return Agent(
            config=self.agents_config["market_researcher"],
            tools=researcher_tools,
            llm=llm,
            verbose=True,
        )

    @agent
    def trading_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["trading_analyst"],
            tools=[macd_tool],
            llm=llm,
            verbose=True,
        )

    # --- Tasks --- #

    @task
    def research_news_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_news_task"],
            agent=self.market_researcher(),
        )

    @task
    def analyze_macd_task(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_macd_task"],
            agent=self.trading_analyst(),
            context=[self.research_news_task()],
        )

    @task
    def generate_report_task(self) -> Task:
        return Task(
            config=self.tasks_config["generate_report_task"],
            agent=self.trading_analyst(),
            context=[self.analyze_macd_task()],
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Trading Crew with 2 agents and 3 sequential tasks."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
