import boto3
import json
from typing import Optional

from botocore.config import Config

from tools.config import RetrieveGenerateConfig


def ret_and_gen(prompt_question: str,
                knowledge_base_id: str,
                model_arn: str,
                region: str = RetrieveGenerateConfig.REGION,
                number_of_results: Optional[int] = None) -> dict:
    """
    使用 RetrieveAndGenerate API：從知識庫檢索，再生成 SAS 簽呈草稿。
    回傳 dict，包含生成文本與引用來源。
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

    # 準備輸入 prompt
    input_payload = {"text": prompt_question}

    # 設定檢索 + 生成流程
    retrieve_and_gen_config = RetrieveGenerateConfig.retrieve_and_gen_config(
        knowledge_base_id=knowledge_base_id,
        model_arn=model_arn,
        number_of_results=number_of_results,
    )

    response = client.retrieve_and_generate(
        input=input_payload,
        retrieveAndGenerateConfiguration=retrieve_and_gen_config
    )

    return response

# if __name__ == "__main__":
#     KB_ID = "YOUR_KB_ID"
#     MODEL_ARN = "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-pro-v1:0"
#     if KB_ID == "YOUR_KB_ID":
#         raise ValueError("Please replace YOUR_KB_ID with the actual knowledge base ID before running this file.")
#     question = "我們準備提交 SAS 簽呈，目的為提升保險理賠流程效率，請幫我撰寫草稿。"
#     print("Testing ret_and_gen...")
#     print(json.dumps(ret_and_gen(question, KB_ID, MODEL_ARN), indent=2, ensure_ascii=False))
