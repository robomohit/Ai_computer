# AI Computer 🚀

An autonomous AI agent that controls your computer using natural language. 

AI Computer is a high-performance, open-source alternative to proprietary computer-use agents. It is designed to be **extensible**, **provider-agnostic**, and **production-ready**, supporting multiple LLM backends and three specialized operating modes.

---

## 🔥 Key Features

### 💻 Specialized Coding Mode
- **Zero-Vision Overhead**: Optimized for software engineering. Bypasses screenshots and vision models for maximum speed and accuracy.
- **Local Toolchain**: Directly interacts with your shell, filesystem, and editors.
- **Dynamic Context**: Automatically discovers your environment (OS, user home, workspace) to ensure robust path resolution across Windows, MacOS, and Linux.
- **Live Code Panel**: See files created/modified in real-time, plus a terminal view for command output.

### 🌐 Computer Use Mode (Browser Automation)
- **Headless Browser**: Uses Playwright in the background — never touches your real desktop.
- **DOM-Based Navigation**: Reads pages via accessibility tree, not pixel coordinates.
- **Permission System**: The agent must request permission before accessing the browser or Google Sheets.
- **Background Operation**: You can keep using your computer while the agent works.

### 🖥️ Desktop Mode (Computer Vision)
- **Full Screen Control**: Takes over mouse and keyboard for GUI automation.
- **Live Screenshots**: Real-time screen previews in the dashboard.
- **Visual Verification**: Post-action screenshots to verify results.

### 📡 Real-Time SSE Streaming
- **Live Dashboard**: A stunning UI that shows the agent's thought process as it happens.
- **Auto-Reconnect**: If the SSE connection drops, the client automatically retries with a 3-second backoff and recovers gracefully.
- **Adaptive UI**:
  - **Thinking Indicators**: Watch the agent "think" in real-time with pulse animations.
  - **Action Cards**: Color-coded results (Success/Failure) for every tool usage.
  - **Activity Log**: High-granularity system logs streamed directly from the agent's core.

### 🌍 Provider Agnostic
- **Multi-LLM Support**: Configurable with Anthropic (Claude), OpenAI (GPT-4), Google (Gemini), Groq, and OpenRouter.
- **Free-Tier Optimization**: Works flawlessly with free-tier models via OpenRouter.
- **Grouped Model Selector**: Models are organized by provider in the dropdown (optgroup).
- **API Key Validation**: Only models with configured API keys are shown. Selecting an unconfigured model returns a clear error message identifying which key is missing.
- **Intelligent Fallback**: For OpenRouter vision tasks, automatically switches between Gemma 31B and 26B models to handle rate limits.

