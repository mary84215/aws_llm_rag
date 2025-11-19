"""Functions that turn KB retrievals into model invocations."""
from __future__ import annotations

import json
from typing import Dict, List

import boto3

from .config import BedrockConfig


class ResponseGenerator:
    """Uses a Bedrock text model to create responses grounded in KB snippets."""

    def __init__(self, config: BedrockConfig):
        self.config = config
        self._session = boto3.Session(region_name=config.region)
        self._runtime = self._session.client("bedrock-runtime", region_name=config.region)

    def generate(
        self,
        query: str,
        chunks: List[Dict[str, object]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        instructions: str | None = None,
    ) -> str:
        """Calls the configured model with the provided context."""

        gen_cfg = self.config.generation
        context = self._build_context_block(chunks)
        resolved_temperature = temperature if temperature is not None else gen_cfg.temperature
        resolved_max_tokens = max_tokens if max_tokens is not None else gen_cfg.max_tokens
        resolved_instructions = instructions or gen_cfg.instructions
        formatted_prompt = gen_cfg.context_template.format(context=context, query=query)
        payload = {
            "anthropic_version": gen_cfg.anthropic_version,
            "max_tokens": resolved_max_tokens,
            "temperature": resolved_temperature,
            "system": resolved_instructions,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": formatted_prompt,
                        }
                    ],
                }
            ],
        }

        response = self._runtime.invoke_model(
            modelId=self.config.model_id,
            body=json.dumps(payload),
            accept="application/json",
            contentType="application/json",
        )
        body = json.loads(response["body"].read())
        outputs = body.get("output", [])
        text_parts: List[str] = []
        for output in outputs:
            for content in output.get("content", []):
                if content.get("type") == "text":
                    text_parts.append(content.get("text", ""))
        return "".join(text_parts)

    @staticmethod
    def _build_context_block(chunks: List[Dict[str, object]]) -> str:
        lines = []
        for index, chunk in enumerate(chunks, start=1):
            metadata = chunk.get("metadata") or {}
            header = f"Snippet {index}: " + ", ".join(f"{k}={v}" for k, v in metadata.items())
            lines.append(header.strip())
            lines.append(chunk.get("content", ""))
            lines.append("")
        return "\n".join(lines)
