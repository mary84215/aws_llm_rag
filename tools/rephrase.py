import boto3
import json
from botocore.config import Config

def rephrase_question(question: str,
                      region: str = "us-east-1",
                      model_id: str = "amazon.nova-pro-v1:0",
                      max_tokens: int = 500,
                      temperature: float = 0.7,
                      top_p: float = 0.9,
                      top_k: int = 50) -> str:
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
        "inferenceConfig": {
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k
        }
    }

    # 呼叫 invoke_model
    response = client.invoke_model(
        modelId=model_id,
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
