"""Helper for invoking a Bedrock Agent session and persisting the outputs."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import boto3
from botocore.config import Config

from tools.config import AgentInvocationConfig


def _project_output_dir() -> Path:
    """Return the root-level output directory, creating it when necessary."""
    root_dir = Path(__file__).resolve().parent.parent
    output_dir = root_dir / AgentInvocationConfig.OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _serialize_event(event: Dict[str, object]) -> Dict[str, object]:
    """Convert streaming events into JSON serializable chunks."""
    chunk_payload = event.get("chunk")
    if isinstance(chunk_payload, dict):
        chunk_bytes = chunk_payload.get("bytes", b"")
        chunk_text = chunk_bytes.decode("utf-8") if isinstance(chunk_bytes, (bytes, bytearray)) else str(chunk_bytes)
        return {"type": "chunk", "text": chunk_text}

    trace_payload = event.get("trace")
    if isinstance(trace_payload, dict):
        trace_bytes = None
        if isinstance(trace_payload.get("trace"), dict):
            trace_bytes = trace_payload["trace"].get("bytes")
        if trace_bytes is None:
            trace_bytes = trace_payload.get("bytes")
        trace_text = trace_bytes.decode("utf-8") if isinstance(trace_bytes, (bytes, bytearray)) else str(trace_bytes)
        try:
            trace_json = json.loads(trace_text)
        except (json.JSONDecodeError, TypeError):
            trace_json = trace_text
        return {"type": "trace", "content": trace_json}

    # Fallback for other event types (e.g., metadata or citations)
    sanitized: Dict[str, object] = {"type": "event", "payload": {}}
    for key, value in event.items():
        if isinstance(value, dict) and "bytes" in value:
            sanitized["payload"][key] = value.get("bytes").decode("utf-8")  # type: ignore[arg-type]
        else:
            sanitized["payload"][key] = value
    return sanitized


def invoke_agent(
    prompt: str,
    *,
    agent_id: str,
    agent_alias_id: str,
    session_id: Optional[str] = None,
    region: str = AgentInvocationConfig.REGION,
    output_markdown_name: Optional[str] = None,
    output_chunk_name: Optional[str] = None,
) -> Dict[str, object]:
    """Invoke an Agent and persist both the markdown response and chunk log."""

    client = boto3.client(
        "bedrock-agent-runtime",
        region_name=region,
        config=Config(connect_timeout=300, read_timeout=300, retries={"max_attempts": 2}),
    )

    active_session_id = session_id or uuid.uuid4().hex

    response = client.invoke_agent(
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=active_session_id,
        inputText=prompt,
    )

    output_segments: List[str] = []
    chunk_records: List[Dict[str, object]] = []

    for event in response.get("responseStream", []):
        serialized = _serialize_event(event)
        chunk_records.append(serialized)
        if serialized["type"] == "chunk":
            output_segments.append(serialized.get("text", ""))

    generated_markdown = "".join(output_segments)

    output_dir = _project_output_dir()
    markdown_path = output_dir / (
        output_markdown_name or AgentInvocationConfig.RESPONSE_MD_FILENAME
    )
    chunk_path = output_dir / (
        output_chunk_name or AgentInvocationConfig.CHUNKS_JSON_FILENAME
    )

    markdown_path.write_text(generated_markdown, encoding="utf-8")
    chunk_path.write_text(json.dumps(chunk_records, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "sessionId": active_session_id,
        "markdown_path": str(markdown_path),
        "chunk_path": str(chunk_path),
        "text": generated_markdown,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Invoke a Bedrock Agent and save outputs.")
    parser.add_argument("prompt", help="Prompt text to send to the agent.")
    parser.add_argument("--agent-id", required=True, help="Target Bedrock Agent ID.")
    parser.add_argument("--agent-alias-id", required=True, help="Agent alias ID to invoke.")
    parser.add_argument("--session-id", help="Optional session id to continue a conversation.")
    parser.add_argument(
        "--region",
        default=AgentInvocationConfig.REGION,
        help=f"AWS region, default: {AgentInvocationConfig.REGION}",
    )
    parser.add_argument(
        "--output-md",
        help="Custom markdown filename (stored under the output directory).",
    )
    parser.add_argument(
        "--output-json",
        help="Custom chunk JSON filename (stored under the output directory).",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    result = invoke_agent(
        args.prompt,
        agent_id=args.agent_id,
        agent_alias_id=args.agent_alias_id,
        session_id=args.session_id,
        region=args.region,
        output_markdown_name=args.output_md,
        output_chunk_name=args.output_json,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
