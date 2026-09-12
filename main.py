import os
from openai import OpenAI
from dotenv import load_dotenv

# 加载 .env 文件中的密钥
load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
if not api_key:
    raise ValueError("没有找到 DEEPSEEK_API_KEY，请检查 .env 文件")

# 初始化客户端，指向 DeepSeek
client = OpenAI(
    api_key=api_key,
    base_url="https://api.deepseek.com"
)

print("🤖 你的第一个 DeepSeek Agent 已上线！(输入 quit 退出)")

while True:
    user_input = input("\n你: ")
    if user_input.lower() == "quit":
        print("下次见！")
        break

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个乐于助人的AI助手。"},
                {"role": "user", "content": user_input}
            ],
            stream=False
        )
        print("AI:", response.choices[0].message.content)
    except Exception as e:
        print(f"出错了: {e}")