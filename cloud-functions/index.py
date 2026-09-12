from fastapi import FastAPI
from fastapi.responses import HTMLResponse
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

# 把前端 HTML 直接写在这里
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>我的第一个 AI Agent</title>
    <style>
        body { font-family: sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
        #chat-box { border: 1px solid #ccc; height: 400px; overflow-y: scroll; padding: 10px; margin-bottom: 10px; }
        .msg { margin: 10px 0; }
        .user { text-align: right; color: blue; }
        .ai { text-align: left; color: green; }
        input { width: 80%; padding: 10px; }
        button { padding: 10px; }
    </style>
</head>
<body>
    <h1>🤖 我的第一个 AI Agent</h1>
    <div id="chat-box"></div>
    <input type="text" id="user-input" placeholder="输入你的问题..." onkeypress="if(event.key==='Enter') sendMessage()">
    <button onclick="sendMessage()">发送</button>

    <script>
        async function sendMessage() {
            const input = document.getElementById('user-input');
            const text = input.value.trim();
            if (!text) return;

            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML += `<div class="msg user">你: ${text}</div>`;
            input.value = '';

            chatBox.innerHTML += `<div class="msg ai" id="loading">AI 正在思考...</div>`;
            chatBox.scrollTop = chatBox.scrollHeight;

            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });
            const data = await response.json();
            
            document.getElementById('loading').innerText = `AI: ${data.reply}`;
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    </script>
</body>
</html>
"""

# 根路径直接返回网页
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return HTML_CONTENT

# API 聊天接口
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