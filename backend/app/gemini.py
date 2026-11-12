"""Gemini adapter: LLM output is schema-validated and never authorizes money movement."""
from typing import TypeVar
from pydantic import BaseModel
from .config import settings

T = TypeVar("T", bound=BaseModel)


class GeminiClient:
    """Small adapter that is easy to replace with a mock in agent tests."""
    async def generate(self, prompt: str, schema: type[T]) -> T:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini-enhanced analysis")
        from google import genai
        client = genai.Client(api_key=settings.gemini_api_key)
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config={"response_mime_type": "application/json", "response_json_schema": schema.model_json_schema(), "temperature": 0.1},
        )
        return schema.model_validate_json(response.text)
