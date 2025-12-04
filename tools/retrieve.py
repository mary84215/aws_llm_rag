import boto3
import json
import re
from decimal import Decimal
from typing import Any, Optional

from botocore.config import Config
from botocore.exceptions import ClientError

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
        "key": "category",
        "type": "STRING",
        "description": "The category of this contract, often but not exclusively on of ['簽約','續約']"
    },
    {
        "key": "product_name",
        "type": "STRING",
        "description": "The name of the product, including such like ['SAS Viya','SAS OA']"
    }]
    ```

    # Input User Query:  
    數據部於2025年12月31日續約SAS OA軟體，總計3年3000000元，最高簽核至總經理。

    # Output Structured Request:
    ```json
    {
    "query": "請幫我生成簽呈內容",
    "filter": {
        "andAll": [
        {"equals": {"key": "product_name", "value": "SAS OA"}},
        {"equals": {"key": "category", "value": "續約"}}
        ]
    }
    }
    ```
    << Example 2 >>
    # Metadata Schema:
    ```json
    [
    {
        "key": "category",
        "type": "STRING",
        "description": "The category of this contract, often but not exclusively on of ['簽約','續約']"
    },
    {
        "key": "product_name",
        "type": "STRING",
        "description": "The name of the product, including such like ['SAS Viya','SAS OA','SAS雲端','SAS地端']"
    }]
    ```

    # Input User Query:  
    數據部於2025年12月31日簽約SAS Viya軟體，總計3年3000000元，最高簽核至總經理。

    # Output Structured Request:
    ```json
    {
    "query": "請幫我生成簽呈內容",
    "filter": {
        "andAll": [
        {"equals": {"key": "product_name", "value": "SAS Viya"}},
        {"equals": {"key": "category", "value": "簽約"}}
        ]
    }
    }
    ```
    << Example 3 >>
    # Metadata Schema:
    ```json
    [
    {
        "key": "category",
        "type": "STRING",
        "description": "The category of this contract, often but not exclusively on of ['簽約','續約']"
    },
    {
        "key": "product_name",
        "type": "STRING",
        "description": "The name of the product, including such like ['SAS Viya','SAS OA','SAS雲端','SAS地端']"
    }]
    ```

    # Input User Query:  
    數據部於2025年12月31日續約SAS，總計3年3000000元，最高簽核至總經理。

    # Output Structured Request:
    ```json
    {
    "query": "請幫我生成簽呈內容",
    "filter": {
        "orAll": [
        {"equals": {"key": "product_name", "value": "SAS OA"}},
        {"equals": {"key": "product_name", "value": "SAS Viya"}}
        ],
        "andAll": [
        {"equals": {"key": "category", "value": "續約"}}
        ]
    }
    }
    ```
    << Example 4 >>
    # Metadata Schema:
    ```json
    [
    {
        "key": "category",
        "type": "STRING",
        "description": "The category of this contract, often but not exclusively on of ['簽約','續約']"
    },
    {
        "key": "product_name",
        "type": "STRING",
        "description": "The name of the product, including such like ['SAS Viya','SAS OA','SAS雲端','SAS地端']"
    }]
    ```

    # Input User Query:  
    數據部於2025年12月31日簽約SAS，總計3年3000000元，最高簽核至總經理。

    # Output Structured Request:
    ```json
    {
    "query": "請幫我生成簽呈內容",
    "filter": {
        "orAll": [
        {"equals": {"key": "product_name", "value": "SAS OA"}},
        {"equals": {"key": "product_name", "value": "SAS Viya"}}
        ],
        "andAll": [
        {"equals": {"key": "category", "value": "簽約"}}
        ]
    }
    }
    ```
    << Example 5 >>
    # Metadata Schema:
    ```json
    [
    {
        "key": "category",
        "type": "STRING",
        "description": "The category of this contract, often but not exclusively on of ['簽約','續約']"
    },
    {
        "key": "product_name",
        "type": "STRING",
        "description": "The name of the product, including such like ['SAS Viya','SAS OA','SAS雲端','SAS地端']"
    }]
    ```

    # Input User Query:  
    數據部於2025年12月31日SAS Viya簽呈，總計3年3000000元，最高簽核至總經理。

    # Output Structured Request:
    ```json
    {
    "query": "請幫我生成簽呈內容",
    "filter": {
        "orAll": [
        {"equals": {"key": "category", "value": "簽約"},
        {"equals": {"key": "category", "value": "續約"}}
        ],
        "andAll": [
        {"equals": {"key": "product_name", "value": "SAS Viya"}}
        ]
    }
    }
    ```
    << Example 6 >>
    # Metadata Schema:
    ```json
    [
    {
        "key": "category",
        "type": "STRING",
        "description": "The category of this contract, often but not exclusively on of ['簽約','續約']"
    },
    {
        "key": "product_name",
        "type": "STRING",
        "description": "The name of the product, including such like ['SAS Viya','SAS OA','SAS雲端','SAS地端']"
    }]
    ```

    # Input User Query:  
    數據部於2025年12月31日SAS OA簽呈，總計3年3000000元，最高簽核至總經理。

    # Output Structured Request:
    ```json
    {
    "query": "請幫我生成簽呈內容",
    "filter": {
        "orAll": [
        {"equals": {"key": "category", "value": "簽約"},
        {"equals": {"key": "category", "value": "續約"}}
        ],
        "andAll": [
        {"equals": {"key": "product_name", "value": "SAS OA"}}
        ]
    }
    }
    ```
"""


ATTRIBUTE_VALUE_KEYS = {
    "booleanValue",
    "doubleValue",
    "longValue",
    "stringListValue",
    "stringValue",
}
COMPARATOR_KEYS = {
    "equals",
    "notEquals",
    "greaterThan",
    "greaterThanOrEquals",
    "lessThan",
    "lessThanOrEquals",
    "in",
    "notIn",
    "startsWith",
    "listContains",
    "stringContains",
}
LOGICAL_KEYS = {"andAll", "orAll", "and", "or", "op"}

# Known attribute types for the current KB metadata schema.
# Extend this map if you add more metadata fields.
ATTRIBUTE_TYPES: dict[str, str] = {
    "category": "STRING_LIST",
    "product_name": "STRING",
    "creation_year": "NUMBER",
    "title": "STRING",
    "related_departments": "STRING_LIST",
    "tags": "STRING_LIST",
    "highest_approval_level": "STRING",
    "date_created": "STRING",
    "budget_amount": "NUMBER",
}


def _coerce_attribute_value(value: Any, force_list: bool = False) -> Optional[dict]:
    """
    Convert a raw value from the LLM output into the Bedrock AttributeValue schema.
    Returns None when the value is empty or cannot be mapped.
    """
    if isinstance(value, dict) and ATTRIBUTE_VALUE_KEYS & set(value.keys()):
        return {k: v for k, v in value.items() if k in ATTRIBUTE_VALUE_KEYS}

    if isinstance(value, bool):
        return {"booleanValue": value}

    if isinstance(value, (int, Decimal)) and not isinstance(value, bool):
        return {"longValue": int(value)}

    if isinstance(value, float):
        return {"doubleValue": value}

    if isinstance(value, list):
        items = [str(item).strip() for item in value if item is not None and str(item).strip()]
        return {"stringListValue": items} if items else None

    if force_list:
        text = str(value).strip()
        return {"stringListValue": [text]} if text else None

    text = str(value).strip()
    return {"stringValue": text} if text else None


def _enforce_attribute_types(node: Any) -> Optional[dict]:
    """
    Ensure comparator values match the KB metadata types (e.g., STRING vs STRING_LIST).
    Prevents Bedrock "filter value type provided is not supported" errors.
    """
    if not isinstance(node, dict):
        return None

    fixed: dict[str, Any] = {}
    for key, value in node.items():
        if key in {"andAll", "orAll"}:
            children = value if isinstance(value, list) else []
            normalized_children = [_enforce_attribute_types(child) for child in children]
            normalized_children = [child for child in normalized_children if child]
            if normalized_children:
                fixed[key] = normalized_children
        elif key in COMPARATOR_KEYS:
            if not isinstance(value, dict):
                continue
            attr = value.get("key")
            attr_value = value.get("value", {})
            if not attr or not isinstance(attr_value, dict):
                continue

            attr_type = ATTRIBUTE_TYPES.get(attr)
            # Skip unknown attributes to avoid invalid filter errors.
            if not attr_type:
                continue

            # Normalize STRING_LIST attributes to stringListValue
            if attr_type == "STRING_LIST":
                list_value = attr_value.get("stringListValue")
                if list_value is None:
                    raw = attr_value.get("stringValue") or attr_value.get("longValue") or attr_value.get("doubleValue")
                    if raw is not None:
                        list_value = [str(raw)]
                if list_value:
                    attr_value = {"stringListValue": [str(item).strip() for item in list_value if str(item).strip()]}
                else:
                    continue

            # Normalize STRING attributes to stringValue
            elif attr_type == "STRING":
                if "stringValue" not in attr_value:
                    # fallback to first available value as string
                    raw = next(iter(attr_value.values()), None)
                    if raw is None:
                        continue
                    text = str(raw).strip()
                    if not text:
                        continue
                    attr_value = {"stringValue": text}

            # Normalize NUMBER attributes to longValue/doubleValue
            elif attr_type == "NUMBER":
                num_value = None
                if "longValue" in attr_value:
                    num_value = attr_value.get("longValue")
                elif "doubleValue" in attr_value:
                    num_value = attr_value.get("doubleValue")
                else:
                    raw = attr_value.get("stringValue") or next(iter(attr_value.values()), None)
                    if raw is not None:
                        try:
                            num_value = int(raw)
                        except (ValueError, TypeError):
                            try:
                                num_value = float(raw)
                            except (ValueError, TypeError):
                                num_value = None
                if num_value is None:
                    continue
                if isinstance(num_value, bool):
                    continue
                if isinstance(num_value, float) and not num_value.is_integer():
                    attr_value = {"doubleValue": float(num_value)}
                else:
                    attr_value = {"longValue": int(num_value)}

            # Normalize BOOLEAN attributes to booleanValue
            elif attr_type == "BOOLEAN":
                bool_value = attr_value.get("booleanValue")
                if bool_value is None:
                    raw = attr_value.get("stringValue") or next(iter(attr_value.values()), None)
                    if isinstance(raw, str):
                        lowered = raw.strip().lower()
                        if lowered in {"true", "yes", "1"}:
                            bool_value = True
                        elif lowered in {"false", "no", "0"}:
                            bool_value = False
                if bool_value is None:
                    continue
                attr_value = {"booleanValue": bool(bool_value)}

            fixed[key] = {"key": attr, "value": attr_value}
        else:
            fixed[key] = value

    return fixed or None


def _extract_product_from_query(query: str) -> Optional[str]:
    """
    Heuristically extract a product name from the user query (e.g., 'SAS Viya', 'SAS OA').
    Returns None if nothing obvious is found.
    """
    matches = re.findall(r"SAS[\s\\-]*[A-Za-z0-9]+(?:[\s\\-]*[A-Za-z0-9]+)?", query, flags=re.IGNORECASE)
    if not matches:
        return None
    # Choose the longest match to avoid partials.
    product = max(matches, key=len).strip()
    return product


def _add_product_filter(node: dict, product: str) -> dict:
    """
    Ensure the filter tree includes an equals comparator for product_name with the provided value.
    If a product_name comparator already exists, it is overwritten with the query-derived product.
    """
    if not isinstance(node, dict):
        return {}

    product_comp = {"equals": {"key": "product_name", "value": {"stringValue": product}}}

    def _product_matches(val: Any) -> bool:
        if not isinstance(val, dict):
            return False
        if val.get("key") != "product_name":
            return False
        v = val.get("value", {})
        if not isinstance(v, dict):
            return False
        if "stringValue" in v and str(v.get("stringValue", "")).strip() == product:
            return True
        if "stringListValue" in v and any(str(x).strip() == product for x in v.get("stringListValue") or []):
            return True
        return False

    def _append_to_first_or(n: Any) -> bool:
        if not isinstance(n, dict):
            return False
        if "orAll" in n and isinstance(n["orAll"], list):
            # Only append if not already present
            exists = False
            for item in n["orAll"]:
                if isinstance(item, dict):
                    inner = next(iter(item.values())) if item else None
                    if _product_matches(inner):
                        exists = True
                        break
            if not exists:
                n["orAll"].append(product_comp)
            return True
        for v in n.values():
            if isinstance(v, dict) and _append_to_first_or(v):
                return True
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and _append_to_first_or(item):
                        return True
        return False

    # Overwrite existing product_name comparator if present.
    for key, value in list(node.items()):
        if key in COMPARATOR_KEYS and isinstance(value, dict) and value.get("key") == "product_name":
            node[key] = product_comp["equals"]
            return node
        if key in {"andAll", "orAll"} and isinstance(value, list):
            for child in value:
                if isinstance(child, dict) and any(
                    comp.get("key") == "product_name" for comp in child.values() if isinstance(comp, dict)
                ):
                    # Overwrite in-place
                    for comp_key, comp_val in child.items():
                        if isinstance(comp_val, dict) and comp_val.get("key") == "product_name":
                            child[comp_key] = product_comp["equals"]
                            return node

    # If the LLM already expressed disjunction (orAll) anywhere, append there.
    if _append_to_first_or(node):
        return node

    # Otherwise, append the comparator to an existing andAll or wrap both in a new andAll.
    if "andAll" in node and isinstance(node["andAll"], list):
        node["andAll"].append(product_comp)
        return node
    else:
        return {"andAll": [node, product_comp]}


def _extract_category_from_query(query: str) -> Optional[str]:
    """
    Heuristically extract a category keyword from the user query to reduce LLM mix-ups (簽約 vs 續約).
    """
    # Order matters: longer phrases first.
    candidates = ["續約", "簽約"]
    for cand in candidates:
        if cand in query:
            return cand
    # Fallback to single-word hints (less precise)
    if "續約" in query:
        return "續約"
    if "簽約" in query:
        return "簽約"
    return None


def _add_category_filter(node: dict, category: str) -> dict:
    """
    Ensure the filter tree includes a comparator for category using the KB type (STRING_LIST by default).
    """
    if not isinstance(node, dict):
        return {}

    # Build comparator based on configured type
    attr_type = ATTRIBUTE_TYPES.get("category", "STRING_LIST")
    if attr_type == "STRING_LIST":
        cat_comp = {"listContains": {"key": "category", "value": {"stringListValue": [category]}}}
    else:
        cat_comp = {"equals": {"key": "category", "value": {"stringValue": category}}}

    # Overwrite existing category comparator if present
    for key, value in list(node.items()):
        if key in COMPARATOR_KEYS and isinstance(value, dict) and value.get("key") == "category":
            node[key] = cat_comp[next(iter(cat_comp.keys()))]
            return node
        if key in {"andAll", "orAll"} and isinstance(value, list):
            for child in value:
                if isinstance(child, dict) and any(
                    comp.get("key") == "category" for comp in child.values() if isinstance(comp, dict)
                ):
                    for comp_key, comp_val in child.items():
                        if isinstance(comp_val, dict) and comp_val.get("key") == "category":
                            child[comp_key] = cat_comp[next(iter(cat_comp.keys()))]
                            return node

    # If the LLM already expressed disjunction (orAll), append there.
    def _append_to_first_or(n: Any) -> bool:
        if not isinstance(n, dict):
            return False
        if "orAll" in n and isinstance(n["orAll"], list):
            n["orAll"].append(cat_comp)
            return True
        for v in n.values():
            if isinstance(v, dict) and _append_to_first_or(v):
                return True
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and _append_to_first_or(item):
                        return True
        return False
    if _append_to_first_or(node):
        return node

    # Otherwise, append to existing andAll or wrap
    if "andAll" in node and isinstance(node["andAll"], list):
        node["andAll"].append(cat_comp)
        return node
    else:
        return {"andAll": [node, cat_comp]}


def _normalize_comparator_payload(comparator: str, payload: Any) -> Optional[dict]:
    """
    Normalize a single comparator block into the expected Bedrock format.
    """
    if not isinstance(payload, dict):
        return None

    key = payload.get("key")
    raw_value = payload.get("value")
    if not key or raw_value is None:
        return None

    prefer_list = comparator in {"in", "notIn", "listContains"}
    attr_value = _coerce_attribute_value(raw_value, force_list=prefer_list)
    if not attr_value:
        return None

    return {"key": key, "value": attr_value}


def _normalize_filter_node(node: Any) -> Optional[dict]:
    """
    Recursively normalize filter nodes produced by the LLM into Bedrock's filter schema.
    Unsupported or empty nodes return None to avoid invalid requests.
    """
    if not isinstance(node, dict):
        return None

    normalized: dict[str, Any] = {}
    for key, value in node.items():
        if key in LOGICAL_KEYS:
            children = value if isinstance(value, list) else []
            child_filters = [_normalize_filter_node(child) for child in children]
            child_filters = [child for child in child_filters if child]
            if child_filters:
                normalized["andAll" if key in {"andAll", "and", "op"} else "orAll"] = child_filters
        elif key in COMPARATOR_KEYS:
            comparator_block = _normalize_comparator_payload(key, value)
            if comparator_block:
                normalized[key] = comparator_block

    return normalized or None


def _normalize_metadata_filter(metadata_filter: Any) -> Optional[dict]:
    """
    Convert the LLM-generated filter into a Bedrock-compatible RetrievalFilter.
    Returns None when the filter is unusable.
    """
    normalized = _normalize_filter_node(metadata_filter)
    if not normalized:
        return None

    compacted = _compact_filter_node(normalized)
    return _enforce_attribute_types(compacted) if compacted else None


def _compact_filter_node(node: Any) -> Optional[dict]:
    """
    Remove single-child logical nodes (and/or) that Bedrock rejects.
    Bedrock expects at least two children for andAll/orAll, so unwrap when only one.
    """
    if not isinstance(node, dict):
        return None

    compacted = {}
    for key, value in node.items():
        if key in {"andAll", "orAll"}:
            children = value if isinstance(value, list) else []
            cleaned_children = [child for child in (children or []) if child]
            cleaned_children = [
                _compact_filter_node(child) if isinstance(child, dict) else child
                for child in cleaned_children
            ]
            cleaned_children = [child for child in cleaned_children if child]

            # Unwrap single-child logical blocks to avoid invalid length errors.
            if len(cleaned_children) == 1:
                return cleaned_children[0]
            if cleaned_children:
                compacted[key] = cleaned_children
        else:
            compacted[key] = value

    return compacted or None


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

    normalized_filter = _normalize_metadata_filter(metadata_filter)
    if not isinstance(normalized_filter, dict):
        return None

    # Force product_name to match the query if we can extract it; otherwise, keep the normalized filter.
    product_in_query = _extract_product_from_query(query)
    if product_in_query:
        normalized_filter = _add_product_filter(normalized_filter, product_in_query)

    # Force category to match query hints (簽約/續約).
    category_in_query = _extract_category_from_query(query)
    if category_in_query:
        normalized_filter = _add_category_filter(normalized_filter, category_in_query)

    return normalized_filter if isinstance(normalized_filter, dict) else None


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
    try:
        response = client.retrieve(
            knowledgeBaseId=knowledge_base_id,
            retrievalQuery={"text": question},
            retrievalConfiguration=retrieval_configuration
        )
    except ClientError as exc:
        # Fallback: if filter is invalid, retry without filter to avoid blocking retrieval.
        error_msg = exc.response.get("Error", {}).get("Message", "")
        if metadata_filter and "filter value type" in error_msg.lower():
            retrieval_configuration = RetrieveConfig.retrieval_configuration(
                number_of_results=number_of_results,
                metadata_filter=None,
            )
            response = client.retrieve(
                knowledgeBaseId=knowledge_base_id,
                retrievalQuery={"text": question},
                retrievalConfiguration=retrieval_configuration
            )
        else:
            raise

    return response

# if __name__ == "__main__":
#     KB_ID = "YOUR_KB_ID"
#     if KB_ID == "YOUR_KB_ID":
#         raise ValueError("Please replace YOUR_KB_ID with the actual knowledge base ID before running this file.")
#     question = "請說明 SAS 簽呈 的流程與注意事項是什麼？"
#     print("Testing retrieve_from_kb...")
#     print(json.dumps(retrieve_from_kb(question, KB_ID), indent=2, ensure_ascii=False))
