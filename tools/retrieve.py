import boto3
import json
from typing import Any, Optional

from botocore.config import Config

from tools.config import RephraseConfig, RetrieveConfig


# METADATA_FILTER_SYSTEM_PROMPT = (
#     "你是一個負責為 AWS Bedrock 知識庫檢索流程產生 metadata filter 的助理。"
#     "會收到使用者的檢索需求，請根據內容挑選以下欄位作為過濾條件："
#     "category (STRING)、tags (STRING_LIST)、product_name (STRING)、creation_year (NUMBER)。"
#     "你必須輸出 JSON 物件：{\"user_prompt\": 原始輸入, \"metadata_filter\": 過濾條件或 null}。"
#     "metadata_filter 需符合 Bedrock filter schema，例如 "
#     "{\"equals\": {\"key\": \"category\", \"value\": {\"stringValue\": \"SAS\"}}} 或 "
#     "{\"equals\": {\"key\": \"creation_year\", \"value\": {\"longValue\": 2024}}}。"
#     "若資訊不足或不需要過濾，請回傳 null。僅輸出 JSON，不能包含額外說明。"
# )
METADATA_FILTER_SYSTEM_PROMPT = """
    Your task is to structure the user's query to match the request schema provided below.

    << Output Format >>
    ```json
    {
    "query": string \ transformed query that excludes the filters
    "filter": {
        "op": [{comparison / statement 1}, {comparison / logical statement 2}, ...]
    }
    }
    ```

    The query string should contain only text that is expected to match the contents of documents. It should preserve most of the information and intents in the original query.  
    The filter is a JSON object containing logical and comparison statements structured according to the metadata schema.

    A comparison statement takes the form:  
    ```json
    {
    "comp": {
        "key": "attr",
        "value": "val"
    }
    }
    ```

    - `comp`: comparator, MUST be one of ["equals", "notEquals", "greaterThan", "greaterThanOrEquals", "lessThan", "lessThanOrEquals", "in", "notIn", "startsWith", "listContains", "stringContains"]
    - `attr` (string): name of attribute to apply the comparison to (i.e., metadata)
    - `val` (string | list[string]): the comparison value (i.e., filter value)
    Note: "greaterThan", "greaterThanOrEquals", "lessThan", and "lessThanOrEquals" can only apply to NUMBER data typed filter values. The filter value for the "in" and "notIn" comparators should have the type of list[string] instead of string. "listContains" can only apply to STRING_LIST typed metadata attributes.

    A logical operation statement takes the form:  
    ```json
    {
    "op": [{statement 1}, {statement 2}, ...]
    }
    ```

    - `op`: logical operator, MUST be one of ["and", "or"]
    - `statement1`, `statement2`, ... (comparison statements or logical operation statements): one or more statements to apply the operation to

    Ensure that you only use comparators ("equals", "notEquals", "greaterThan", "greaterThanOrEquals", "lessThan", "lessThanOrEqualst", "lessThanOrEquals", "in", "notIn", "startwith", "listContains", "stringContains") and logical operators ('and', 'or') in your queries. Avoid using functions like 'exists' or any other function over attributes.

    Filters must only refer to attributes that exist in the metadata schema. If a query involves intents that don't exist in the metadata schema, skip that intent.

    Filters must take into account the descriptions of attributes and only make comparisons that are feasible given the type of data being stored.

    Use filters only as needed. If there are no filters that should be applied, return `null` for the filter value. Avoid asking users to rephrase their question.

    Filters must use values `true` or `false` (unquoted) when handling Boolean data typed values.

    The output should contain only the JSON object in the structured request format defined above. Avoid generating additional text (e.g., explanations).

    For questions involving multiple possible values associated with a filter, such as comparison questions, remember to use 'or' instead of 'and' as the logical operator.

    If a filter is generated over a metadata attribute which is a unique identifier (e.g., File Name), you can skip the rest of the filters.

    For metadata fact-finding or comparison questions, such as "What is <attribute> of the file named 'xxx.pdf'", avoid generating filters for the <attribute> being asked.

    Be sure to double-quote all string values in filters.

    You should be conservative in generating the filters. Ignore the filter if the information is ambiguous or unclear.

    Ignore non-filter-related information unless they are explicitly labeled as conditions.

    Avoid generating filters for recency intents, such as "most recent xxx".

"""


