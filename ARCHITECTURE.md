# Architecture

## System diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        User's Browser                           │
│                    http://localhost:8501                         │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTP (Streamlit)
┌───────────────────────────────▼─────────────────────────────────┐
│                        app.py  (Streamlit)                       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Session state                                           │   │
│  │  ├── messages[]          display history (local)         │   │
│  │  └── resp_id             last response ID (pointer)      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  System prompt  (built once at startup)                  │   │
│  │  ├── INSTRUCTIONS        conversation flow rules         │   │
│  │  ├── <manual>            manual_ea6350.txt  (17 KB)      │   │
│  │  └── <visual_descriptions>  manual_images.txt  (11 KB)   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                │                                 │
│          client.responses.stream()                               │
│          ├── instructions=INSTRUCTIONS                           │
│          ├── input=<new user message only>                       │
│          ├── previous_response_id=resp_id                        │
│          └── store=True                                          │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTPS
┌───────────────────────────────▼─────────────────────────────────┐
│                    OpenAI Responses API                          │
│                                                                  │
│  ┌─────────────────────────────────────────────────────┐        │
│  │  Server-side conversation thread                    │        │
│  │  resp_0 → resp_1 → resp_2 → …                      │        │
│  │  (full history stored by OpenAI, not resent)        │        │
│  └─────────────────────────────────────────────────────┘        │
│                                                                  │
│  Streaming: response.output_text.delta events                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     Startup (once, cached)                       │
│                                                                  │
│   EA6350_manual.pdf                                              │
│        │                                                         │
│        ├─ pypdf ──────────────► manual_ea6350.txt  (text)       │
│        │    English pages 1-19    injected into instructions     │
│        │                                                         │
│        └─ pymupdf ────────────► base64 PNG  ×3 pages            │
│             pages 3, 4, 17         held in RAM (never on disk)   │
│             rendered at 108 dpi    cached via @st.cache_resource │
└─────────────────────────────────────────────────────────────────┘

## Image memory model

Images are never written to disk. The pipeline is entirely in-memory:

  EA6350_manual.pdf
    │
    └─ pymupdf.open()  ──►  page.get_pixmap()  ──►  .tobytes("png")
                                (render to RAM)       (PNG bytes in RAM)
                                     │
                                     ▼
                             base64.b64encode()
                                     │
                                     ▼
                             MANUAL_IMAGES[]   ←── @st.cache_resource
                          (list of base64 strs)     (survives reruns)
                                     │
                              sent on every turn
                                     ▼
                         "data:image/png;base64,…"  in API input array

The PDF is opened once at startup, the 3 pages are rendered, and the file
handle is closed. All subsequent API calls read from the in-memory list.

Per-turn input structure:
  [
    { role: "user", content: [
        { type: "input_text",  text: "EA6350 top view — LED, USB port"  },
        { type: "input_image", image_url: "data:image/png;base64,…", detail: "low" },
        { type: "input_text",  text: "EA6350 back view — ports & buttons" },
        { type: "input_image", image_url: "data:image/png;base64,…", detail: "low" },
        { type: "input_text",  text: "Smart Wi-Fi — Troubleshooting > Reboot UI" },
        { type: "input_image", image_url: "data:image/png;base64,…", detail: "low" },
        { type: "input_text",  text: <user message> },
    ]}
  ]
```

## File map

```
routethis_assign/
├── app.py                    Main Streamlit app
├── manual_ea6350.txt         Extracted text — EA6350 user guide, English pages 1–19
├── EA6350_manual.pdf         Original manual PDF (source of truth for text + images)
├── extract_image_context.py  Utility: renders PDF pages for inspection (not used at runtime)
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── ARCHITECTURE.md           (this file)
└── DECISIONS.md
```

## Conversation state

```
Turn 1                        Turn 2                        Turn 3
──────                        ──────                        ──────
input: "internet is down"     input: "just now"             input: "done, unplugged"
instructions: INSTRUCTIONS    previous_response_id: r1      previous_response_id: r2
store: True                   store: True                   store: True
        │                             │                             │
        ▼                             ▼                             ▼
   response r1               response r2                   response r3
  (OpenAI stores)            (OpenAI stores)               (OpenAI stores)
```

Only the new user message is sent each turn. OpenAI reconstructs the full context from the stored thread via `previous_response_id`.

## Conversation flow (state machine)

```
START
  │
  ▼
[QUALIFY] ── not appropriate ──► explain + exit gracefully
  │
  │  appropriate
  ▼
[ANSWER QUESTIONS] ◄──────────────────────────────┐
  │                                               │ any question
  │  reboot confirmed                             │
  ▼                                               │
[GUIDE REBOOT] ─── step by step from manual ──────┘
  │
  ▼
[VERIFY]
  ├── yes ──► congratulate + note settings preserved + END
  └── no  ──► apologise + next steps from manual + END
```
