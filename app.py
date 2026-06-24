import os
import json
from html import escape
from pathlib import Path

import streamlit as st
import yaml
from streamlit_js_eval import streamlit_js_eval

os.environ["HAYSTACK_TELEMETRY_ENABLED"] = "False"

from query import get_local_gemini_key, get_response


ROOT = Path(__file__).resolve().parent
with (ROOT / "config.yaml").open("r", encoding="utf-8") as file:
    config = yaml.safe_load(file)

st.set_page_config(page_title="Character Studio · Storyline", page_icon="✦", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap');
:root { --ink:#272522; --muted:#77716b; --paper:#f4eee6; --card:rgba(255,253,249,.78); --line:rgba(73,58,48,.12); --amber:#d9954f; }
.stApp { background:radial-gradient(ellipse at 78% 12%,#e4d2c5 0,transparent 39%),radial-gradient(ellipse at 8% 86%,#e6d4c7 0,transparent 40%),#f2eae2; color:var(--ink); font-family:'DM Sans',sans-serif; }
[data-testid="stHeader"] {background:transparent} [data-testid="stToolbar"] {right:1rem}
[data-testid="stSidebar"] {background:rgba(255,253,249,.66); border-right:1px solid var(--line)}
[data-testid="stSidebar"] > div:first-child {padding-top:1.5rem}
h1,h2,h3 {font-family:'Playfair Display',serif!important;color:var(--ink)!important;letter-spacing:-.025em}
p, label, .stMarkdown {color:var(--ink)}
.brand {font-size:1.12rem;font-weight:700;letter-spacing:-.03em;padding:.4rem 0 1.2rem}
.brand-mark {display:inline-grid;place-items:center;width:32px;height:32px;background:#292724;color:white;border-radius:50%;margin-right:.55rem}
.eyebrow {text-transform:uppercase;letter-spacing:.14em;font-size:.68rem;font-weight:700;color:#9a7256;margin-bottom:.5rem}
.hero-panel,.info-panel,.welcome-card {background:var(--card);border:1px solid rgba(255,255,255,.8);border-radius:22px;box-shadow:0 12px 40px rgba(83,61,45,.07);backdrop-filter:blur(18px)}
.hero-panel {padding:1.05rem 1.1rem;margin:.65rem 0 1rem}
.hero-icon {font-size:2.3rem;line-height:1.3}.hero-name {font-family:'Playfair Display',serif;font-size:1.55rem;font-weight:700;margin:.3rem 0}
.tag {display:inline-block;border:1px solid var(--line);border-radius:99px;padding:.25rem .65rem;font-size:.74rem;color:#75563f;margin:.35rem .3rem .2rem 0}
.tag-hot {background:#f1d9bb;border-color:#f1d9bb;color:#75491f}
.topline {display:flex;justify-content:space-between;align-items:center;padding:.8rem 1.1rem;background:rgba(255,253,249,.72);border:1px solid rgba(255,255,255,.85);border-radius:18px;margin:.25rem 0 1.3rem}
.top-title {font-weight:600;font-size:1rem}.top-meta {font-size:.8rem;color:var(--muted)}
.message-user {background:#fffdfa;border:1px solid rgba(255,255,255,.9);border-radius:18px 18px 4px 18px;padding:.85rem 1rem;max-width:85%;margin:.6rem 0 .8rem auto;box-shadow:0 5px 20px rgba(70,51,39,.05)}
.source-card {background:rgba(255,253,249,.75);border:1px solid var(--line);border-radius:14px;padding:.8rem;margin:.45rem 0;font-size:.85rem}
.source-title {font-size:.76rem;font-weight:700;color:#9a6738;margin-bottom:.35rem}
.welcome-card {padding:1.2rem 1.3rem;margin:1.5rem 0}.welcome-title {font-family:'Playfair Display',serif;font-size:1.45rem;margin-bottom:.3rem}
.stButton > button {border-radius:13px;border:1px solid var(--line);background:rgba(255,253,249,.72);color:var(--ink);font-weight:500;min-height:2.7rem;transition:all .18s ease}
.stButton > button:hover {border-color:#d9954f;color:#8b5728;transform:translateY(-1px)}
button[kind="primary"] {background:#d9954f!important;border-color:#d9954f!important;color:white!important}
.stChatInput textarea {border-radius:16px!important;background:#fffdfa!important}
.stBottom {z-index:1000}
.stBottom > div:first-child {background:linear-gradient(180deg,rgba(242,234,226,0),rgba(242,234,226,.96) 30%)!important}
[data-testid="stChatInput"] > div:first-child {background:rgba(255,253,249,.82)!important;border:1px solid rgba(255,255,255,.9);border-radius:18px;box-shadow:0 8px 28px rgba(70,51,39,.1)}
[data-baseweb="select"] > div {background:rgba(255,253,249,.92)!important;color:var(--ink)!important;border-color:var(--line)!important}
.stTextInput input {background:rgba(255,253,249,.92)!important;color:var(--ink)!important}
div[data-testid="stChatMessage"] {background:rgba(255,253,249,.68);border:1px solid rgba(255,255,255,.8);border-radius:18px;padding:.6rem .8rem;margin:.7rem 0;box-shadow:0 5px 20px rgba(70,51,39,.04)}
div[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {line-height:1.7}
hr {border-color:var(--line)!important}.stCaption {color:var(--muted)!important}
</style>
""", unsafe_allow_html=True)

heroes = config["LIST_OF_SUPERHEROES"]
metadata = config.get("SUPERHERO_METADATA", {})
synonyms = config.get("SUPERHERO_SYNONYMS", {})
movies = config.get("MOVIES_LIST_OF_SUPERHEROES", {})
models = config.get("GEMINI_AVAILABLE_MODELS", ["gemini-3.8-flash"])
LOCAL_STORAGE_KEY = "storyline_local_data_v1"


def read_browser_state():
    raw = streamlit_js_eval(
        js_expressions=f"window.localStorage.getItem({json.dumps(LOCAL_STORAGE_KEY)}) || '__EMPTY_LOCAL_STORAGE__'",
        want_output=True,
        key="storyline_local_storage_load",
        default=None,
    )
    # Streamlit components return None until their browser-side code reports
    # its first value. Keep initialization pending instead of mistaking that
    # handshake for an empty localStorage value.
    if raw is None:
        return None
    if raw == "__EMPTY_LOCAL_STORAGE__":
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (TypeError, json.JSONDecodeError):
        return {}


def write_browser_state(state):
    serialized_state = json.dumps(state, ensure_ascii=False)
    js_expression = f"(window.localStorage.setItem({json.dumps(LOCAL_STORAGE_KEY)}, {json.dumps(serialized_state)}), 'saved')"
    write_id = st.session_state.get("local_storage_write_id", 0) + 1
    st.session_state.local_storage_write_id = write_id
    streamlit_js_eval(
        js_expressions=js_expression,
        want_output=False,
        key=f"storyline_local_storage_write_{write_id}",
    )


def persist_chat_history():
    write_browser_state({
        "chat_history": st.session_state.chat_history,
        "profile_settings": st.session_state.profile_settings,
    })

if "chat_history" not in st.session_state:
    browser_state = read_browser_state()
    st.session_state.browser_storage_ready = browser_state is not None
    st.session_state.chat_history = (browser_state or {}).get("chat_history", {})
    st.session_state.profile_settings = (browser_state or {}).get("profile_settings", {})
else:
    browser_state = read_browser_state()
    if browser_state is not None and not st.session_state.get("browser_storage_ready", False):
        st.session_state.browser_storage_ready = True
        st.session_state.chat_history = browser_state.get("chat_history", {})
        st.session_state.profile_settings = browser_state.get("profile_settings", {})
if "selected_hero" not in st.session_state:
    st.session_state.selected_hero = heroes[0]
if "profile_name" not in st.session_state:
    st.session_state.profile_name = st.session_state.profile_settings.get("name", "")
if "gemini_model" not in st.session_state:
    default_model = config.get("GEMINI_DEFAULT_MODEL", "gemini-3.8-flash")
    st.session_state.gemini_model = st.session_state.profile_settings.get("model", default_model)
if st.session_state.gemini_model not in models:
    st.session_state.gemini_model = models[0]

with st.sidebar:
    st.markdown('<div class="brand"><span class="brand-mark">✦</span>STORYLINE <span style="font-weight:400;color:#9a7256">/ AI</span></div>', unsafe_allow_html=True)
    page = st.radio("Workspace", ["Chat", "Settings"], horizontal=True, label_visibility="collapsed")
    if page == "Settings":
        st.markdown("### Settings")
        st.caption("Profile, Gemini engine and credentials")
    else:
        st.markdown('<div class="eyebrow">Your character</div>', unsafe_allow_html=True)
        universe = st.radio("Universe", ["All", "Marvel", "DC"], horizontal=True, label_visibility="collapsed")
        filtered = [h for h in heroes if universe == "All" or metadata.get(h, {}).get("universe", "Marvel") == universe]
        if st.session_state.selected_hero not in filtered:
            st.session_state.selected_hero = filtered[0]
        selected = st.selectbox("Choose a character", filtered, format_func=lambda h: f"{metadata.get(h, {}).get('emoji', '✦')}  {h}", index=filtered.index(st.session_state.selected_hero))
        st.session_state.selected_hero = selected
        info = metadata.get(selected, {})
        identity = (synonyms.get(selected) or [selected])[0]
        st.markdown(f'''<div class="hero-panel"><div class="hero-icon">{escape(info.get('emoji','✦'))}</div><div class="hero-name">{escape(selected)}</div><span class="tag tag-hot">{escape(info.get('universe','Marvel'))}</span><span class="tag">{escape(identity)}</span><p style="color:#77716b;font-style:italic;margin:.6rem 0 0">“{escape(info.get('tagline',''))}”</p></div>''', unsafe_allow_html=True)
        st.caption(f"{len(movies.get(selected, []))} indexed script sources · Haystack + Qdrant")
        with st.expander("Character library"):
            for movie in movies.get(selected, []):
                st.markdown(f"· {movie.replace('.pdf','').replace('.txt','')}")
        if st.button("＋  New conversation", type="primary", use_container_width=True):
            st.session_state.chat_history[selected] = []
            persist_chat_history()
            st.rerun()
        if st.button("Clear this conversation", use_container_width=True):
            st.session_state.chat_history[selected] = []
            persist_chat_history()
            st.rerun()

if page == "Settings":
    st.title("Settings")
    st.caption("Your profile and engine preferences are saved in this browser. The Gemini key is kept in the local, git-ignored .env file.")
    with st.form("storyline_settings_form"):
        st.subheader("Profile")
        profile_name_input = st.text_input("Display name", value=st.session_state.profile_name, placeholder="How should characters address you?")
        st.subheader("Engine")
        model_input = st.selectbox("Gemini model", models, index=models.index(st.session_state.gemini_model))
        st.subheader("Gemini API key")
        key_input = st.text_input("API key", value=get_local_gemini_key() or "", type="password", placeholder="Paste your Gemini API key", help="Saved only to this local project's .env file; never stored in browser local storage.")
        save_settings = st.form_submit_button("Save settings", type="primary", use_container_width=True, disabled=not st.session_state.browser_storage_ready)
    if save_settings:
        if not key_input.strip():
            st.error("Enter your Gemini API key before saving settings.")
        else:
            env_file = ROOT / ".env"
            existing_lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
            preserved_lines = [line for line in existing_lines if not line.startswith(("GEMINI_API_KEY=", "GOOGLE_API_KEY="))]
            preserved_lines.append(f"GEMINI_API_KEY={key_input.strip()}")
            env_file.write_text("\n".join(preserved_lines) + "\n", encoding="utf-8")
            env_file.chmod(0o600)
            os.environ["GEMINI_API_KEY"] = key_input.strip()
            st.session_state.profile_name = profile_name_input.strip()
            st.session_state.gemini_model = model_input
            st.session_state.profile_settings = {"name": st.session_state.profile_name, "model": model_input}
            write_browser_state({
                "chat_history": st.session_state.chat_history,
                "profile_settings": st.session_state.profile_settings,
            })
            st.success("Settings saved. Gemini is ready for your next character conversation.")
    st.info("Chat history and profile preferences stay in this browser's local storage. The API key stays in the local .env file and is sent to Google's Gemini API only when you chat.")
else:
    if not st.session_state.browser_storage_ready:
        st.info("Loading your conversations from this browser…")
    else:
        selected = st.session_state.selected_hero
        info = metadata.get(selected, {})
        identity = (synonyms.get(selected) or [selected])[0]
        model = st.session_state.gemini_model
        api_key = get_local_gemini_key()
        history = st.session_state.chat_history.setdefault(selected, [])
        emoji = info.get("emoji", "✦")
        st.markdown(f'''<div class="topline"><div><div class="eyebrow" style="margin:0 0 .2rem">Private character session</div><div class="top-title">A conversation with {escape(selected)}</div></div><div class="top-meta">{escape(model)} · Grounded in indexed scripts</div></div>''', unsafe_allow_html=True)

        left, right = st.columns([0.72, 0.28], gap="large")
        with left:
            if not history:
                st.markdown(f'''<div class="welcome-card"><div class="eyebrow">Character studio</div><div class="welcome-title">Step into {escape(selected)}’s world.</div><div style="color:#77716b">Ask anything. Replies draw on retrieved script moments and stay true to the character’s voice, values, and point of view.</div></div>''', unsafe_allow_html=True)
                st.markdown("<div class='eyebrow'>Start with a question</div>", unsafe_allow_html=True)
                suggestions = info.get("sample_questions", [f"What matters most to you, {selected}?", "What experience changed you most?", "What would you do in a difficult situation?"])
                chosen_question = None
                for row in range(0, min(len(suggestions), 4), 2):
                    cols = st.columns(2)
                    for offset, col in enumerate(cols):
                        idx = row + offset
                        if idx < len(suggestions) and col.button(suggestions[idx], key=f"suggest_{selected}_{idx}", use_container_width=True):
                            chosen_question = suggestions[idx]
            else:
                chosen_question = None
            for message in history:
                with st.chat_message(message["role"], avatar="👤" if message["role"] == "user" else emoji):
                    st.markdown(message["content"])
                    if message.get("docs"):
                        with st.expander(f"✦  {len(message['docs'])} script excerpts retrieved", expanded=False):
                            for doc in message["docs"]:
                                st.markdown(f'''<div class="source-card"><div class="source-title">{escape(doc.get('movie','Script reference'))}</div><div>{escape(doc.get('content',''))}</div></div>''', unsafe_allow_html=True)
        with right:
            st.markdown('<div class="eyebrow">Character dossier</div>', unsafe_allow_html=True)
            st.markdown(f'''<div class="info-panel" style="padding:1.05rem"><div style="font-size:.78rem;color:#9a7256;font-weight:700">KNOWN AS</div><div style="font-size:1.05rem;font-weight:600;margin:.2rem 0 .9rem">{escape(identity)}</div><div style="font-size:.78rem;color:#9a7256;font-weight:700">VOICE GUIDE</div><p style="font-size:.88rem;color:#77716b;margin:.3rem 0 1rem">{escape(info.get('tagline','Character-led, script-grounded conversation.'))}</p><div style="font-size:.78rem;color:#9a7256;font-weight:700">SOURCE MATERIAL</div><p style="font-size:.88rem;color:#77716b;margin:.3rem 0 0">{len(movies.get(selected, []))} indexed film scripts for {escape(selected)}.</p></div>''', unsafe_allow_html=True)
            st.markdown("<div style='height:1rem'></div><div class='eyebrow'>How replies work</div>", unsafe_allow_html=True)
            st.markdown('<div class="info-panel" style="padding:1rem;font-size:.86rem;color:#77716b;line-height:1.65">Your message searches this character’s script index. Retrieved scenes give the reply evidence, while character values and mannerisms shape how it is expressed.</div>', unsafe_allow_html=True)

        prompt = st.chat_input(f"Ask {selected} something…")
        prompt = chosen_question or prompt

        if prompt:
            previous_turns = history[:-1]
            history.append({"role": "user", "content": prompt})
            persist_chat_history()
            with left:
                with st.chat_message("user", avatar="👤"):
                    st.markdown(prompt)
                with st.chat_message("assistant", avatar=emoji):
                    with st.spinner(f"{selected} is thinking…"):
                        try:
                            context = f"User display name: {st.session_state.profile_name or 'not provided'}\n" + ("\n".join(f"{turn['role']}: {turn['content']}" for turn in previous_turns[-8:]) or "No earlier turns.")
                            answer, documents = get_response(question=prompt, superhero=selected, api_key=api_key or None, model_name=model, top_k=3, conversation_context=context)
                            st.markdown(answer)
                            refs = [{"movie": doc.meta.get("movie", "Script reference") if getattr(doc, "meta", None) else "Script reference", "content": getattr(doc, "content", str(doc))} for doc in (documents or [])]
                            if refs:
                                with st.expander(f"✦  {len(refs)} script excerpts retrieved", expanded=False):
                                    for doc in refs:
                                        st.markdown(f'''<div class="source-card"><div class="source-title">{escape(doc['movie'])}</div><div>{escape(doc['content'])}</div></div>''', unsafe_allow_html=True)
                            history.append({"role": "assistant", "content": answer, "docs": refs})
                            persist_chat_history()
                        except Exception as error:
                            error_message = str(error).lower()
                            if "503" in error_message or "high demand" in error_message:
                                st.error("Gemini is temporarily busy. Your message is saved; please try again shortly.")
                            else:
                                st.error("Couldn’t reach the character archive. Check the Gemini API key and local script index, then try again.")
                            history.append({"role": "assistant", "content": "I’m having trouble reaching the character archive. Please check the Gemini API key and that the local Qdrant index has been created.", "docs": []})
                            persist_chat_history()
