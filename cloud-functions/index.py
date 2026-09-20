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
        /* ---------- 可爱配色：浅色 / 深色自动适配 ---------- */
        :root {
            --bg1: #fff0f7;
            --bg2: #eef6ff;
            --ai-bubble: #ffffff;
            --text: #4a4266;
            --muted: #a89ab8;
            --input-bg: #ffffff;
            --input-border: #f3d9e8;
            --avatar-bg-ai: #ffe1f0;
            --avatar-bg-user: #e3ecff;
            --shadow: 0 4px 16px rgba(183, 148, 246, 0.18);
            --send-bg: linear-gradient(135deg, #ff9ecd, #b794f6);
        }

        @media (prefers-color-scheme: dark) {
            :root {
                --bg1: #1e1b2e;
                --bg2: #26213d;
                --ai-bubble: #2e2a47;
                --text: #ece7ff;
                --muted: #9b92bd;
                --input-bg: #2e2a47;
                --input-border: #453d66;
                --avatar-bg-ai: #42355c;
                --avatar-bg-user: #34406b;
                --shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
            }
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        html, body { height: 100%; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                         "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
            background: linear-gradient(160deg, var(--bg1), var(--bg2));
            color: var(--text);
            max-width: 640px;
            margin: 0 auto;
            height: 100vh;
            height: 100dvh;
            padding: 16px 16px 20px;
            display: flex;
            flex-direction: column;
        }

        /* ---------- 头部 ---------- */
        header { text-align: center; padding: 12px 0 10px; }
        header h1 { font-size: 1.25rem; letter-spacing: 1px; }
        header .sub { font-size: 0.8rem; color: var(--muted); margin-top: 4px; }

        /* ---------- 聊天区 ---------- */
        #chat-box {
            flex: 1;
            overflow-y: auto;
            padding: 10px 4px 16px;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }

        /* 一条消息 = 表情头像 + 气泡；用户消息左右对调 */
        .msg { display: flex; align-items: flex-end; gap: 10px; animation: popIn 0.3s ease both; }
        .msg.user { flex-direction: row-reverse; }

        .avatar {
            flex: none;
            width: 42px;
            height: 42px;
            border-radius: 50%;
            background: var(--avatar-bg-ai);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            box-shadow: var(--shadow);
        }
        .msg.user .avatar { background: var(--avatar-bg-user); }

        .bubble {
            max-width: 78%;
            padding: 12px 16px;
            border-radius: 20px 20px 20px 6px;   /* 左下角小尾巴，像在说话 */
            background: var(--ai-bubble);
            color: var(--text);
            box-shadow: var(--shadow);
            font-size: 0.95rem;
            line-height: 1.6;
            white-space: pre-wrap;   /* 保留 AI 回复里的换行 */
            word-break: break-word;
        }
        .msg.user .bubble {
            border-radius: 20px 20px 6px 20px;   /* 尾巴换到右下角 */
            background: var(--send-bg);
            color: #ffffff;
        }

        @keyframes popIn {
            from { opacity: 0; transform: translateY(10px) scale(0.97); }
            to   { opacity: 1; transform: none; }
        }

        /* "正在思考"的三个小点点 */
        .typing-dots span {
            display: inline-block;
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--muted);
            margin-right: 5px;
            animation: blink 1.2s infinite;
        }
        .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
        .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes blink {
            0%, 80%, 100% { opacity: 0.25; transform: translateY(0); }
            40%          { opacity: 1;    transform: translateY(-3px); }
        }

        /* ---------- 底部输入栏 ---------- */
        .input-bar { display: flex; gap: 10px; padding-top: 10px; }

        #user-input {
            flex: 1;
            min-width: 0;
            padding: 13px 20px;
            border: 2px solid var(--input-border);
            border-radius: 999px;
            background: var(--input-bg);
            color: var(--text);
            font-size: 0.95rem;
            outline: none;
            transition: border-color 0.2s ease;
        }
        #user-input:focus { border-color: #ff9ecd; }

        .btn {
            border: none;
            border-radius: 999px;
            padding: 0 20px;
            cursor: pointer;
            font-size: 0.95rem;
            background: var(--send-bg);
            color: #ffffff;
            box-shadow: var(--shadow);
            transition: transform 0.15s ease;
        }
        .btn:hover { transform: scale(1.05); }

        .btn.ghost {
            background: var(--input-bg);
            color: var(--muted);
            border: 2px solid var(--input-border);
            padding: 0 16px;
        }

        @media (prefers-reduced-motion: reduce) {
            * { animation: none !important; transition: none !important; }
        }
    </style>
