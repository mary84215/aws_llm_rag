import boto3
import json
from botocore.config import Config

from tools.config import BasicModelConfig


def rephrase_question(question: str, region: str = BasicModelConfig.REGION) -> str:
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

    system_list = [
            {
                "text": "你現在是在 RAG 流程中扮演「問題重述 Agent」。\
            使用者會輸入他對於保險公司內部簽呈（內部公文）相關的需求說明或問題。\
            你的任務是：根據使用者的輸入，將內容改寫成一段更清楚完整的敘述，\
            好像你就是使用者本人，正在向公司內部提出簽呈需求。\
            \
            請嚴格遵守以下規則：\
            1. 一律使用第一人稱視角（例如：『我想申請…』『我需要…』）。\
            2. 只能根據使用者輸入的資訊進行改寫，『不要』加入使用者沒有提到的內容、假設或細節。\
            3. 保留並明確呈現原文中的關鍵資訊（如：金額、日期、保單資訊、部門名稱、對象、原因、目的、限制條件等）\
            4. 若使用者原本描述較口語或零碎，請幫忙整理成一段正式、通順、適合用在簽呈上的書面語敘述。\
            5. 不要詢問問題，不要解釋你的做法，也不要輸出任何說明文字或標題，只輸出改寫後的那一段敘述。\
            6. 請使用繁體中文。"
            }
    ]

    # 組建 request body
    body = {
        "messages": messages,
        "system":system_list,
        "inferenceConfig": BasicModelConfig.inference_config()
    }

    # 呼叫 invoke_model
    response = client.invoke_model(
        modelId=BasicModelConfig.MODEL_ID,
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
#     prompt = "我們公司的保險政策如何因應通貨膨脹？"
#     print("Testing rephrase_question...")
#     print(f"Input : {prompt}")
#     print(f"Output: {rephrase_question(prompt)}")
