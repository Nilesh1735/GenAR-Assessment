from __future__ import annotations

import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from src.llm.sections import SectionNarrative
from src.log import emit

load_dotenv()

_RETRYABLE = ("rate", "429", "timeout", "timed out", "503", "overloaded", "connection")


class LLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMConfig:
    model: str
    max_retries: int
    timeout: int


def load_config() -> LLMConfig:
    return LLMConfig(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        max_retries=int(os.getenv("GROQ_MAX_RETRIES", "5")),
        timeout=int(os.getenv("GROQ_TIMEOUT_SECONDS", "60")),
    )


def _api_key() -> str:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise LLMError("GROQ_API_KEY is not set; add it to your .env file")
    return key


class NarrativeGenerator:
    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or load_config()
        model = ChatGroq(
            model=self.config.model,
            api_key=_api_key(),
            temperature=0,
            timeout=self.config.timeout,
            max_retries=0,
        )
        self._model = model.with_structured_output(SectionNarrative)

    def generate(self, system_prompt: str, user_prompt: str) -> SectionNarrative:
        delay = 2.0
        last_error: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                return self._model.invoke(
                    [("system", system_prompt), ("human", user_prompt)]
                )
            except Exception as error:
                message = str(error).lower()
                if any(token in message for token in _RETRYABLE):
                    last_error = error
                    emit("llm_retry", level="warning", attempt=attempt, delay=delay)
                    time.sleep(delay)
                    delay = min(delay * 2, 30)
                    continue
                raise LLMError(str(error)) from error
        raise LLMError(f"exhausted {self.config.max_retries} retries: {last_error}")
