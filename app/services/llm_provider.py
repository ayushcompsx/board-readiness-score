"""
LLM provider abstraction (Section 8).

Both agents call get_llm() instead of constructing ChatOllama/ChatGroq
directly. Switching providers is a config change (MODEL_PROVIDER in
.env), not a code change.

Ollama: free, fully self-hosted, but slow on constrained hardware.
Groq: free-tier hosted API, much faster.
"""
from langchain_core.language_models.chat_models import BaseChatModel

from app.config.settings import settings


def get_llm(temperature: float = 0.2) -> BaseChatModel:
    if settings.model_provider == "groq":
        from langchain_groq import ChatGroq

        if not settings.groq_api_key:
            raise ValueError(
                "MODEL_PROVIDER is set to 'groq' but GROQ_API_KEY is empty. "
                "Get a free key at https://console.groq.com/keys and set it "
                "in your .env file."
            )
        return ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            temperature=temperature,
            max_tokens=4096,
            reasoning_effort="low",
            model_kwargs={"response_format": {"type": "json_object"}},
        )

    if settings.model_provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=temperature,
            timeout=180,
        )

    raise ValueError(
        f"Unknown MODEL_PROVIDER '{settings.model_provider}'. "
        f"Expected 'ollama' or 'groq'."
    )
