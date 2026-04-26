# AI Computer

An autonomous AI agent that controls your computer using plain English. Give it a goal — it plans, acts, and shows you exactly what it's doing in real time.

> Coding and browser modes run on Windows, macOS, and Linux; desktop control is Windows-focused. Free to run with OpenRouter free-tier models, subject to OpenRouter's limits.

---

## Quick Start (3 steps)

### 1. Clone & setup

**Windows** — double-click `setup.bat`, or run in terminal:
```cmd
git clone https://github.com/robomohit/Ai_computer.git
cd Ai_computer
setup.bat
```

**Mac / Linux:**
```bash
git clone https://github.com/robomohit/Ai_computer.git
cd Ai_computer
chmod +x setup.sh && ./setup.sh
```

### 2. Add your API key

Open `.env` and paste in at least one key:

```env
OPENROUTER_API_KEY=sk-or-v1-...   # free tier — recommended
```

> Get a free-tier key at [openrouter.ai](https://openrouter.ai/). Availability and rate limits are controlled by OpenRouter.

### 3. Launch

**Windows:** double-click `start.bat`

**Mac / Linux:**
```bash
chmod +x start.sh && ./start.sh
```

Then open **http://localhost:8080** in your browser.

---

## Modes

| Mode | What it does |
|---|---|
| **Coding** | Writes, edits, and runs code. No screenshots — fast and accurate. |
| **Browser** | Controls a headless Chrome browser via accessibility tree. Fills forms, navigates sites, reads pages. |
| **Desktop** | Full mouse + keyboard control with live screenshot previews. |

The mode is **auto-detected** from your goal, or you can pick it manually.

---

## Desktop App (optional)

Run as a native window instead of a browser tab:

```bash
# Windows
pip install -r requirements-desktop.txt
python run_desktop.py

# Mac / Linux
pip3 install -r requirements-desktop.txt
python3 run_desktop.py
```

Requires `pywebview` (installed automatically by `requirements-desktop.txt`).

---

## Semantic Memory (optional)

For richer memory that uses vector search instead of keyword matching:

```bash
pip install -r requirements-memory.txt
```

Then add to `.env`:
```env
USE_CHROMA=1
```

---

## API Keys

| Variable | Provider | Cost |
|---|---|---|
| `OPENROUTER_API_KEY` | OpenRouter | **Free tier available** ✓ |
| `ANTHROPIC_API_KEY` | Claude (Anthropic) | Paid |
| `OPENAI_API_KEY` | GPT-4o (OpenAI) | Paid |
| `GOOGLE_API_KEY` | Gemini (Google) | Paid |
| `GROQ_API_KEY` | Llama (Groq) | Free tier available |
| `AGENT_API_KEY` | Internal auth | Auto-generated if blank |

---

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `Enter` | Send task |
| `Shift+Enter` | New line |
| `Ctrl+K` | Command palette |
| `Space` | Pause / resume |
| `Esc` | Close modal |

---

## Docker

```bash
docker-compose up --build
```

---

## Architecture

```
Browser UI  ──SSE──►  FastAPI (main.py)
                           │
                      AgentService (agent.py)
                      ├── PlannerProvider  → LLM APIs
                      ├── ToolExecutor     → shell / files / browser / desktop
                      ├── SafetyManager    → blocks dangerous commands
                      └── LogEmitter       → streams events to UI
```

---

## License

MIT — [robomohit](https://github.com/robomohit)
