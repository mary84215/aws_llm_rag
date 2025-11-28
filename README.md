# AWS Bedrock Knowledge Base CLI

這個範例展示如何在 VS Code 內使用 Python 透過 AWS Bedrock 進行下列動作：

- 測試指定的 Knowledge Base 是否可用
- 依照 metadata 進行向量檢索
- 將檢索結果傳遞給指定的 Bedrock 文字模型（例如 Claude 3 Sonnet）完成推論

## 目錄結構

```
.
├── README.md                # 說明與使用教學
├── setup.py                 # 套件安裝與 CLI entry point 設定
├── cli.py                   # 命令列工具主程式
└── kb_tool/                 # 共用模組
    ├── __init__.py
    ├── config.py            # 讀取環境變數、共用設定
    ├── generator.py         # 呼叫 Bedrock Runtime 進行推論
    ├── kb_client.py         # 使用 bedrock-agent-runtime 進行知識檢索
    └── metadata.py          # 解析 metadata filter 參數
```

## 先決條件

1. 已具備對應 AWS 帳號的 IAM 權限，可呼叫 `bedrock-agent-runtime` 與 `bedrock-runtime` API。
2. 工作站已設定好 AWS 認證資訊（`~/.aws/credentials` 或 `AWS_ACCESS_KEY_ID` 等環境變數）。
3. 在vscode terminal,運用sh指令執行aws_local_access.sh,可以輸入MFA_CODE_ON_PHONE, 之後把echo出的那三組密碼丟入settings.json
4. aws s3 ls測試有沒有權限操啜aws, 若無法，請重開一個vscode terminal
4. 目標 Knowledge Base、向量儲存區與 Bedrock 模型均已在對應 Region 建立。

## 安裝

此專案建議使用 Conda 建立隔離環境並指定 Python 版本，例如 3.11：

```bash
conda create -n aws python=3.11 -y
conda activate aws
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

`requirements.txt` 會安裝執行 CLI 所需的第三方套件，`setup.py` 則會註冊 `kb-cli` 這個命令列工具，方便於任何資料夾直接執行。

## 必要環境變數

| 變數 | 用途 |
| ---- | ---- |
| `AWS_REGION` 或 `AWS_DEFAULT_REGION` | 目標 Region |
| `BEDROCK_KB_ID` | 要測試/檢索的 Knowledge Base ID |
| `BEDROCK_MODEL_ID` | （可選）Bedrock 文字模型 ID，預設為 `anthropic.claude-3-sonnet-20240229-v1:0` |
| `BEDROCK_KB_TOP_K` | （可選）預設檢索回傳段落數 |
| `BEDROCK_INSTRUCTIONS` | （可選）系統提示詞 |

## 使用方式

以下所有指令都可使用 `--metadata key=value` 重複提供多組條件，並自動形成 Bedrock 的 equals filter。例如 `--metadata language=zh category=policy`。

### 1. 健康檢查

```bash
kb-cli --mode test
```

會使用預設查詢字串 `health check` 呼叫 `retrieve`，並輸出成功取得的段落數量，可快速驗證權限、Region 與 Knowledge Base 設定是否正確。

### 2. 單純檢索（不做模型生成）

```bash
kb-cli --mode retrieve "請問備援機房的標準流程？" --metadata department=it
```

指令會呼叫 `bedrock-agent-runtime.retrieve`，並將 JSON 格式的檢索段落直接輸出在終端機，方便與 VS Code Rest Client 或其他工具整合。

### 3. 檢索後產生模型回答

```bash
kb-cli --mode generate "總結零信任規範重點" --metadata language=zh --temperature 0.3
```

流程如下：

1. 透過向量檢索取得最相關的段落。
2. 將段落內容轉成 context block，搭配自訂 instructions 傳給 `bedrock-runtime.invoke_model`。
3. 以 JSON 格式回傳回答與原始 snippets，方便除錯與在應用程式中記錄。

### 參數補充

- `--top-k`：調整單次檢索回傳的段落數，預設取決於 `BEDROCK_KB_TOP_K`。
- `--search-type`：`SEMANTIC` 或 `HYBRID`，方便在測試階段切換演算法。
- `--instructions`：臨時覆寫系統提示詞（未提供時使用環境變數或預設值）。
- `--temperature`、`--max-tokens`：對應模型推論參數。

## 開發與除錯

- 指令列工具會以 `json.dumps(..., ensure_ascii=False)` 輸出結果，VS Code 終端機可以直接閱讀中文。
- 若要檢視實際送出的 metadata filter 格式，可使用 `print` 或在 `kb_tool/config.py` 中加入額外 logging。
- 一旦需要進行更進階的 filter（例如 `in`、`greaterThan`），可在 `metadata_dict_from_key_values` 內擴充。

## Lambda 部署

我已經為您創建了三個檔案：

### 1. lambda_handler.py - Lambda 主程式
- 接收 prompt_question 輸入
- 使用 RetrieveGenerateConfig 設定
- 呼叫 retrieve_generate.py 執行檢索與生成
- 回傳簽呈草稿文字

### 2. test_lambda.py - 測試案例
包含三種測試情境：
- 直接事件格式
- API Gateway 格式（JSON body）
- 錯誤情況處理

### 3. requirements_lambda.txt - Lambda 依賴

### 部署前準備

設定環境變數（在 test_lambda.py 中更新實際值）：
```bash
KNOWLEDGE_BASE_ID=your-actual-kb-id
MODEL_ARN=your-actual-model-arn
```

本地測試：
```bash
python test_lambda.py
```

Lambda 部署時需要：
- 將整個 tools/ 資料夾一起打包
- 設定環境變數 KNOWLEDGE_BASE_ID 和 MODEL_ARN
- 確保 Lambda 執行角色有 bedrock-agent-runtime 權限

Lambda 函數會回傳 JSON 格式，包含 draft_text 欄位存放生成的簽呈草稿。

## 免責聲明

此程式碼僅作為測試與教學用途，請依照組織安全規範妥善管理 AWS 認證與敏感資料。
