import os
import time
from typing import Any, Dict

import requests


class DeepSeekAPIError(Exception):
    """Raised when all DeepSeek API retry attempts have been exhausted."""

    def __init__(self, message: str, last_response: Any = None):
        super().__init__(message)
        self.last_response = last_response


def call_deepseek(content: str, config: dict) -> str:
    """Send markdown content to the DeepSeek API for processing.

    Reads API key from the ``DEEPSEEK_API_KEY`` environment variable and model
    / temperature / prompt settings from ``config["processing"]["deepseek_api"]``.
    Retries up to 3 times with exponential backoff (1 s, 2 s, 4 s).

    Args:
        content: The raw markdown text to process.
        config: Full application configuration dict.

    Returns:
        The processed text from the API response (``choices[0].message.content``).

    Raises:
        ValueError: If ``DEEPSEEK_API_KEY`` is not set.
        DeepSeekAPIError: If all retry attempts fail.
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("Missing DEEPSEEK_API_KEY environment variable")

    deepseek_cfg: Dict[str, Any] = config.get("processing", {}).get(
        "deepseek_api", {}
    )
    model = deepseek_cfg.get("model", "deepseek-v4-flash")
    temperature = deepseek_cfg.get("temperature", 0.3)
    max_tokens = deepseek_cfg.get("max_tokens", 4000)
    prompt_template = deepseek_cfg.get(
        "prompt_template",
        "请处理以下内容：\n\n{content}",
    )

    system_prompt = deepseek_cfg.get(
        "system_prompt",
        "你是一个专业的博客编辑器。"
        "不要修改任何图片链接语法，保持 ![alt](url) 和 ![[filename]] 格式原样。",
    )
    user_message = prompt_template.replace("{content}", content)

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    max_retries = 3
    last_error: str = ""
    last_response: Any = None

    for attempt in range(max_retries):
        try:
            print(f"  DeepSeek API call (attempt {attempt + 1}/{max_retries}) ...")
            resp = requests.post(url, headers=headers, json=payload, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                result = data["choices"][0]["message"]["content"]
                finish_reason = data["choices"][0].get("finish_reason", "unknown")
                print(f"  DeepSeek API returned {len(result)} chars (finish_reason: {finish_reason})")
                if finish_reason == "length":
                    print(f"  ⚠️  WARNING: Response truncated by max_tokens ({max_tokens})!")
                    print(f"  ⚠️  Consider increasing max_tokens in config.yaml")
                return result
            else:
                last_error = f"HTTP {resp.status_code}: {resp.text[:500]}"
                last_response = resp
                print(f"  DeepSeek API error: {last_error}")
        except requests.RequestException as e:
            last_error = str(e)
            print(f"  DeepSeek API request failed: {last_error}")

        if attempt < max_retries - 1:
            wait = 2 ** attempt  # 1s, 2s, 4s
            print(f"  Retrying in {wait}s ...")
            time.sleep(wait)

    raise DeepSeekAPIError(
        f"DeepSeek API call failed after {max_retries} attempts: {last_error}",
        last_response=last_response,
    )
