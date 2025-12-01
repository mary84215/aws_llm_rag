"""Command line helpers for the three regression scenarios defined in test.py."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Callable, List, Optional

from tools.rephrase import rephrase_question
from tools.retrieve import generate_metadata_filter, retrieve_from_kb
from tools.retrieve_generate import ret_and_gen


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the rephrase, retrieve-and-generate, or retrieve test flows via the CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Scenario 1: rephrase question
    rephrase_parser = subparsers.add_parser(
        "rephrase",
        help="Invoke the Nova Pro based rephrase_question helper.",
    )
    rephrase_parser.add_argument("prompt", help="Prompt that should be rewritten in first-person formal tone.")
    rephrase_parser.set_defaults(handler=run_rephrase)

    # Scenario 2: retrieve and generate
    ret_gen_parser = subparsers.add_parser(
        "ret-gen",
        help="Call retrieve_and_generate() to build a draft and optionally save it to disk.",
    )
    ret_gen_parser.add_argument("prompt", help="Question that will be passed to Bedrock RetrieveAndGenerate.")
    ret_gen_parser.add_argument(
        "--kb-id",
        default=os.environ.get("KNOWLEDGE_BASE_ID"),
        help="Knowledge Base ID (default: $KNOWLEDGE_BASE_ID).",
    )
    ret_gen_parser.add_argument(
        "--model-arn",
        default=os.environ.get("MODEL_ARN"),
        help="Bedrock model ARN for generation (default: $MODEL_ARN).",
    )
    ret_gen_parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Override numberOfResults sent to RetrieveAndGenerate.",
    )
    ret_gen_parser.add_argument(
        "--save-output",
        nargs="?",
        const="output/ret_and_gen.md",
        default=None,
        help="Optional file path for storing the generated draft (default when flag used: output/ret_and_gen.md).",
    )
    ret_gen_parser.set_defaults(handler=run_ret_gen)

    # Scenario 3: retrieve chunks and/or metadata filters
    retrieve_parser = subparsers.add_parser(
        "retrieve",
        help="Run the standalone retrieve flow and inspect chunks or the metadata filter.",
    )
    retrieve_parser.add_argument("prompt", help="Question that should be answered from the Knowledge Base.")
    retrieve_parser.add_argument(
        "--kb-id",
        default=os.environ.get("KNOWLEDGE_BASE_ID"),
        help="Knowledge Base ID (default: $KNOWLEDGE_BASE_ID).",
    )
    retrieve_parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Override numberOfResults for the retrieve call.",
    )
    retrieve_parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Only output the generated metadata filter without calling retrieve().",
    )
    retrieve_parser.add_argument(
        "--show-raw",
        action="store_true",
        help="Include the full bedrock-agent-runtime.retrieve response in the output JSON.",
    )
    retrieve_parser.set_defaults(handler=run_retrieve)

    return parser


def _require(value: Optional[str], *, flag: str, env: str) -> str:
    if value:
        return value
    raise SystemExit(f"Missing required {flag}. Provide it explicitly or set the {env} environment variable.")


def run_rephrase(args: argparse.Namespace) -> int:
    rephrased = rephrase_question(args.prompt)
    print(json.dumps({"input": args.prompt, "rephrased": rephrased}, indent=2, ensure_ascii=False))
    return 0


def run_ret_gen(args: argparse.Namespace) -> int:
    kb_id = _require(args.kb_id, flag="--kb-id", env="KNOWLEDGE_BASE_ID")
    model_arn = _require(args.model_arn, flag="--model-arn", env="MODEL_ARN")

    response = ret_and_gen(
        args.prompt,
        kb_id,
        model_arn,
        number_of_results=args.top_k,
    )

    output = response.get("output", {}).get("text")
    payload = {"response": response}
    if output:
        payload["output_text"] = output

    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if output and args.save_output:
        output_path = Path(args.save_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(f"Saved generated text to {output_path}")

    return 0


def run_retrieve(args: argparse.Namespace) -> int:
    kb_id = _require(args.kb_id, flag="--kb-id", env="KNOWLEDGE_BASE_ID")
    metadata_filter = generate_metadata_filter(args.prompt)

    if args.metadata_only:
        print(json.dumps({"metadata_filter": metadata_filter}, indent=2, ensure_ascii=False))
        return 0

    response = retrieve_from_kb(
        args.prompt,
        kb_id,
        number_of_results=args.top_k,
        metadata_filter=metadata_filter,
    )

    chunks = response.get("retrievalResults", [])
    payload = {
        "chunks": chunks,
        "metadata_filter": metadata_filter,
    }
    if args.show_raw:
        payload["raw_response"] = response

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler: Optional[Callable[[argparse.Namespace], int]] = getattr(args, "handler", None)
    if handler is None:
        parser.error("A sub command is required. Use --help for the available commands.")
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
