import boto3
import json
from botocore.config import Config

def retrieve_from_kb(question: str,
                     knowledge_base_id: str,
                     region: str = "us-east-1",
                     number_of_results: int = 3) -> dict:
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

    retrieval_configuration = {
        "vectorSearchConfiguration": {
            "numberOfResults": number_of_results,
            "overrideSearchType": "SEMANTIC"
        }
    }

    response = client.retrieve(
        knowledgeBaseId=knowledge_base_id,
        retrievalQuery={"text": question},
        retrievalConfiguration=retrieval_configuration
    )

    return response

# if __name__ == "__main__":
#     kb_id = "KB12345678"  # 替換成您實際的知識庫 ID
#     prompt_question = "請說明 SAS 簽呈 的流程與注意事項是什麼？"
#     result = retrieve_from_kb(prompt_question, kb_id)
#     print("檢索結果：")
#     print(json.dumps(result, indent=2, ensure_ascii=False))
