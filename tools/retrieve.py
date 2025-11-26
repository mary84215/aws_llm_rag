import boto3
import json
from typing import Optional

from botocore.config import Config

from tools.config import RetrieveConfig


def retrieve_from_kb(question: str,
                     knowledge_base_id: str,
                     region: str = RetrieveConfig.REGION,
                     number_of_results: Optional[int] = None) -> dict:
    """
    從指定的知識庫進行檢索 (Retrieve API)，回傳最相關的內容塊。
    """
    client = boto3.client(
        "bedrock-agent-runtime",
        region_name=region,
        config=Config(
            connect_timeout=300,
            read_timeout=300,
            retries={"max_attempts": 2}
        )
    )

    retrieval_configuration = RetrieveConfig.retrieval_configuration(number_of_results)

    response = client.retrieve(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery={"text": question},
        retrievalConfiguration=retrieval_configuration
    )

    return response

# if __name__ == "__main__":
#     KB_ID = "YOUR_KB_ID"
#     if KB_ID == "YOUR_KB_ID":
#         raise ValueError("Please replace YOUR_KB_ID with the actual knowledge base ID before running this file.")
#     question = "請說明 SAS 簽呈 的流程與注意事項是什麼？"
#     print("Testing retrieve_from_kb...")
#     print(json.dumps(retrieve_from_kb(question, KB_ID), indent=2, ensure_ascii=False))
