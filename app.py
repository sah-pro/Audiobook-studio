import streamlit as st
import pdfplumber
import os
import json
import bcrypt
import tempfile
import base64
from pathlib import Path

# ── optional OCR imports ──────────────────────────────────────────────────────
try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# ── TTS import ────────────────────────────────────────────────────────────────
try:
    from gtts import gTTS
    TTS_BACKEND = "gtts"
except ImportError:
    TTS_BACKEND = None

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PDF to Audiobook Studio",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Lato:wght@300;400;700&display=swap');

html, body, [class*="css"] { font-family: 'Lato', sans-serif; }
h1, h2, h3, .stTitle { font-family: 'Playfair Display', serif !important; }

:root {
    --wine:   #8b1e3f;
    --wine-d: #6d1532;
    --cream:  #fff5e6;
    --brown:  #2e1b0f;
}

/* sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(160deg, #8b1e3f 0%, #6d1532 100%) !important;
}
[data-testid="stSidebar"] * { color: #fff5e6 !important; }
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,245,230,0.15) !important;
    color: #fff5e6 !important;
    border: 1px solid rgba(255,245,230,0.3) !important;
    border-radius: 8px !important;
    width: 100% !important;
    font-family: 'Lato', sans-serif !important;
    font-weight: 700 !important;
    letter-spacing: 0.05em !important;
    transition: all 0.2s !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,245,230,0.28) !important;
    transform: translateX(3px);
}

/* main buttons */
.stButton > button {
    background: #8b1e3f !important;
    color: #fff5e6 !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'Lato', sans-serif !important;
    font-weight: 700 !important;
    padding: 0.5rem 1.5rem !important;
    transition: background 0.2s, transform 0.15s !important;
}
.stButton > button:hover {
    background: #6d1532 !important;
    transform: translateY(-1px);
}

/* cards */
.card {
    background: #fff5e6;
    border: 1px solid rgba(139,30,63,0.15);
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1rem;
    box-shadow: 0 2px 12px rgba(139,30,63,0.07);
}

