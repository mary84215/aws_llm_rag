"""Knowledge base client for AWS Bedrock."""
from __future__ import annotations

from typing import Dict, List, Optional

import boto3

from .config import BedrockConfig, metadata_dict_from_key_values


class KnowledgeBaseClient:
    """Wraps the AWS Bedrock Agent Runtime client for KB retrieval."""

    def __init__(self, config: BedrockConfig):
        self.config = config
        self._session = boto3.Session(region_name=config.region)
        self._agent_runtime = self._session.client(
            "bedrock-agent-runtime", region_name=config.region
        )

    def retrieve(
        self,
        query: str,
        metadata_filters: Optional[Dict[str, str]] = None,
        number_of_results: Optional[int] = None,
        search_type: Optional[str] = None,
    ) -> List[Dict[str, object]]:
        """Retrieves relevant documents from the knowledge base."""

        if not query.strip():
            raise ValueError("Query cannot be empty")

        filter_payload = metadata_dict_from_key_values(metadata_filters or {})
        resolved_top_k = number_of_results or self.config.retrieval.top_k
        resolved_search_type = search_type or self.config.retrieval.search_type
        retrieval_configuration = {
            "vectorSearchConfiguration": {
                "numberOfResults": resolved_top_k,
                "overrideSearchType": resolved_search_type,
            }
        }
        if filter_payload:
            retrieval_configuration["vectorSearchConfiguration"]["filter"] = filter_payload

        response = self._agent_runtime.retrieve(
            knowledgeBaseId=self.config.knowledge_base_id,
            retrievalConfiguration=retrieval_configuration,
            retrievalQuery={"text": query},
        )

        formatted: List[Dict[str, object]] = []
        for item in response.get("retrievalResults", []):
            formatted.append(
                {
                    "content": item.get("content", {}).get("text", ""),
                    "score": item.get("score"),
                    "metadata": item.get("metadata", {}),
                    "referencedDocuments": item.get("referencedDocuments", []),
                }
            )
        return formatted

    @staticmethod
    def summarize_chunks(chunks: List[Dict[str, object]]) -> str:
        """Creates a single string concatenating retrieved chunks."""

        summary_lines = []
        for index, chunk in enumerate(chunks, start=1):
            metadata = chunk.get("metadata") or {}
            meta_desc = ", ".join(f"{k}={v}" for k, v in metadata.items())
            summary_lines.append(
                f"[Chunk {index} | score={chunk.get('score')}] {meta_desc}\n{chunk.get('content')}"
            )
        return "\n\n".join(summary_lines)
