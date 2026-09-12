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

# 多轮对话记忆改由前端保存：每次请求前端把完整历史一起传来，
# 后端无状态、不存储任何会话数据（EdgeOne 云函数实例间不共享内存）
class ChatRequest(BaseModel):
    messages: list = []  # 前端传来的对话历史：[{role, content}, ...]

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
        // 多轮对话记忆：历史保存在前端这个数组里，每次请求完整发给后端
        let messages = [];
        const MAX_HISTORY = 20;  // 最多携带最近 20 条历史（约 10 轮），防止请求无限变大
        let sending = false;
        const FETCH_TIMEOUT_MS = 120000;  // 请求超时上限 2 分钟，AI 回复较慢，可按需调整

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

            // 直接持有"AI 正在思考..."元素的引用，结束时更新它，
            // 而不是靠 id 查找（连续发送时 id 会重复，getElementById 会命中旧消息，
            // 导致新的"思考中"永远没人更新——之前页面假死的原因）
            const loadingEl = document.createElement('div');
            loadingEl.className = 'msg ai';
            loadingEl.innerText = 'AI 正在思考...';
            chatBox.appendChild(loadingEl);
            chatBox.scrollTop = chatBox.scrollHeight;

            // 超时控制：到时间自动中断 fetch，避免页面无限期停在"AI 正在思考..."
            // 新问题先记进历史，再连同之前的完整历史一起发给后端
            messages.push({ role: 'user', content: text });

            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

            let reply = '出错了，请稍后重试';
            let ok = false;  // 是否真正拿到 AI 回复（决定历史怎么记录）
            try {
                const response = await fetch('/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ messages: messages.slice(-MAX_HISTORY) }),
                    signal: controller.signal
                });

                // 先检查 HTTP 状态码：非 200 时响应体通常不是 JSON
                //（例如平台网关返回的 HTML 错误页），此时不要调用 response.json()，
                // 而是读出文本展示，方便排查
                if (!response.ok) {
                    let body = '';
                    try { body = (await response.text()).slice(0, 300); } catch (e) { body = ''; }
                    reply = `HTTP 错误 ${response.status} ${response.statusText}: ${body}`;
                } else {
                    const data = await response.json();
                    reply = data.reply || '(后端未返回内容)';
                    ok = true;
                }
            } catch (e) {
                // AbortError = 超时主动中断；其余异常（断网、JSON 解析失败等）一并兜底
                reply = e.name === 'AbortError'
                    ? `请求超时（${FETCH_TIMEOUT_MS / 1000} 秒无响应），请检查网络或稍后重试`
                    : `请求失败: ${e.message}`;
            } finally {
                // 无论成功、失败还是超时，都结束"思考中"状态，避免页面假死
                clearTimeout(timer);
                sending = false;
                loadingEl.innerText = `AI: ${reply}`;
                chatBox.scrollTop = chatBox.scrollHeight;
            }

            // 拿到回复才把 AI 回答写进历史；失败则撤掉刚才的问题，
            // 保证历史一问一答成对，下次发给 DeepSeek 时格式正确
            if (ok) {
                messages.push({ role: 'assistant', content: reply });
            } else {
                messages.pop();
            }
        }

        function clearChat() {
            // 历史就在前端的 messages 数组里：清掉数组和页面即可，无需请求后端
            messages = [];
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

# 聊天接口：无状态，前端传来的完整历史原样转发给 DeepSeek
@app.post("/")
async def chat(request: ChatRequest):
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个乐于助人的AI助手。"}
            ] + request.messages
        )
        reply = response.choices[0].message.content
        return {"reply": reply}
    except Exception as e:
        return {"reply": f"出错了: {str(e)}"}