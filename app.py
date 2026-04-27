import os
import json
import base64
from pathlib import Path
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

MANUAL_TEXT = (Path(__file__).parent / "manual_ea6350.txt").read_text(encoding="utf-8")

# load manual page images at startup 
# Each entry: (page_index_0based, detail, one_line_description)
_PDF_PATH = Path(__file__).parent / "EA6350_manual.pdf"
_IMAGE_PAGES = [
    (2,  "low",  "EA6350 top view — LED indicator (front-center) and USB port (front-right)."),
    (3,  "low",  "EA6350 back view — left to right: WPS button, Reset button, 4 blue Ethernet ports, yellow Internet port, Power port, Power switch."),
    (16, "low",  "Linksys Smart Wi-Fi web interface — Troubleshooting > Diagnostics tab with Reboot button and confirmation dialog."),
]

@st.cache_resource
def load_manual_images() -> list[tuple[str, str, str]]:
    """Returns list of (description, base64_png, detail) for each key page."""
    if not _PDF_PATH.exists():
        return []
    try:
        import fitz
        doc = fitz.open(str(_PDF_PATH))
        result = []
        for page_idx, detail, description in _IMAGE_PAGES:
            pix = doc[page_idx].get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            b64 = base64.b64encode(pix.tobytes("png")).decode()
            result.append((description, b64, detail))
        doc.close()
        return result
    except Exception:
        return []

MANUAL_IMAGES = load_manual_images()

INSTRUCTIONS = f"""You are a friendly WiFi support assistant for the Routethis Company named WiFiBOT.
You have access to the full router documentation and page images provided below — use them
as your knowledge base. Answer naturally as a support agent. Please reference any source, document, or page
number in your replies and cite them properly.
If something is not covered by your knowledge, say you don't have that information and end the conversation gracefully.

<manual>
{MANUAL_TEXT}
</manual>

# How to handle the conversation

Always start by understanding what the user is experiencing before offering any advice.
Ask one or two short questions at a time — never more. You need to figure out the root cause of the issue based on 
the user's response and answer it based on the manual provided.

No matter how the user phrases their opening message — whether it's a complaint, a question,
or "why is X happening" — gather context first. Only move to guiding a reboot once you
understand the situation well enough to know it's the right step based on the manual.

If a reboot is clearly not the right solution based on the manual, explain briefly and close the conversation gracefully.

If unrelated to WiFi or this router, let the user know you can only help with connectivity
and router reboot questions.

Once a reboot is appropriate, walk through it one step at a time, waiting for the user to
confirm each step before moving on. Use the power-cord method by default; offer the
web-interface method if they ask. Use only the exact steps and timings you know — do not
improvise.

After the reboot, ask if their connection is restored.
- If yes: wrap up warmly, and mention that a power reboot doesn't erase their settings.
- If no: apologize the user for the inconvenience and exit the conversation in a helpful manner.

# Style
- Conversational and warm — like a helpful person, not a manual.
- One question or one step per message, never a list of instructions all at once.
- Short, plain sentences. No jargon.
- If the user drifts off-topic, gently bring them back.
- Be empathetic and patient, especially if the user is frustrated.

# Output format
Always respond with valid JSON matching this exact structure:
{{
  "answer": "<your conversational reply here>",
  "citations": ["<citation 1>", "<citation 2>"]
}}
- "answer" is the full reply shown to the user.
- "citations" is a list of short source references (e.g. "EA6350 User Guide, p. 3 — Top view").
  Leave it as an empty array [] if no specific section was referenced.
"""

_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "name": "wifi_response",
    "schema": {
        "type": "object",
        "properties": {
            "answer":    {"type": "string"},
            "citations": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["answer", "citations"],
        "additionalProperties": False,
    },
    "strict": True,
}

GREETING = "Hi! I'm here to help with your WiFi. What's going on — is your internet down, slow, dropping, or something else?"


def _build_input(user_message: str) -> list:
    """
    Wraps each user message with the manual page images so the model has
    visual context for every turn (port positions, button labels, UI screenshots).
    """
    content = []
    for description, b64, detail in MANUAL_IMAGES:
        content.append({"type": "input_text", "text": description})
        content.append({
            "type": "input_image",
            "image_url": f"data:image/png;base64,{b64}",
            "detail": detail,
        })
    content.append({"type": "input_text", "text": user_message})
    return [{"role": "user", "content": content}]

