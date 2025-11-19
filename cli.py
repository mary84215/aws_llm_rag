"""CLI for interacting with AWS Bedrock Knowledge Bases via boto3."""
from __future__ import annotations

import argparse
import json
import sys
from typing import List

from kb_tool.config import BedrockConfig
from kb_tool.generator import ResponseGenerator
from kb_tool.kb_client import KnowledgeBaseClient
from kb_tool.metadata import parse_metadata_args


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Interact with AWS Bedrock Knowledge Bases and run metadata filtered queries.",
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Question or search query depending on the command",
    )
    parser.add_argument(
        "--metadata",
        nargs="*",
        default=[],
        help="Metadata filters formatted as key=value pairs",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Override number of retrieval results",
    )
    parser.add_argument(
        "--search-type",
        default=None,
        choices=["SEMANTIC", "HYBRID"],
        help="Vector search strategy (default uses config value)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Sampling temperature for the text model (default uses config value)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Maximum tokens in the model response (default uses config value)",
    )
    parser.add_argument(
        "--instructions",
        help="Optional override for the system instructions",
    )
    parser.add_argument(
        "--mode",
        default="retrieve",
        choices=["retrieve", "generate", "test"],
        help="Operation mode",
    )
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.query and args.mode != "test":
        parser.error("A query is required unless running in test mode")

    config = BedrockConfig.from_env()
    kb_client = KnowledgeBaseClient(config)

    metadata_filters = parse_metadata_args(args.metadata, config.metadata)

    if args.mode == "test":
        print("Performing a lightweight health check against the knowledge base...")
        sample_query = args.query or config.retrieval.health_check_query
        chunks = kb_client.retrieve(
            sample_query,
            metadata_filters=metadata_filters,
            number_of_results=args.top_k,
            search_type=args.search_type,
        )
        print(json.dumps({"retrieved": len(chunks)}, indent=2, ensure_ascii=False))
        return 0

    chunks = kb_client.retrieve(
        args.query,
        metadata_filters=metadata_filters,
        number_of_results=args.top_k,
        search_type=args.search_type,
    )

    if args.mode == "retrieve":
        print(json.dumps({"chunks": chunks}, indent=2, ensure_ascii=False))
        return 0

    generator = ResponseGenerator(config)
    answer = generator.generate(
        args.query,
        chunks,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        instructions=args.instructions,
    )
    print(json.dumps({"answer": answer, "snippets": chunks}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
