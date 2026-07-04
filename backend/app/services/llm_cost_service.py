"""Estimate LLM request costs based on provider, model, and token counts."""

MODEL_PRICING = {
    "deepseek": {
        "deepseek-v4-flash": {
            "prompt": 0.00002,
            "completion": 0.00006,
        },
        "deepseek-chat": {
            "prompt": 0.0001,
            "completion": 0.0002,
        },
        "deepseek-chat-v2": {
            "prompt": 0.0001,
            "completion": 0.0002,
        },
    },
    "openai": {
        "gpt-4o-mini": {
            "prompt": 0.00015,
            "completion": 0.0006,
        },
        "gpt-4o": {
            "prompt": 0.0025,
            "completion": 0.01,
        },
        "gpt-4-turbo": {
            "prompt": 0.01,
            "completion": 0.03,
        },
        "gpt-3.5-turbo": {
            "prompt": 0.0005,
            "completion": 0.0015,
        },
        "gpt-3.5-turbo-0125": {
            "prompt": 0.0005,
            "completion": 0.0015,
        },
    },
}


def estimate_llm_cost(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Return estimated request cost in USD.

    Args:
        provider: The LLM provider name (e.g., "deepseek", "openai").
        model: The model name (e.g., "deepseek-v4-flash", "gpt-4o-mini").
        prompt_tokens: Number of tokens in the prompt.
        completion_tokens: Number of tokens in the completion.

    Returns:
        Estimated cost in USD, or 0.0 if provider/model is unknown.
    """

    if prompt_tokens <= 0 and completion_tokens <= 0:
        return 0.0

    provider_pricing = MODEL_PRICING.get(provider)
    if provider_pricing is None:
        return 0.0

    model_pricing = provider_pricing.get(model)
    if model_pricing is None:
        return 0.0

    return (
        model_pricing["prompt"] * prompt_tokens / 1000
        + model_pricing["completion"] * completion_tokens / 1000
    )