# Page config and HTML styling
st.set_page_config(page_title="WiFi Helper", page_icon="📶", layout="centered")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=JetBrains+Mono:wght@400;500&display=swap');

    /* ── base ── */
    html, body, [class*="css"] {
        font-family: 'Fraunces', serif !important;
        color: #e2e8f8 !important;
    }

    /* ── full-page dark gradient ── */
    .stApp {
        background: #090e1f !important;
        background-image:
            radial-gradient(ellipse 900px 500px at 0% 0%, #0f2545 0%, transparent 65%),
            radial-gradient(ellipse 700px 400px at 100% 0%, #2a1040 0%, transparent 60%),
            radial-gradient(ellipse 600px 600px at 50% 100%, #0a1830 0%, transparent 70%) !important;
    }

    /* hide Streamlit chrome */
    header[data-testid="stHeader"],
    [data-testid="stToolbar"],
    #MainMenu { visibility: hidden; height: 0; }
    footer { display: none; }

    /* ── layout ── */
    .block-container {
        padding-top: 2.5rem !important;
        padding-bottom: 2rem !important;
        max-width: 800px !important;
    }

    /* ── hero card ── */
    .hero {
        border: 1px solid rgba(100, 160, 255, 0.18);
        background: linear-gradient(135deg, rgba(15,37,69,0.6) 0%, rgba(42,16,64,0.4) 100%);
        padding: 1.4rem 1.6rem 1.3rem;
        border-radius: 16px;
        margin-bottom: 1.4rem;
        backdrop-filter: blur(12px);
        box-shadow: 0 0 0 1px rgba(100,160,255,0.06), 0 8px 32px rgba(0,0,0,0.4);
    }
    .hero .tag {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 10px;
        letter-spacing: 0.18em;
        color: #60a0f0;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }
    .hero h1 {
        margin: 0 0 0.3rem 0;
        font-size: 2.1rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: #f0f4ff;
    }
    .hero p {
        margin: 0;
        color: #94a8cc;
        font-size: 0.92rem;
        line-height: 1.5;
    }

    /* ── chat messages ── */
    [data-testid="stChatMessage"] {
        background: rgba(255,255,255,0.045) !important;
        border: 1px solid rgba(255,255,255,0.09) !important;
        border-radius: 14px !important;
        padding: 0.75rem 1rem 1rem !important;
        margin-bottom: 0.5rem !important;
        overflow: visible !important;
    }
    [data-testid="stChatMessage"] > div,
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
        overflow: visible !important;
    }
    [data-testid="stChatMessage"] p {
        color: #dce6f8 !important;
        line-height: 1.65 !important;
        font-size: 0.97rem !important;
    }

    /* ── chat input area — transparent wrapper, styled input ── */
    [data-testid="stBottom"],
    [data-testid="stBottom"] > div,
    [data-testid="stBottom"] > div > div,
    .stChatInputContainer,
    [data-testid="stChatInputContainer"] {
        background: transparent !important;
        background-color: transparent !important;
        box-shadow: none !important;
        border-top: none !important;
    }
    [data-testid="stChatInput"] {
        background: rgba(12, 20, 42, 0.85) !important;
        border: 1px solid rgba(100,160,255,0.22) !important;
        border-radius: 12px !important;
        color: #e2e8f8 !important;
        box-shadow: none !important;
        outline: none !important;
    }
    [data-testid="stChatInput"]:focus-within {
        border-color: rgba(100,160,255,0.5) !important;
        box-shadow: 0 0 0 3px rgba(100,160,255,0.1) !important;
        outline: none !important;
    }
    [data-testid="stChatInput"] textarea:focus {
        outline: none !important;
        box-shadow: none !important;
    }
    /* send button */
    [data-testid="stChatInput"] button {
        background: rgba(100,160,255,0.15) !important;
        border: 1px solid rgba(100,160,255,0.3) !important;
        border-radius: 8px !important;
        color: #90b8f8 !important;
    }
    [data-testid="stChatInput"] button:hover {
        background: rgba(100,160,255,0.28) !important;
        color: #c0d8ff !important;
    }

    /* ── sidebar ── */
    [data-testid="stSidebar"] {
        background: rgba(8, 14, 32, 0.85) !important;
        border-right: 1px solid rgba(255,255,255,0.07) !important;
    }
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #94a8cc !important;
        font-size: 0.75rem !important;
        letter-spacing: 0.12em !important;
        text-transform: uppercase !important;
        font-family: 'JetBrains Mono', monospace !important;
        margin-bottom: 0.8rem !important;
    }
    [data-testid="stSidebar"] small,
    [data-testid="stSidebar"] .stCaption {
        color: #5a6a88 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.72rem !important;
    }

    /* ── reset button ── */
    [data-testid="stSidebar"] .stButton > button {
        background: rgba(100,160,255,0.08) !important;
        border: 1px solid rgba(100,160,255,0.25) !important;
        color: #90b8f8 !important;
        border-radius: 8px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.78rem !important;
        letter-spacing: 0.05em !important;
        padding: 0.4rem 0.9rem !important;
        width: 100% !important;
        transition: all 0.15s ease !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(100,160,255,0.16) !important;
        border-color: rgba(100,160,255,0.45) !important;
        color: #c0d8ff !important;
    }

    /* hide default disclosure triangle on citations */
    details summary::-webkit-details-marker { display: none; }
    details summary::marker { display: none; }

    /* ── expander ── */
    [data-testid="stExpander"] {
        border: 1px solid rgba(255,255,255,0.07) !important;
        border-radius: 10px !important;
        background: rgba(255,255,255,0.02) !important;
    }

    /* ── suggestion chips (vertical stacked, left-aligned) ── */
    .block-container .stButton > button {
        background: rgba(255,255,255,0.04) !important;
        border: 1px solid rgba(100,160,255,0.18) !important;
        border-radius: 10px !important;
        color: #94b8e8 !important;
        font-size: 0.88rem !important;
        font-family: 'Fraunces', serif !important;
        padding: 0.55rem 1.1rem !important;
        display: flex !important;
        align-items: center !important;
        justify-content: flex-start !important;
        text-align: left !important;
        transition: all 0.15s ease !important;
        margin-bottom: 0.2rem !important;
        max-width: 420px !important;
    }
    .block-container .stButton > button p,
    .block-container .stButton > button span {
        text-align: left !important;
    }
    .block-container .stButton > button:hover {
        background: rgba(100,160,255,0.1) !important;
        border-color: rgba(100,160,255,0.38) !important;
        color: #c0d8ff !important;
    }
    </style>
    <div class="hero">
        <div class="tag">EA6350 &nbsp;·&nbsp; Support Chat</div>
        <h1>WiFi Helper</h1>
        <p>Trouble with your connection? I'll ask a few quick questions and walk you through a router reboot — grounded in the Linksys EA6350 user guide.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("Missing OPENAI_API_KEY. Copy .env.example to .env and add your key.")
    st.stop()

client = OpenAI(api_key=api_key)
MODEL = os.getenv("OPENAI_MODEL", "gpt-5-4-mini")

# Session state

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": GREETING, "citations": []}]
if "resp_id" not in st.session_state:
    st.session_state.resp_id = None
if "tokens_in" not in st.session_state:
    st.session_state.tokens_in = 0
if "tokens_out" not in st.session_state:
    st.session_state.tokens_out = 0
if "tokens_cached" not in st.session_state:
    st.session_state.tokens_cached = 0

def _citations_html(citations: list) -> str:
    if not citations:
        return ""
    items = "".join(
        f'<div style="display:flex;align-items:baseline;gap:0.5rem;padding:0.3rem 0;border-bottom:1px solid rgba(255,255,255,0.05);">'
        f'<span style="color:#4a7aaa;font-size:0.7rem;flex-shrink:0;">↗</span>'
        f'<span style="color:#7a9ac0;font-size:0.78rem;line-height:1.5;">{c}</span></div>'
        for c in citations
    )
    return f"""
    <details style="margin-top:-0.2rem;margin-bottom:0.4rem;padding-left:3.5rem;">
      <summary style="
        cursor:pointer;
        font-size:0.7rem;
        color:#4a7aaa;
        font-family:'JetBrains Mono',monospace;
        letter-spacing:0.1em;
        text-transform:uppercase;
        list-style:none;
        display:inline-flex;
        align-items:center;
        gap:0.4rem;
        padding:0.25rem 0.7rem;
        border:1px solid rgba(80,130,210,0.2);
        border-radius:6px;
        background:rgba(80,130,210,0.06);
        user-select:none;
        transition:all 0.15s ease;
      ">
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style="opacity:0.6">
          <path d="M1 2h8M1 5h6M1 8h4" stroke="#6090d0" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        Sources
      </summary>
      <div style="margin-top:0.5rem;padding:0.5rem 0.75rem;border-left:2px solid rgba(80,130,210,0.25);border-radius:0 6px 6px 0;background:rgba(80,130,210,0.04);">
        {items}
      </div>
    </details>"""

def _call_llm(user_input: str) -> tuple[str, list, object]:
    """Returns (answer, citations, final_response)."""
    kwargs = dict(
        model=MODEL,
        instructions=INSTRUCTIONS,
        input=_build_input(user_input),
        text={"format": _RESPONSE_SCHEMA},
        store=True,
    )
    if st.session_state.resp_id:
        kwargs["previous_response_id"] = st.session_state.resp_id
    with client.responses.stream(**kwargs) as stream:
        for _ in stream:
            pass
        final = stream.get_final_response()
    data = json.loads(final.output_text)
    return data["answer"], data.get("citations", []), final

def _show_citations(citations: list):
    """Render citations outside the chat bubble so they are never clipped."""
    if citations:
        st.markdown(_citations_html(citations), unsafe_allow_html=True)

# ── render history ────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
    if msg["role"] == "assistant":
        _show_citations(msg.get("citations", []))

# ── chat input
if prompt := st.chat_input("Describe your WiFi issue..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("*WiFiBot is typing…*")
        answer, citations, final = _call_llm(prompt)
        placeholder.empty()
        st.markdown(answer)
    _show_citations(citations)
    st.session_state.resp_id = final.id
    if final.usage:
        st.session_state.tokens_in     += final.usage.input_tokens
        st.session_state.tokens_out    += final.usage.output_tokens
        st.session_state.tokens_cached += final.usage.input_tokens_details.cached_tokens
    st.session_state.messages.append({"role": "assistant", "content": answer, "citations": citations})


_n_user = sum(1 for m in st.session_state.messages if m["role"] == "user")

if _n_user == 0:
    _chips = ["Internet is completely down", "WiFi keeps dropping", "Internet is very slow", "Can't see my WiFi network"]
    st.markdown("<p style='color:#5a6a88;font-size:0.75rem;margin:1rem 0 0.5rem;font-family:JetBrains Mono,monospace;letter-spacing:0.1em;text-transform:uppercase;'>Common issues</p>", unsafe_allow_html=True)
    for chip in _chips:
        if st.button(chip, key=f"chip_{chip}", use_container_width=True):
            st.session_state["_quick_reply"] = chip
            st.rerun()

if "_quick_reply" in st.session_state:
    _qr = st.session_state.pop("_quick_reply")
    st.session_state.messages.append({"role": "user", "content": _qr})
    with st.chat_message("user"):
        st.markdown(_qr)
    with st.chat_message("assistant"):
        _ph = st.empty()
        _ph.markdown("*WiFiBot is typing…*")
        _answer, _citations, _final = _call_llm(_qr)
        _ph.empty()
        st.markdown(_answer)
    _show_citations(_citations)
    st.session_state.resp_id = _final.id
    if _final.usage:
        st.session_state.tokens_in     += _final.usage.input_tokens
        st.session_state.tokens_out    += _final.usage.output_tokens
        st.session_state.tokens_cached += _final.usage.input_tokens_details.cached_tokens
    st.session_state.messages.append({"role": "assistant", "content": _answer, "citations": _citations})
    st.rerun()

# sidebar 
with st.sidebar:
    st.markdown("### Session")
    if st.button("Reset conversation"):
        st.session_state.messages = [{"role": "assistant", "content": GREETING, "citations": []}]
        st.session_state.resp_id = None
        st.session_state.tokens_in     = 0
        st.session_state.tokens_out    = 0
        st.session_state.tokens_cached = 0
        st.rerun()
    st.caption(f"Model: `{MODEL}`")
    st.caption(f"Manual: {len(MANUAL_TEXT):,} chars")
    st.caption(f"Visual refs: {len(MANUAL_IMAGES)} page images per turn")
    if st.session_state.resp_id:
        st.caption(f"Response ID: `{st.session_state.resp_id[:20]}…`")

    st.markdown("---")
    transcript = "\n\n".join(
        f"{'You' if m['role'] == 'user' else 'WiFiBOT'}: {m['content']}"
        for m in st.session_state.messages
    )
    st.download_button("Download transcript", transcript, file_name="wifi_support_chat.txt", mime="text/plain", use_container_width=True)

    st.markdown("---")
    st.markdown("### Tokens")
    col1, col2 = st.columns(2)
    col1.metric("Input",  f"{st.session_state.tokens_in:,}")
    col2.metric("Output", f"{st.session_state.tokens_out:,}")
    cached = st.session_state.tokens_cached
    hit_pct = int(cached / st.session_state.tokens_in * 100) if st.session_state.tokens_in else 0
    st.caption(f"Cached: {cached:,} tokens ({hit_pct}% cache hit)")
