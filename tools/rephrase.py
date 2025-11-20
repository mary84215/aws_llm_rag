import boto3
import json
from botocore.config import Config

from tools.config import RephraseConfig


def rephrase_question(question: str, region: str = RephraseConfig.REGION) -> str:
    """
    接收一個問題，回傳模型重述後的問題文字。
    """
    # 建立 Bedrock Runtime 客戶端
    client = boto3.client(
        "bedrock-runtime",
        region_name=region,
        config=Config(
            connect_timeout=3600,
            read_timeout=3600,
            retries={'max_attempts': 1}
        )
    )

    # 準備 messages 結構（使用聊天式 API 的方式）
    messages = [
        {
            "role": "user",
            "content": [
                {"text": question}
            ]
        }
    ]

    # 組建 request body
    body = {
        "messages": messages,
        "inferenceConfig": RephraseConfig.inference_config()
    }

    # 呼叫 invoke_model
    response = client.invoke_model(
        modelId=RephraseConfig.MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body)
    )

    # 解析回傳結果
    resp_body = json.loads(response["body"].read().decode('utf-8'))
    # 假設模型回傳格式為 output->message->content list, 取第一個 text
    rephrased = resp_body["output"]["message"]["content"][0]["text"]
    return rephrased

# if __name__ == "__main__":
#     input_question = "我們公司的保險政策如何因應通貨膨脹？"
#     result = rephrase_question(input_question)
#     print("原問題：", input_question)
#     print("重述後：", result)
