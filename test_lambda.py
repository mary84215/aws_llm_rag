import json
import os
from lambda_handler import lambda_handler


def test_lambda_local():
    """
    本地測試 Lambda 函數
    """
    # 設定環境變數（請替換為實際值）
    os.environ['KNOWLEDGE_BASE_ID'] = 'your-kb-id-here'
    os.environ['MODEL_ARN'] = 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0'
    
    # 測試案例 1: 直接事件格式
    event1 = {
        'prompt_question': '請協助撰寫關於導入零信任架構的簽呈'
    }
    
    print("測試案例 1 - 直接事件格式:")
    result1 = lambda_handler(event1, {})
    print(json.dumps(result1, indent=2, ensure_ascii=False))
    print("\n" + "="*50 + "\n")
    
    # 測試案例 2: API Gateway 格式
    event2 = {
        'body': json.dumps({
            'prompt_question': '請協助撰寫關於備援機房建置的簽呈'
        })
    }
    
    print("測試案例 2 - API Gateway 格式:")
    result2 = lambda_handler(event2, {})
    print(json.dumps(result2, indent=2, ensure_ascii=False))
    print("\n" + "="*50 + "\n")
    
    # 測試案例 3: 錯誤情況 - 缺少 prompt_question
    event3 = {}
    
    print("測試案例 3 - 錯誤情況:")
    result3 = lambda_handler(event3, {})
    print(json.dumps(result3, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    test_lambda_local()