import json
from datetime import datetime
from pathlib import Path

import tools.rephrase as rf
import tools.retrieve as rt
import tools.retrieve_generate as rg



if __name__ == "__main__":
    # rephrase
    # prompt = "幫我生成SAS軟體採購簽呈"
    # print("Testing rephrase_question...")
    # print(f"Input : {prompt}")
    # print(f"Output: {rf.rephrase_question(prompt)}")

    # retrieve and generate

    # KB_ID = "THK650DL3Q"
    # MODEL_ARN = "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-pro-v1:0"
    # question = "幫我生成2025 SAS地端簽呈。"
    # print("Testing ret_and_gen...")
    # response = rg.ret_and_gen(question, KB_ID, MODEL_ARN)
    # print(json.dumps(response, indent=2, ensure_ascii=False))

    # output_text = response.get("output", {}).get("text")
    # if output_text:
    #     output_dir = Path("output")
    #     output_dir.mkdir(parents=True, exist_ok=True)
    #     output_path = output_dir / "ret_and_gen.md"
    #     output_path.write_text(output_text, encoding="utf-8")
    #     print(f"Saved generated text to {output_path}")
    # else:
    #     print("No output text found in the response.")

    # retrieve
    KB_ID = "JJYFVHJSPA"

    # 得出chunk
    question = "幫我生成SAS地端簽呈，這份簽呈屬於軟體續約，軟體類別為SAS"
    #question = "幫我生成SAS Viya雲端簽呈，這份簽呈屬於軟體新約，軟體類別為SAS Viya"
    # print("Testing retrieve_from_kb...")
    #print(json.dumps(rt.retrieve_from_kb(question, KB_ID), indent=2, ensure_ascii=False))

    # 得出metadata filter 
    print(rt._generate_metadata_filter("幫我生成2025 SAS地端簽呈，這份簽呈屬於軟體續約，軟體類別為SAS，申請單位為系統資訊部"))
    #print(rt._generate_metadata_filter("幫我生成SAS Viya雲端簽呈"))
