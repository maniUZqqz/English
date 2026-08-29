"""
Shared AI service layer for the whole project.

Every app talks to the language model through this module. Configuration is
resolved at call time with this priority:
  1. AIConfig row in the database (editable in Django admin)
  2. .env / environment variables (settings.AI_*)
So the admin can paste an API key in the admin panel without touching files.
"""

import json
import re

from django.conf import settings
from openai import OpenAI


class AIDisabled(Exception):
    """AI features are switched off in admin, or no API key is configured."""


def get_ai_settings():
    """Resolve (api_key, base_url, model, is_active) from admin config falling back to .env."""
    from app.models import AIConfig
    config = AIConfig.get()
    api_key = settings.AI_API_KEY
    base_url = settings.AI_BASE_URL
    model = settings.AI_MODEL
    is_active = True
    if config:
        api_key = config.api_key.strip() or api_key
        base_url = config.base_url.strip() or base_url
        model = config.model_name.strip() or model
        is_active = config.is_active
    return api_key, base_url, model, is_active


def get_daily_limit():
    """سقف روزانه: مقدار ادمین اگر بزرگ‌تر از صفر باشد، وگرنه .env."""
    from app.models import AIConfig
    config = AIConfig.get()
    if config and config.daily_limit > 0:
        return config.daily_limit
    return getattr(settings, 'AI_DAILY_LIMIT', 100)


def chat_completion(messages, temperature=None, max_tokens=None):
    """Call the chat model and return the assistant message content (str)."""
    api_key, base_url, model, is_active = get_ai_settings()
    if not is_active:
        raise AIDisabled('AI features are currently disabled by the administrator.')
    if not api_key:
        raise AIDisabled('No AI API key configured. Set it in Django admin (AI Configuration) or .env.')

    client = OpenAI(base_url=base_url, api_key=api_key)
    kwargs = {'model': model, 'messages': messages}
    if temperature is not None:
        kwargs['temperature'] = temperature
    if max_tokens is not None:
        kwargs['max_tokens'] = max_tokens
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def strip_code_fence(text):
    """Remove ```json ... ``` style fences the model sometimes wraps output in."""
    text = text.strip()
    if text.startswith('```'):
        lines = text.splitlines()
        if lines and lines[0].lstrip().startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].lstrip().startswith('```'):
            lines = lines[:-1]
        text = '\n'.join(lines).strip()
    return text


def extract_json(text):
    """
    Parse a JSON object or array out of a model reply, tolerating extra prose
    and markdown fences. Raises ValueError if nothing parseable is found.
    """
    cleaned = strip_code_fence(text)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r'(\[.*\]|\{.*\})', cleaned, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError('No JSON found in model reply')
