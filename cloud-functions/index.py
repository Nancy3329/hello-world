from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from openai import OpenAI
import os
import uuid
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

# 多轮对话记忆：session_id -> 历史消息列表
chat_histories = {}
MAX_HISTORY = 20    # 每个会话最多保留最近 20 条消息（约 10 轮对话）
MAX_SESSIONS = 100  # 最多保留 100 个会话，防止内存无限增长

class ChatRequest(BaseModel):
    message: str
    session_id: str = ""  # 为空时后端自动生成

class ClearRequest(BaseModel):
    session_id: str

# 网页代码直接写在这里
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
    <button onclick="clearChat()">清空对话</button>

    <script>
        // 会话 ID：后端用它记住多轮对话
        let sessionId = '';
        try { sessionId = crypto.randomUUID(); } catch (e) {
            sessionId = Date.now().toString(36) + Math.random().toString(36).slice(2);
        }
        let sending = false;

        function escapeHtml(s) {
            const div = document.createElement('div');
            div.textContent = s;
            return div.innerHTML;
        }

        async function sendMessage() {
            if (sending) return;
            const input = document.getElementById('user-input');
            const text = input.value.trim();
            if (!text) return;
            sending = true;

            const chatBox = document.getElementById('chat-box');
            chatBox.innerHTML += `<div class="msg user">你: ${escapeHtml(text)}</div>`;
            input.value = '';

            chatBox.innerHTML += `<div class="msg ai" id="loading">AI 正在思考...</div>`;
            chatBox.scrollTop = chatBox.scrollHeight;

            let reply = '出错了，请稍后重试';
            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, session_id: sessionId })
                });
                const data = await response.json();
                if (data.session_id) sessionId = data.session_id;
                reply = data.reply;
            } catch (e) {
                reply = '请求失败: ' + e.message;
            } finally {
                sending = false;
            }

            const loadingEl = document.getElementById('loading');
            if (loadingEl) loadingEl.innerText = `AI: ${reply}`;
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        async function clearChat() {
            await fetch('/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId })
            });
            document.getElementById('chat-box').innerHTML = '';
            document.getElementById('user-input').value = '';
        }
    </script>
</body>
</html>
"""

# 根路径返回网页，且强制声明是 HTML 格式
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return HTML_CONTENT

# 聊天接口
@app.post("/chat")
async def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    try:
        history = chat_histories.setdefault(session_id, [])
        history.append({"role": "user", "content": request.message})

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个乐于助人的AI助手。"}
            ] + history
        )
        reply = response.choices[0].message.content
        history.append({"role": "assistant", "content": reply})

        # 只保留最近 N 条消息，避免历史越来越长
        if len(history) > MAX_HISTORY:
            del history[:-MAX_HISTORY]

        # 会话太多时丢弃最旧的会话
        if len(chat_histories) > MAX_SESSIONS:
            for old in list(chat_histories)[:-MAX_SESSIONS]:
                chat_histories.pop(old, None)

        return {"reply": reply, "session_id": session_id}
    except Exception as e:
        return {"reply": f"出错了: {str(e)}", "session_id": session_id}


# 清空指定会话的历史记录
@app.post("/clear")
async def clear(request: ClearRequest):
    chat_histories.pop(request.session_id, None)
    return {"ok": True}