</head>
<body>
    <header>
        <h1>🤖 我的第一个 AI Agent</h1>
        <div class="sub">和 AI 聊聊天吧～</div>
    </header>
    <div id="chat-box"></div>
    <div class="input-bar">
        <input type="text" id="user-input" placeholder="输入你的问题…" onkeypress="if(event.key==='Enter') sendMessage()">
        <button class="btn ghost" onclick="clearChat()" title="清空对话">🧹</button>
        <button class="btn" onclick="sendMessage()">发送 🚀</button>
    </div>

    <script>
        // 多轮对话记忆：历史保存在前端这个数组里，每次请求完整发给后端
        let messages = [];
        const MAX_HISTORY = 20;  // 最多携带最近 20 条历史（约 10 轮），防止请求无限变大
        let sending = false;
        const FETCH_TIMEOUT_MS = 120000;  // 请求超时上限 2 分钟，AI 回复较慢，可按需调整

        // 表情包：AI 每次回复随机换一个可爱表情当头像，你的头像固定，思考中用 💭
        const AI_EMOJIS = ['😊', '🥰', '😄', '🤗', '✨', '💖', '🌸', '🥳', '😇', '🍀', '🦄', '🎀'];
        const USER_EMOJI = '👧';
        const THINKING_EMOJI = '💭';
        const ERROR_EMOJI = '😵';

        const chatBox = document.getElementById('chat-box');

        function randomEmoji() {
            return AI_EMOJIS[Math.floor(Math.random() * AI_EMOJIS.length)];
        }

        // 创建一条消息（表情头像 + 气泡），文本一律用 textContent 写入，天然防 XSS
        function addMsg(role, text, avatarEmoji) {
            const row = document.createElement('div');
            row.className = 'msg ' + role;

            const avatar = document.createElement('div');
            avatar.className = 'avatar';
            avatar.textContent = avatarEmoji || (role === 'user' ? USER_EMOJI : randomEmoji());

            const bubble = document.createElement('div');
            bubble.className = 'bubble';
            bubble.textContent = text;

            row.appendChild(avatar);
            row.appendChild(bubble);
            chatBox.appendChild(row);
            chatBox.scrollTop = chatBox.scrollHeight;
            return { avatar: avatar, bubble: bubble };
        }

        // "AI 正在思考"消息：气泡里是三个会跳动的小点点
        function addTyping() {
            const typing = addMsg('ai', '', THINKING_EMOJI);
            typing.bubble.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';
            return typing;
        }

        async function sendMessage() {
            if (sending) return;
            const input = document.getElementById('user-input');
            const text = input.value.trim();
            if (!text) return;
            sending = true;

            addMsg('user', text);
            input.value = '';

            // 直接持有"思考中"消息的引用，结束时更新它，
            // 而不是靠 id 查找（连续发送时 id 会重复，getElementById 会命中旧消息，
            // 导致新的"思考中"永远没人更新——之前页面假死的原因）
            const typing = addTyping();

            // 新问题先记进历史，再连同之前的完整历史一起发给后端
            messages.push({ role: 'user', content: text });

            // 超时控制：到时间自动中断 fetch，避免页面无限期停在"AI 正在思考..."
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
                typing.bubble.textContent = reply;
                typing.avatar.textContent = ok ? randomEmoji() : ERROR_EMOJI;  // 回复完换个表情
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
            chatBox.innerHTML = '';
            document.getElementById('user-input').value = '';
            addMsg('ai', '对话已清空～我们重新开始吧！😊');
        }

        // 首次进入时打个招呼（纯页面展示，不写进发给后端的历史）
        addMsg('ai', '你好呀！我是你的 AI 小助手，有什么想聊的嘛？🥰');
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