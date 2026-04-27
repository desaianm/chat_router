# WiFi Helper — Router Reboot Chatbot

A compact LLM-powered chat assistant that diagnoses WiFi connectivity issues and walks users through a reboot of their **Linksys EA6350** router, grounded in the official device manual.

## What it does

The bot follows a strict four-phase flow:

1. **Qualify** — asks targeted questions to determine whether a reboot is appropriate. Exits gracefully if the issue is an ISP outage, a single-device problem, or repeated failed reboots.
2. **Answer questions** — responds to any user question about the process using only the official EA6350 user guide.
3. **Guide the reboot** — walks through the power-cord procedure one step at a time, sourced directly from the manual.
4. **Verify** — asks if the issue is resolved. Ends warmly on success; directs to Linksys support if not.

## Stack

| Layer | Choice |
|-------|--------|
| UI | [Streamlit](https://streamlit.io) |
| LLM | OpenAI Responses API (`gpt-5.4-mini` default) |
| Grounding | Linksys EA6350 user guide (pages 1–19, extracted to `manual_ea6350.txt`) |
| Conversation state | `previous_response_id` — server-side multi-turn, no full history resent |

## Run locally

### Prerequisites

- Python 3.11+
- An [OpenAI API key](https://platform.openai.com/api-keys)

### Setup

```bash
# 1. Clone
git clone https://github.com/desaianm/chat_router.git
cd chat_router

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
# Option A — uv (faster): brew install uv
uv pip install -r requirements.txt

# Option B — standard pip
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and paste your OpenAI API key

# 5. Run
streamlit run app.py
```

The app opens at **http://localhost:8501**.

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `OPENAI_MODEL` | `gpt-5.4-mini` | Any OpenAI chat model ID |

### Dependencies

| Package | Purpose |
|---------|---------|
| `streamlit` | Web UI |
| `openai>=2.0.0` | Responses API + vision |
| `pymupdf` | Render PDF pages to images at startup |
| `python-dotenv` | Load `.env` file |

## Design decisions

**PDF processing — text + vision.** The EA6350 manual is a multi-language PDF (499 pages). The English section (pages 1–19) was extracted once during development using `pypdf` and committed as `manual_ea6350.txt` (~17 KB). At runtime the app simply reads that file and injects it verbatim into the system prompt. For visual context that text alone can't convey (port colors, button positions, Smart Wi-Fi interface layout), `pymupdf` renders three key pages (top view, back view, Troubleshooting/Reboot UI) as PNG images on startup. These are base64-encoded and sent as `input_image` items alongside every user message, so the model can answer questions like "which port is yellow?" directly from the diagram pixels.

**Responses API over Chat Completions.** Uses `client.responses.stream()` with `previous_response_id` for stateful multi-turn — only the new user message is sent each turn, not the full history.

**System-prompt state machine.** The four phases (qualify → answer → guide → verify) are described as instructions, not hardcoded logic. The reboot steps are not written into the prompt — the model reads them from the `<manual>` block on demand.

**Structured output.** The model returns `{"answer": "...", "citations": [...]}` via JSON schema. Citations render as a collapsible Sources element below each message — outside the chat bubble so they never get clipped regardless of how many there are.

**Prompt caching.** The `instructions` block (~4K tokens of manual text) and the 3 static images form a common prefix on every request. OpenAI caches this automatically — 80–85% cache hit rate from turn 1 onwards.

**Single file.** All app logic lives in `app.py`.

## Possible extensions

**Voice interface.** The most natural next step — someone standing at their router with hands full should be able to speak rather than type. Concretely: capture mic audio in the browser via a custom Streamlit component, transcribe with OpenAI Whisper, feed the transcript into the existing Responses API call, and read the reply back via TTS. The reboot guidance maps naturally to spoken turn-by-turn instructions. I built this class of system recently: [Jarvis](https://github.com/desaianm/jarvis_computer) is a macOS voice agent built on Gemini Live that listens continuously, reasons over what's on screen, and takes actions — the STT/TTS plumbing from that project applies directly here.

**Multi-router support.** At startup, ask the user their router model, load the matching manual PDF, and extract text + key images for that model. The rest of the pipeline stays identical.

**Escalation handoff.** When the bot exits without resolving the issue, generate a structured support summary (model, symptoms, steps attempted, transcript) and POST it to a helpdesk API so a human agent picks up with full context.

## Manual reference

Reboot steps sourced from the Linksys EA6350 user guide (pages 16–17):
https://downloads.linksys.com/support/assets/userguide/EA6350_UG_INTL_update.pdf
