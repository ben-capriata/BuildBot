import logging

from openai import OpenAI

from config import PROVIDERS
from db import log_llm_call

logger = logging.getLogger(__name__)

# Track which provider last succeeded
last_provider = None


def get_chat_response(messages):
    """Send a full message history to the LLM. Returns (response_text, provider_name)."""
    global last_provider

    for provider in PROVIDERS:
        if not provider["api_key"]:
            continue
        try:
            client = OpenAI(
                base_url=provider["base_url"],
                api_key=provider["api_key"],
                timeout=10.0,
            )
            response = client.chat.completions.create(
                model=provider["model"],
                messages=messages,
                max_tokens=1024,
            )
            usage = response.usage
            log_llm_call(
                provider=provider["name"],
                model=provider["model"],
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None,
            )
            last_provider = provider["name"]
            return response.choices[0].message.content, provider["name"]

        except Exception as e:
            logger.warning("Provider %s failed: %s", provider["name"], e)
            log_llm_call(
                provider=provider["name"],
                model=provider["model"],
                success=False,
                error=str(e)[:500],
            )
            continue

    return None, None


def get_llm_response(system_prompt, user_prompt):
    """Try each provider in the fallback chain. Returns (response_text, provider_name)."""
    global last_provider

    for provider in PROVIDERS:
        if not provider["api_key"]:
            continue
        try:
            client = OpenAI(
                base_url=provider["base_url"],
                api_key=provider["api_key"],
                timeout=10.0,
            )
            response = client.chat.completions.create(
                model=provider["model"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1024,
            )
            usage = response.usage
            log_llm_call(
                provider=provider["name"],
                model=provider["model"],
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None,
            )
            last_provider = provider["name"]
            return response.choices[0].message.content, provider["name"]

        except Exception as e:
            logger.warning("Provider %s failed: %s", provider["name"], e)
            log_llm_call(
                provider=provider["name"],
                model=provider["model"],
                success=False,
                error=str(e)[:500],
            )
            continue

    return None, None
