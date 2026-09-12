from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

class ChatRequest(BaseModel):
    message: str

# 前端请求的是 /api/chat，所以这里保留完整的路径
@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个乐于助人的AI助手。"},
                {"role": "user", "content": request.message}
            ]
        )
        return {"reply": response.choices[0].message.content}
    except Exception as e:
        return {"reply": f"出错了: {str(e)}"}