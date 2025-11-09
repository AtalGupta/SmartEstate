import os
import os
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel


def get_llm(default_to_fake: bool = False) -> Optional[BaseChatModel]:
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    model = os.getenv("LLM_MODEL", "llama3.1:8b")
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))

    if provider == "ollama":
        try:
            from langchain_community.chat_models import ChatOllama
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            return ChatOllama(model=model, base_url=base_url, temperature=temperature)
        except Exception:
            if not default_to_fake:
                return None

    if provider in ("openai", "openai_compat"):
        try:
            from langchain_openai import ChatOpenAI
            base_url = os.getenv("OPENAI_BASE_URL") if provider == "openai_compat" else None
            return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), base_url=base_url, temperature=temperature)
        except Exception:
            if not default_to_fake:
                return None

    if default_to_fake or provider == "fake":
        try:
            from langchain_core.language_models import FakeListChatModel
            return FakeListChatModel(responses=["Placeholder response"])  # type: ignore[return-value]
        except Exception:
            return None

    return None
