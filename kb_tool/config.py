"""Configuration helpers for AWS Bedrock knowledge base tooling."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


def _instructions_default() -> str:
    return (
        "You are a helpful assistant that answers using the knowledge base"
        " snippets when applicable."
    )


def _context_template_default() -> str:
    return (
        "You must base your answer on the provided knowledge base context. "
        "If the context does not contain the answer, state that clearly.\n"
        "\nContext:\n{context}\n\nUser question: {query}"
    )


@dataclass
class MetadataConfig:
    """Controls how CLI metadata arguments are parsed."""

    key_value_separator: str = "="
    strip_whitespace: bool = True
    allow_empty_values: bool = True


@dataclass
class RetrievalConfig:
    """Default settings for knowledge base retrieval."""

    top_k: int = 5
    search_type: str = "SEMANTIC"
    health_check_query: str = "health check"


@dataclass
class GenerationConfig:
    """Default settings for RAG-style model generation."""

    instructions: str = field(default_factory=_instructions_default)
    temperature: float = 0.1
    max_tokens: int = 800
    anthropic_version: str = "bedrock-2023-05-31"
    context_template: str = field(default_factory=_context_template_default)

    @staticmethod
    def instructions_default() -> str:
        return _instructions_default()


@dataclass
class BedrockConfig:
    """Holds core configuration for interacting with Bedrock."""

    region: str
    knowledge_base_id: str
    model_id: str
    metadata: MetadataConfig = field(default_factory=MetadataConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)

    @classmethod
    def from_env(cls) -> "BedrockConfig":
        """Loads configuration from environment variables with sane defaults."""

        region = _get_env_value("AWS_REGION") or _get_env_value("AWS_DEFAULT_REGION")
        if not region:
            raise RuntimeError(
                "Environment variable AWS_REGION or AWS_DEFAULT_REGION is required"
            )
        knowledge_base_id = _get_env_value("BEDROCK_KB_ID")
        if not knowledge_base_id:
            raise RuntimeError("Environment variable BEDROCK_KB_ID is required")
        model_id = _get_env_value("BEDROCK_MODEL_ID") or "anthropic.claude-3-sonnet-20240229-v1:0"

        retrieval_defaults = RetrievalConfig()
        retrieval_cfg = RetrievalConfig(
            top_k=int(_get_env_value("BEDROCK_KB_TOP_K") or retrieval_defaults.top_k),
            search_type=_get_env_value("BEDROCK_SEARCH_TYPE") or retrieval_defaults.search_type,
            health_check_query=_get_env_value("BEDROCK_HEALTHCHECK_QUERY")
            or retrieval_defaults.health_check_query,
        )

        generation_defaults = GenerationConfig()
        generation_cfg = GenerationConfig(
            instructions=_get_env_value("BEDROCK_INSTRUCTIONS")
            or GenerationConfig.instructions_default(),
            temperature=float(
                _get_env_value("BEDROCK_TEMPERATURE") or generation_defaults.temperature
            ),
            max_tokens=int(_get_env_value("BEDROCK_MAX_TOKENS") or generation_defaults.max_tokens),
            anthropic_version=generation_defaults.anthropic_version,
            context_template=generation_defaults.context_template,
        )

        metadata_defaults = MetadataConfig()
        metadata_cfg = MetadataConfig(
            key_value_separator=_get_env_value("BEDROCK_METADATA_SEPARATOR")
            or metadata_defaults.key_value_separator,
            strip_whitespace=_env_flag(
                "BEDROCK_METADATA_STRIP_WHITESPACE", default=metadata_defaults.strip_whitespace
            ),
            allow_empty_values=_env_flag(
                "BEDROCK_METADATA_ALLOW_EMPTY_VALUES", default=metadata_defaults.allow_empty_values
            ),
        )

        return cls(
            region=region,
            knowledge_base_id=knowledge_base_id,
            model_id=model_id,
            metadata=metadata_cfg,
            retrieval=retrieval_cfg,
            generation=generation_cfg,
        )

    @staticmethod
    def instructions_default() -> str:
        return _instructions_default()


def metadata_dict_from_key_values(key_values: Dict[str, str]) -> Optional[Dict[str, object]]:
    """Creates a simple equals filter payload for the KB vector search."""

    if not key_values:
        return None

    equals_filters = []
    for key, value in key_values.items():
        equals_filters.append(
            {
                "key": key,
                "value": {
                    "stringValue": value,
                },
            }
        )

    return {"equals": equals_filters}


def _get_env_value(name: str) -> Optional[str]:
    """Reads an environment variable, falling back to VS Code settings if available."""

    value = os.getenv(name)
    if value is not None:
        return value

    settings_env = _load_settings_env()
    return settings_env.get(name)


def _env_flag(name: str, default: bool) -> bool:
    """Reads a boolean flag from environment/settings.json."""

    raw_value = _get_env_value(name)
    if raw_value is None:
        return default
    lowered = raw_value.strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    return default


_SETTINGS_ENV_CACHE: Optional[Dict[str, str]] = None


def _load_settings_env() -> Dict[str, str]:
    """Loads environment-style variables from settings.json for local workflows."""

    global _SETTINGS_ENV_CACHE
    if _SETTINGS_ENV_CACHE is not None:
        return _SETTINGS_ENV_CACHE

    settings_path = _resolve_settings_path()
    if not settings_path or not settings_path.exists():
        _SETTINGS_ENV_CACHE = {}
        return _SETTINGS_ENV_CACHE

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _SETTINGS_ENV_CACHE = {}
        return _SETTINGS_ENV_CACHE

    env_data: Dict[str, str] = {}

    for key in ("bedrock.env", "awsBedrock.env"):
        section = data.get(key)
        if isinstance(section, dict):
            env_data.update({k: str(v) for k, v in section.items()})

    platform_section = data.get(_platform_settings_key())
    if isinstance(platform_section, dict):
        env_data.update({k: str(v) for k, v in platform_section.items()})

    generic_terminal = data.get("terminal.integrated.env")
    if isinstance(generic_terminal, dict):
        env_data.update({k: str(v) for k, v in generic_terminal.items()})

    _SETTINGS_ENV_CACHE = env_data
    return _SETTINGS_ENV_CACHE


def _resolve_settings_path() -> Optional[Path]:
    """Determines where settings.json lives, allowing environment overrides."""

    explicit_path = os.getenv("BEDROCK_SETTINGS_PATH")
    if explicit_path:
        return Path(explicit_path).expanduser()

    candidates = [
        Path.cwd() / ".vscode" / "settings.json",
        Path.cwd() / "settings.json",
        Path(__file__).resolve().parents[1] / ".vscode" / "settings.json",
        Path(__file__).resolve().parents[1] / "settings.json",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def _platform_settings_key() -> str:
    """Maps the current OS to VS Code's terminal env key."""

    if sys.platform == "darwin":
        return "terminal.integrated.env.osx"
    if sys.platform.startswith("linux"):
        return "terminal.integrated.env.linux"
    if sys.platform.startswith("win"):
        return "terminal.integrated.env.windows"
    return "terminal.integrated.env"
