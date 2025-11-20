"""Metadata filtering helpers for Bedrock knowledge base calls."""
from __future__ import annotations

from typing import Dict, List, Optional

from .config import MetadataConfig


def parse_metadata_args(
    metadata_args: List[str], metadata_config: Optional[MetadataConfig] = None
) -> Dict[str, str]:
    """Parses CLI metadata flags `key=value` into a dictionary."""

    config = metadata_config or MetadataConfig()
    filters: Dict[str, str] = {}
    for pair in metadata_args:
        if config.key_value_separator not in pair:
            raise ValueError(
                f"Metadata filter '{pair}' must use the form key{config.key_value_separator}value"
            )
        key, value = pair.split(config.key_value_separator, 1)
        if config.strip_whitespace:
            key = key.strip()
            value = value.strip()
        if not key:
            raise ValueError("Metadata filter key cannot be empty")
        if not config.allow_empty_values and not value:
            raise ValueError(f"Metadata filter '{key}' cannot have an empty value")
        filters[key] = value
    return filters