/* status badge */
.badge {
    display: inline-block;
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.06em;
}
.badge-ok  { background:#d4edda; color:#155724; }
.badge-err { background:#f8d7da; color:#721c24; }
.badge-info{ background:#cce5ff; color:#004085; }

/* audio player */
audio { width: 100%; border-radius: 8px; }

/* login card */
.login-wrap {
    max-width: 440px;
    margin: 3rem auto;
    background: #fff5e6;
    border-radius: 18px;
    padding: 2.5rem 2rem;
    box-shadow: 0 8px 32px rgba(139,30,63,0.13);
    border: 1px solid rgba(139,30,63,0.1);
}
.login-title {
    font-family: 'Playfair Display', serif;
    font-size: 2rem;
    color: #8b1e3f;
    text-align: center;
    margin-bottom: 0.25rem;
}
.login-sub {
    text-align: center;
    color: #888;
    font-size: 0.9rem;
    margin-bottom: 1.8rem;
}
</style>
""", unsafe_allow_html=True)

# ── user database helpers ─────────────────────────────────────────────────────
USER_DB = "users.json"

def load_users():
    if not os.path.exists(USER_DB):
        return {}
    with open(USER_DB, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USER_DB, "w") as f:
        json.dump(users, f)

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

# ── PDF helpers ───────────────────────────────────────────────────────────────
def extract_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes. Falls back to OCR if needed."""
    text = ""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except Exception:
        pass

    if not text.strip() and OCR_AVAILABLE:
        try:
            images = convert_from_path(tmp_path)
            for img in images:
                text += pytesseract.image_to_string(img) + "\n"
        except Exception:
            pass

    os.unlink(tmp_path)
    return text.strip()

# ── TTS helper ────────────────────────────────────────────────────────────────
GTTS_VOICES = {
    "English (US) – Female":  ("en", "com"),
    "English (UK) – Female":  ("en", "co.uk"),
    "English (AU) – Female":  ("en", "com.au"),
    "Hindi – Female":         ("hi", "co.in"),
    "French – Female":        ("fr", "fr"),
    "Spanish – Female":       ("es", "es"),
    "German – Female":        ("de", "de"),
    "Japanese – Female":      ("ja", "co.jp"),
}

def text_to_mp3(text: str, lang: str, tld: str, slow: bool = False) -> bytes:
    tts = gTTS(text=text, lang=lang, tld=tld, slow=slow)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tts.save(tmp.name)
        tmp_path = tmp.name
    with open(tmp_path, "rb") as f:
        data = f.read()
    os.unlink(tmp_path)
    return data

def audio_b64_tag(mp3_bytes: bytes) -> str:
    b64 = base64.b64encode(mp3_bytes).decode()
    return f'<audio controls><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'

# ── session state defaults ────────────────────────────────────────────────────
for key, val in {
    "logged_in": False,
    "username": "",
    "page": "convert",
    "converted_files": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ══════════════════════════════════════════════════════════════════════════════
# LOGIN / REGISTER PAGE
# ══════════════════════════════════════════════════════════════════════════════
def show_auth():
    st.markdown('<div class="login-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="login-title">📖 Audiobook Studio</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-sub">Convert any PDF into an audiobook, instantly.</div>', unsafe_allow_html=True)

    tab_login, tab_reg = st.tabs(["🔓 Login", "🆕 Register"])

    with tab_login:
        u = st.text_input("Username", key="li_user", placeholder="your username")
        p = st.text_input("Password", type="password", key="li_pass", placeholder="••••••••")
        if st.button("Login", key="btn_login"):
            users = load_users()
            if u in users and check_password(p, users[u]):
                st.session_state.logged_in = True
                st.session_state.username = u
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with tab_reg:
        u2 = st.text_input("Choose a username", key="reg_user", placeholder="new username")
        p2 = st.text_input("Choose a password", type="password", key="reg_pass", placeholder="••••••••")
        p3 = st.text_input("Confirm password",  type="password", key="reg_conf", placeholder="••••••••")
        if st.button("Create Account", key="btn_reg"):
            if not u2 or not p2:
                st.error("Username and password are required.")
            elif p2 != p3:
                st.error("Passwords do not match.")
            else:
                users = load_users()
                if u2 in users:
                    st.error("Username already taken.")
                else:
                    users[u2] = hash_password(p2)
                    save_users(users)
                    st.success("Account created! Switch to the Login tab.")

    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
def show_sidebar():
    with st.sidebar:
        st.markdown("## 🎧 Studio")
        st.markdown(f"**Logged in as:** {st.session_state.username}")
        st.markdown("---")
        if st.button("🎙 Convert PDFs"):
            st.session_state.page = "convert"
        if st.button("📁 My Audiobooks"):
            st.session_state.page = "library"
        if st.button("⚙️ Settings"):
            st.session_state.page = "settings"
        st.markdown("---")
        if st.button("🚪 Logout"):
            for k in ["logged_in", "username", "page", "converted_files"]:
                del st.session_state[k]
            st.rerun()

        st.markdown("---")
        st.markdown("**TTS Engine**")
        if TTS_BACKEND == "gtts":
            st.markdown('<span class="badge badge-ok">gTTS ✓ Online</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge badge-err">No TTS engine</span>', unsafe_allow_html=True)
            st.caption("Run: `pip install gtts`")

        st.markdown("**OCR**")
        if OCR_AVAILABLE:
            st.markdown('<span class="badge badge-ok">pytesseract ✓</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge badge-info">Optional – not installed</span>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# CONVERT PAGE
# ══════════════════════════════════════════════════════════════════════════════
def show_convert():
    st.title("📖 PDF to Audiobook")
    st.caption("Upload one or more PDFs, choose your voice, and convert.")

    # ── Upload ────────────────────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("1 · Upload PDFs")
    uploaded = st.file_uploader(
        "Drag & drop PDF files here",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if uploaded:
        st.success(f"{len(uploaded)} file(s) selected: {', '.join(f.name for f in uploaded)}")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Voice settings ────────────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("2 · Voice Settings")
    col1, col2 = st.columns(2)
    with col1:
        voice_name = st.selectbox("Voice / Language", list(GTTS_VOICES.keys()))
    with col2:
        slow_speech = st.checkbox("Slow speech (easier to follow)", value=False)

    preview_chars = st.slider("Preview length (characters)", 100, 1000, 400, step=50)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Actions ───────────────────────────────────────────────────────────────
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("3 · Convert")

    c1, c2 = st.columns(2)
    preview_clicked  = c1.button("▶ Preview first PDF", disabled=not uploaded)
    convert_clicked  = c2.button("🎧 Convert all PDFs", disabled=not uploaded)

    if TTS_BACKEND is None:
        st.error("⚠️ gTTS is not installed. Run: `pip install gtts` then restart.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    lang, tld = GTTS_VOICES[voice_name]

    # -- preview
    if preview_clicked and uploaded:
        with st.spinner("Extracting text…"):
            text = extract_text(uploaded[0].read())
        if not text:
            st.warning("No readable text found in this PDF.")
        else:
            snippet = text[:preview_chars]
            with st.spinner("Generating audio preview…"):
                mp3 = text_to_mp3(snippet, lang, tld, slow_speech)
            st.markdown("**Preview:**")
            st.markdown(audio_b64_tag(mp3), unsafe_allow_html=True)
            with st.expander("Show extracted text snippet"):
                st.text(snippet)

    # -- full convert
    if convert_clicked and uploaded:
        progress = st.progress(0, text="Starting…")
        results = []
        for i, pdf_file in enumerate(uploaded):
            progress.progress((i) / len(uploaded), text=f"Extracting text from {pdf_file.name}…")
            text = extract_text(pdf_file.read())
            if not text:
                st.warning(f"⚠️ No text found in {pdf_file.name} — skipped.")
                continue
            progress.progress((i + 0.5) / len(uploaded), text=f"Converting {pdf_file.name} to audio…")
            mp3 = text_to_mp3(text, lang, tld, slow_speech)
            stem = Path(pdf_file.name).stem
            results.append({"name": stem, "mp3": mp3, "chars": len(text)})

        progress.progress(1.0, text="Done!")

        if results:
            st.session_state.converted_files = results
            st.success(f"✅ Converted {len(results)} audiobook(s)!")
            for r in results:
                st.markdown(f"**{r['name']}** · {r['chars']:,} characters")
                st.markdown(audio_b64_tag(r["mp3"]), unsafe_allow_html=True)
                st.download_button(
                    f"⬇ Download {r['name']}.mp3",
                    data=r["mp3"],
                    file_name=f"{r['name']}.mp3",
                    mime="audio/mp3",
                    key=f"dl_{r['name']}",
                )
                st.markdown("---")

    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# LIBRARY PAGE
# ══════════════════════════════════════════════════════════════════════════════
def show_library():
    st.title("📁 My Audiobooks")
    files = st.session_state.converted_files
    if not files:
        st.info("No audiobooks yet — go to **Convert PDFs** to create your first one.")
        return
    for r in files:
        with st.expander(f"🎧 {r['name']}  ({r['chars']:,} chars)"):
            st.markdown(audio_b64_tag(r["mp3"]), unsafe_allow_html=True)
            st.download_button(
                f"⬇ Download {r['name']}.mp3",
                data=r["mp3"],
                file_name=f"{r['name']}.mp3",
                mime="audio/mp3",
                key=f"lib_{r['name']}",
            )

# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS PAGE
# ══════════════════════════════════════════════════════════════════════════════
def show_settings():
    st.title("⚙️ Settings")

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Change Password")
    old = st.text_input("Current password", type="password", key="s_old")
    new = st.text_input("New password",     type="password", key="s_new")
    cnf = st.text_input("Confirm new",      type="password", key="s_cnf")
    if st.button("Update Password"):
        users = load_users()
        uname = st.session_state.username
        if not check_password(old, users[uname]):
            st.error("Current password is incorrect.")
        elif new != cnf:
            st.error("New passwords do not match.")
        elif len(new) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            users[uname] = hash_password(new)
            save_users(users)
            st.success("Password updated!")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("About")
    st.markdown("""
| Component | Details |
|---|---|
| TTS Engine | gTTS (Google Text-to-Speech, online) |
| PDF Extraction | pdfplumber + optional pytesseract OCR |
| Voices | 8 languages / accents |
| Max file size | Streamlit default 200 MB |
    """)
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    show_auth()
else:
    show_sidebar()
    page = st.session_state.page
    if page == "convert":
        show_convert()
    elif page == "library":
        show_library()
    elif page == "settings":
        show_settings()
