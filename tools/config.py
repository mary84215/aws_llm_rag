from typing import Dict, Optional

DEFAULT_REGION = "us-east-1"


class RephraseConfig:
    REGION = DEFAULT_REGION
    MODEL_ID = "amazon.nova-pro-v1:0"
    MAX_TOKENS = 500
    TEMPERATURE = 0
    TOP_P = 0.1
    TOP_K = 50

    @classmethod
    def inference_config(cls) -> Dict[str, object]:
        return {
            "max_new_tokens": cls.MAX_TOKENS,
            "temperature": cls.TEMPERATURE,
            "top_p": cls.TOP_P,
            "top_k": cls.TOP_K,
        }


class RetrieveConfig:
    REGION = DEFAULT_REGION
    NUMBER_OF_RESULTS = 3
    OVERRIDE_SEARCH_TYPE = "SEMANTIC"

    @classmethod
    def retrieval_configuration(cls,
                                number_of_results: Optional[int] = None,
                                metadata_filter: Optional[Dict[str, object]] = None) -> Dict[str, object]:
        results = cls.NUMBER_OF_RESULTS if number_of_results is None else number_of_results
        vector_search_config: Dict[str, object] = {
            "numberOfResults": results,
            "overrideSearchType": cls.OVERRIDE_SEARCH_TYPE
        }
        if metadata_filter:
            vector_search_config["filter"] = metadata_filter
        return {"vectorSearchConfiguration": vector_search_config}


class RetrieveGenerateConfig:
    REGION = DEFAULT_REGION
    NUMBER_OF_RESULTS = 3
    PROMPT_TEMPLATE = (
        "你是保險公司內部的文件助手，負責將使用者所輸入的需求，撰寫成一份內部簽呈草稿。"
        "請以正式公文語氣、繁體中文完成，並覆蓋以下四大項目："
        "一、【主旨】"
        "二、【內文】"
        "三、【建議附件】"
        "四、【審核流程】"
        "\n\n"
        "以下為來自知識庫的檢索結果：\n"
        "$search_results$\n"
        "\n"
        "請根據上述檢索結果撰寫草稿，並且保留使用者輸入的關鍵資訊，不新增使用者未提及的內容。\n"
        "草稿開始："
    )
    MAX_TOKENS = 1500
    TEMPERATURE = 0.2
    TOP_P = 0.9
    @classmethod
    def retrieve_and_gen_config(cls, knowledge_base_id: str, model_arn: str, number_of_results: Optional[int] = None) -> Dict[str, object]:
        results = cls.NUMBER_OF_RESULTS if number_of_results is None else number_of_results
        return {
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": knowledge_base_id,
                "modelArn": model_arn,
                "retrievalConfiguration": {
                    "vectorSearchConfiguration": {
                        "numberOfResults": results,
                        "overrideSearchType": RetrieveConfig.OVERRIDE_SEARCH_TYPE,
                    }
                },
                "generationConfiguration": {
                    "promptTemplate": {
                        "textPromptTemplate": cls.PROMPT_TEMPLATE,
                    },
                    "inferenceConfig": {
                        "textInferenceConfig": {
                            "maxTokens": cls.MAX_TOKENS,
                            "temperature": cls.TEMPERATURE,
                            "topP": cls.TOP_P,
                        }
                    },
                },
            },
        }