QUERY_CONTEXT_TEMPLATE = """
    << Example 1 >>
    # Metadata Schema:
    ```json
    [
    {
        "key": "Title",
        "type": "STRING",
        "description": "The title of the movie."
    },
    {
        "key": "Genre",
        "type": "STRING",
        "description": "The genre of the movie. One of ['science fiction', 'comedy', 'drama', 'thriller', 'romance', 'action', 'animated']"
    },
    {
        "key": "Year",
        "type": "NUMBER",
        "description": "The year the movie was released (YYYY)"
    },
    {
        "key": "Director",
        "type": "STRING",
        "description": "The name of the movie director"
    },
    {
        "key": "Rating",
        "type": "NUMBER",
        "description": "A 1-10 rating for the movie"
    }
    ]
    ```

    # Input User Query:  
    What's the average rating of action movies released before 2000?

    # Output Structured Request:
    ```json
    {
    "query": "What's the average rating of the movies?",
    "filter": {
        "andAll": [
        {"lessThan": {"key": "Year", "value": 2000}},
        {"equals": {"key": "Genre", "value": "action"}}
        ]
    }
    }
    ```

    Here is the test example:
    # Metadata Schema
    ```json
    [
        {"description":"產品名稱 (product_name)，為SAS, SAS Viya或是DataStage", "key":"product_name", "type":"STRING"}
    ]
    ```

    # Input User Query:
    <<USER_QUERY>>

    # Output Structured Request:
"""


def _generate_metadata_filter(query: str) -> Optional[dict]:
    """
    透過 Nova Pro 產生 metadata filter，方便 Knowledge Base vector search 使用。
    """
    client = boto3.client(
        "bedrock-runtime",
        region_name=RephraseConfig.REGION,
        config=Config(connect_timeout=3600, read_timeout=3600, retries={"max_attempts": 1}),
    )

    query_context = QUERY_CONTEXT_TEMPLATE.replace("<<USER_QUERY>>", query)

    body = {
        "system": [{"text": METADATA_FILTER_SYSTEM_PROMPT}],
        "messages": [
            {
                "role": "user",
                "content": [{"text": query_context}],
            }
        ],
        "inferenceConfig": RephraseConfig.inference_config(),
    }

    try:
        response = client.invoke_model(
            modelId=RephraseConfig.MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
    except Exception:
        return None

    try:
        resp_body: dict[str, Any] = json.loads(response["body"].read().decode("utf-8"))
    except Exception:
        return None

    content = resp_body["output"]["message"]["content"]
    if not content:
        return None

    raw_text = content[0].get("text", "").strip()
 
    if not raw_text:
        return None

    if raw_text.startswith("```"):
        # Remove Markdown-style fenced code blocks to keep the JSON valid.
        if raw_text.startswith("```json"):
            raw_text = raw_text[len("```json"):].lstrip()
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:].lstrip()
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3].rstrip()

    try:
        generated = json.loads(raw_text)
    except json.JSONDecodeError:
        return None

    metadata_filter = generated.get("filter")
    if metadata_filter in (None, "null"):
        return None

    if isinstance(metadata_filter, str):
        try:
            metadata_filter = json.loads(metadata_filter)
        except json.JSONDecodeError:
            return None

    return metadata_filter if isinstance(metadata_filter, dict) else None


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

    metadata_filter = _generate_metadata_filter(question)

    retrieval_configuration = RetrieveConfig.retrieval_configuration(
        number_of_results=number_of_results,
        metadata_filter=metadata_filter,
    )

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
