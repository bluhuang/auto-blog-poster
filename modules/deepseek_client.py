from typing import Optional


def call_deepseek(content: str, config: dict) -> Optional[str]:
    """Send markdown content to DeepSeek API for processing / optimisation.

    Currently returns a mock result. Replace with real API call later.
    """
    print("call_deepseek: using mock implementation")
    return f"processed: {content}"