### 🛡️ Safety & Security
- **Hard-Blocked Commands**: Protects against dangerous shell commands (`rm -rf /`, `del c:\`, etc.).
- **Manual Approval Flow**: High-risk actions pause execution and wait for user confirmation via a modal dialog. Keyboard shortcuts: `Enter` to approve, `Esc` to deny.
- **Permission Scopes**: Browser and sensitive operations require explicit user permission.
- **Secure API Key Handling**: API keys are masked in server logs (only first 6 and last 4 characters shown). The full key is only retrievable via the authenticated `/api/config` endpoint.
- **Isolated Workspace**: Enforces standard operating boundaries while allowing home-directory access for specific user tasks.

### ⏸️ Pause / Resume / Cancel
- **Pause**: Halts the agent at the next action boundary. UI shows "Paused" status.
- **Resume**: Continues from where it left off.
- **Cancel**: Immediately stops the task and marks it as cancelled.
- **Keyboard Shortcut**: Press `Space` (when not typing) to toggle pause.

### 📜 Task History
- **Persistent Logs**: Every task's events are saved as JSONL files in `workspace/logs/`.
- **Clickable History**: Click any past task in the sidebar to replay its full event log, including plans, actions, reflections, file changes, and terminal output.
- **Code Panel Replay**: Past coding tasks show all created/modified files in the right panel.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- pip (Python package manager)
- Playwright (optional, for computer-use mode): `playwright install chromium`

### 2. Installation
```bash
git clone https://github.com/robomohit1/Ai_computer.git
cd Ai_computer
pip install -r requirements.txt
# Optional: install Playwright for browser automation mode
playwright install chromium
```

### 3. Configuration
Copy the example environment file and add your API keys:
```bash
cp .env.example .env
```

**Required**: At least one API key must be set for the agent to work.

| Variable | Provider | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | OpenRouter | **Recommended** — free tier models available |
| `ANTHROPIC_API_KEY` | Anthropic | Claude models (paid) |
| `OPENAI_API_KEY` | OpenAI | GPT-4o models (paid) |
| `GOOGLE_API_KEY` | Google | Gemini models (paid) |
| `GROQ_API_KEY` | Groq | Llama models (free tier available) |
| `AGENT_API_KEY` | Internal | Secures the API. Auto-generated if not set. |

> **Tip**: For free usage, just set `OPENROUTER_API_KEY`. Get one at [openrouter.ai](https://openrouter.ai/).

### 4. Launch
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```
Open your browser to `http://localhost:8080`.

The server will print a masked API key on startup. Use the `/api/config` endpoint to retrieve the full key if needed.

---

## 🏗️ Architecture

```
┌─────────────┐    SSE     ┌──────────────┐    HTTP     ┌───────────────┐
│   Browser   │◄──────────►│  FastAPI App  │◄───────────►│   LLM APIs    │
│  (Frontend) │            │   main.py     │             │ (OpenRouter,  │
└─────────────┘            └──────┬───────┘             │  Anthropic,   │
                                  │                      │  OpenAI, etc) │
                           ┌──────▼───────┐             └───────────────┘
                           │ AgentService  │
                           │   agent.py    │
                           └──┬────┬──┬───┘
                    ┌─────────┘    │  └──────────┐
              ┌─────▼──────┐ ┌────▼─────┐ ┌─────▼──────┐
              │   Tools    │ │ Provider │ │  Safety &  │
              │  tools.py  │ │providers │ │ Permissions│
              └────────────┘ └──────────┘ └────────────┘
```

1. **Agent Engine** (`agent.py`): Asynchronous event loop that processes tasks with hierarchical planning.
2. **Planner Provider** (`providers.py`): Converts goals into sequential sub-tasks using your chosen LLM. Supports Anthropic, OpenAI, Google, Groq, and OpenRouter backends.
3. **SSE Dispatcher** (`log_emitter.py`): Streams logs, screenshots, and statuses to the frontend over persistent Server-Sent Events. Includes log replay for fast-completing tasks.
4. **Tool Executor** (`tools.py`): Sandboxed execution layer for filesystem, shell, editor, and browser interactions.
5. **Safety Manager** (`safety.py`): Evaluates action risk levels and gates dangerous operations behind user approval.
6. **Permission Store** (`permissions.py`): Tracks user-granted permissions per task for browser and sensitive operations.

---

## 🧪 Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test suites
python -m pytest tests/test_agent.py -v
python -m pytest tests/test_integration.py -v
python -m pytest tests/test_security.py -v
```

---

## 🐳 Docker Support

Deploy instantly with Docker Compose:
```bash
docker-compose up --build
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Enter` | Send task |
| `Shift+Enter` | New line in composer |
| `Ctrl/⌘+K` | Open command palette |
| `Ctrl/⌘+N` | Focus task input |
| `Space` | Toggle pause (when not typing) |
| `Ctrl/⌘+Shift+O` | Toggle screenshot lightbox |
| `Esc` | Close modals/palette |

---

## 🔌 API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serve the frontend |
| `GET` | `/api/health` | Health check + uptime |
| `GET` | `/api/config` | Get API key (for frontend auth) |
| `GET` | `/api/models` | List available models (filtered by configured keys) |
| `GET` | `/api/tasks` | List all tasks |
| `POST` | `/api/tasks` | Create a new task |
| `GET` | `/api/tasks/{id}` | Get task details |
| `DELETE` | `/api/tasks/{id}` | Cancel a task |
| `POST` | `/api/tasks/{id}/pause` | Pause a running task |
| `POST` | `/api/tasks/{id}/resume` | Resume a paused task |
| `GET` | `/api/tasks/{id}/log` | Get task event log |
| `GET` | `/api/tasks/{id}/stream` | SSE event stream |
| `POST` | `/api/approvals` | Submit approval decision |
| `POST` | `/api/permissions` | Submit permission decision |

---

## 📜 License
MIT License. Created by [robomohit1](https://github.com/robomohit1).
