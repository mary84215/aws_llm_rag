import json
import os
from tools.retrieve_generate import ret_and_gen


def lambda_handler(event, context):
    """
    Lambda 函數處理器：接收 prompt_question，回傳簽呈草稿文字
    """
    try:
        # 從環境變數讀取必要參數
        knowledge_base_id = os.environ['KNOWLEDGE_BASE_ID']
        model_arn = os.environ['MODEL_ARN']
        
        # 從 event 取得輸入
        if 'body' in event:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
            prompt_question = body.get('prompt_question')
        else:
            prompt_question = event.get('prompt_question')
        
        if not prompt_question:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'prompt_question is required'
                }, ensure_ascii=False)
            }
        
        # 執行檢索與生成
        response = ret_and_gen(
            prompt_question=prompt_question,
            knowledge_base_id=knowledge_base_id,
            model_arn=model_arn
        )
        
        # 提取生成的文字
        generated_text = response['output']['text']
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'draft_text': generated_text
            }, ensure_ascii=False)
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            }, ensure_ascii=False)
        }