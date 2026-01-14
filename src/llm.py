import os
from crewai import LLM as _LLM


class LLM:
    @classmethod
    def default(cls) -> _LLM:
        return cls.deepseek()

    @classmethod
    def deepseek(cls) -> _LLM:
        deepseek_llm = _LLM(
            model="deepseek/deepseek-chat",
            base_url="https://api.deepseek.com/v1/",
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            temperature=0,
        )
        return deepseek_llm

    @classmethod
    def ollama_deepseek(cls) -> _LLM:
        ollama_deepseek_llm = _LLM(
            model="ollama/deepseek-r1:1.5b", base_url="http://localhost:11434"
        )
        return ollama_deepseek_llm
