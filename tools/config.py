from typing import Dict, Optional

DEFAULT_REGION = "us-east-1"


class RephraseConfig:
    REGION = DEFAULT_REGION
    MODEL_ID = "amazon.nova-pro-v1:0"
    MAX_TOKENS = 500
    TEMPERATURE = 0.7
    TOP_P = 0.9
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
    def retrieval_configuration(cls, number_of_results: Optional[int] = None) -> Dict[str, object]:
        results = cls.NUMBER_OF_RESULTS if number_of_results is None else number_of_results
        return {
            "vectorSearchConfiguration": {
                "numberOfResults": results,
                "overrideSearchType": cls.OVERRIDE_SEARCH_TYPE,
            }
        }


class RetrieveGenerateConfig:
    REGION = DEFAULT_REGION
    NUMBER_OF_RESULTS = 3
    PROMPT_TEMPLATE = (
        "請基於以下檢索結果撰寫一份 SAS 簽呈草稿。"
        "使用簡潔條列清楚說明目的、現況、建議與預算。\n\n"
        "檢索結果：\n$search_results$\n\n"
        "草稿開始："
    )
    MAX_TOKENS = 500
    TEMPERATURE = 0.5
    TOP_P = 0.9
    STOP_SEQUENCES = ["\n\n"]

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
                            "stopSequences": cls.STOP_SEQUENCES,
                        }
                    },
                },
            },
        }
