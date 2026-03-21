from core_ai.completions import (
    LLMBudgetExceededError,
    LLMCompletion,
    LLMError,
    LLMRateLimitError,
    GoogleAIStudioGenerateContentClient,
    JSONCompletionClient as LLMClient,
    OllamaChatClient,
    OpenAIChatCompletionsClient,
    StubLLMClient,
    build_llm_client as _build_llm_client,
)


def build_llm_client(settings) -> LLMClient:
    return _build_llm_client(settings, logger_name="ponti-ai.llm")
