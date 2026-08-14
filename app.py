"""Mg Khant အသံပြောင်းစနစ် Pro - Streamlit Voice Changer App with Modern UI."""

import base64
import streamlit as st
from streamlit_option_menu import option_menu
from pathlib import Path
import json

from voice_engine import (
    FEATURED_VOICES,
    change_tempo, get_usage_count, run_tts_to_file
)

# ---------------------------------------------------------------------------
# Page config & Custom CSS
# ---------------------------------------------------------------------------

ADMIN_PASSWORD = "Khant@6789"

st.set_page_config(
    page_title="Mg Khant အသံပြောင်းစနစ် Pro",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Clean, Polished Mobile & Desktop UI without clipping
def inject_custom_css():
    custom_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pyidaungsu:wght@400;700&family=Inter:wght@300;400;500;600;700&display=swap');

    :root {
        --primary-color: #6366f1;
        --secondary-color: #ec4899;
        --accent-color: #06b6d4;
        --bg-dark: #0f172a;
        --text-light: #f8fafc;
        --text-muted: #94a3b8;
        --border-color: rgba(255, 255, 255, 0.1);
    }

    html, body, [class*="css"] {
        font-family: 'Inter', 'Pyidaungsu', sans-serif;
    }

    /* Main background gradient */
    [data-testid="stAppViewContainer"] {
        background: radial-gradient(circle at top right, #1e1b4b 0%, #0f172a 50%, #020617 100%);
        color: var(--text-light);
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e1b4b 0%, #0f172a 100%);
        border-right: 1px solid var(--border-color);
    }

    /* Buttons styling */
    .stButton > button {
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 12px 24px;
        font-weight: 600;
        font-size: 16px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.5);
    }

    .stDownloadButton > button {
        background: linear-gradient(135deg, #059669 0%, #10b981 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 12px 24px !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3) !important;
    }

    /* Text areas and inputs */
    .stTextArea textarea, .stTextInput input {
        background: linear-gradient(145deg, rgba(30, 41, 59, 0.96), rgba(15, 23, 42, 0.96)) !important;
        color: #ffffff !important;
        caret-color: #f9a8d4 !important;
        border: 1px solid rgba(165, 180, 252, 0.65) !important;
        border-radius: 14px !important;
        padding: 12px !important;
        font-size: 15px !important;
    }

    .stTextArea textarea::placeholder, .stTextInput input::placeholder {
        color: rgba(226, 232, 240, 0.72) !important;
        opacity: 1 !important;
    }

    .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: #f472b6 !important;
        box-shadow: 0 0 0 3px rgba(244, 114, 182, 0.25), 0 0 18px rgba(99, 102, 241, 0.18) !important;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(236, 72, 153, 0.1) 100%);
        padding: 20px;
        border-radius: 16px;
        border: 1px solid var(--border-color);
    }

    /* Telegram banner */
    .telegram-banner {
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
        padding: 16px 20px;
        border-radius: 16px;
        text-align: center;
        margin-bottom: 20px;
        border: 1px solid rgba(56, 189, 248, 0.3);
        box-shadow: 0 4px 15px rgba(2, 132, 199, 0.2);
    }

    .telegram-banner a {
        color: #ffffff;
        text-decoration: none;
        font-weight: 700;
        background: rgba(255, 255, 255, 0.2);
        padding: 6px 16px;
        border-radius: 20px;
        display: inline-block;
        margin-top: 8px;
        transition: background 0.2s;
    }

    .telegram-banner a:hover {
        background: rgba(255, 255, 255, 0.35);
    }

    /* Clean section header without clipping box */
    .clean-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 20px 0 10px 0;
        font-size: 1.05rem;
        font-weight: 600;
        color: var(--text-light);
    }

    .header-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
        color: white;
        border-radius: 50%;
        font-size: 13px;
        font-weight: bold;
        flex-shrink: 0;
    }

    /* Voice cards: compact square choices in a horizontal row */
    div[role="radiogroup"] {
        display: flex !important;
        flex-wrap: nowrap !important;
        gap: 8px !important;
        overflow-x: auto !important;
        padding: 8px 2px 12px 2px !important;
        scrollbar-width: thin;
    }

    div[role="radiogroup"] > label {
        min-width: 104px !important;
        height: 88px !important;
        padding: 10px 8px !important;
        border: 1px solid rgba(129, 140, 248, 0.35) !important;
        border-radius: 14px !important;
        background: linear-gradient(145deg, rgba(71, 85, 180, 0.62), rgba(51, 65, 85, 0.96)) !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
        transition: all 0.2s ease !important;
    }

    div[role="radiogroup"] > label:hover {
        transform: translateY(-2px);
        border-color: #a5b4fc !important;
        box-shadow: 0 6px 16px rgba(99, 102, 241, 0.25);
    }

    div[role="radiogroup"] > label:has(input:checked) {
        border: 2px solid #f472b6 !important;
        background: linear-gradient(145deg, #6366f1, #db2777) !important;
        box-shadow: 0 0 0 3px rgba(236, 72, 153, 0.18), 0 8px 20px rgba(99, 102, 241, 0.35);
    }

    div[role="radiogroup"] > label p {
        color: #ffffff !important;
        font-size: 12px !important;
        font-weight: 700 !important;
        line-height: 1.25 !important;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.45);
    }

    div[role="radiogroup"] > label span {
        color: #ffffff !important;
    }

    [data-testid="stCaptionContainer"] p {
        color: #cbd5e1 !important;
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] .nav-link {
        color: #e2e8f0 !important;
    }

    /* Audio player styling */
    audio {
        width: 100%;
        border-radius: 12px;
        margin: 10px 0;
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

inject_custom_css()

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def b64_audio(path):
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode()
    mime = "audio/wav" if path.suffix.lower() == ".wav" else "audio/mpeg"
    return f"data:{mime};base64,{b64}"

def audio_player(path):
    audio_format = "audio/wav" if path.suffix.lower() == ".wav" else "audio/mp3"
    st.audio(b64_audio(path), format=audio_format)

def render_section(num, title):
    st.markdown(f"""
    <div class="clean-header">
        <div class="header-badge">{num}</div>
        <span>{title}</span>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# TTS Page (Main)
# ---------------------------------------------------------------------------

def tts_page():
    # Telegram Banner
    st.markdown("""
    <div class="telegram-banner">
        <div style="font-size: 16px; font-weight: 600; color: #f0f9ff; margin-bottom: 2px;">
            📢 အားလုံးပဲ မင်္ဂလာပါ — Mg Khant AI မှ ကြိုဆိုပါတယ်
        </div>
        <div style="font-size: 13px; color: #e0f2fe; margin-bottom: 6px;">
            အသံသွင်းရတာ အဆင်မပြေတာရှိရင် Group မှာ လာရောက်မေးမြန်းနိုင်ပါတယ်။
        </div>
        <a href="https://t.me/fruitworld23" target="_blank">🔗 Telegram Group သို့ ဝင်မည်</a>
    </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("### 🎙️ အသံဖန်တီးခြင်း (Text to Speech)")
        
        render_section("1", "စာသားထည့်သွင်းရန် (မြန်မာ / အင်္ဂလိပ်)")
        text = st.text_area(
            "စာသားထည့်ရန်",
            value="",
            height=140,
            label_visibility="collapsed",
            placeholder="ဒီမှာ စာသားရိုက်ထည့်ပါ..."
        )
        
        render_section("2", "အသံအမျိုးအစား ရွေးချယ်ခြင်း")
        # Keep the visible UI names explicit so old cached voice labels cannot reappear.
        voice_options = [
            "Thiha", "Nilar",
            "ကိုဇင်မင်း", "ကိုထက်အောင်", "ကိုရဲမင်း", "ကိုသီဟ",
            "မေသက်", "သဇင်", "နွယ်နွယ်", "အိမ့်ချစ်",
        ]
        selected_voice_str = st.radio(
            "အသံရွေးပါ",
            options=voice_options,
            index=0,
            horizontal=True,
            label_visibility="collapsed"
        )
        selected_idx = voice_options.index(selected_voice_str)
        voice_id, pitch_offset, name, label = FEATURED_VOICES[:10][selected_idx]

        # The key is managed from the dedicated API Key menu page.
        google_api_key = st.session_state.get("saved_google_api_key")
        if voice_id.startswith("google:") and not google_api_key:
            st.info("🔑 Premium အသံ ၈ ခုသုံးရန် Sidebar ရှိ **API Key** menu မှာ Key ထည့်ပြီး သိမ်းပါ။")

        col_speed, col_pitch = st.columns(2)
        with col_speed:
            render_section("3", "အလျင် (Speed)")
            speed_level = st.slider(
                "အသံအလျင်",
                min_value=1,
                max_value=100,
                value=50,
                step=1,
                format="%d",
                label_visibility="collapsed"
            )
            # Map the user-friendly 1–100 control to the engine's 0.5x–2.0x range.
            speed = 0.5 + (speed_level - 1) * 1.5 / 99
            st.caption(f"Speed: {speed_level}/100 • {speed:.2f}x")
        with col_pitch:
            render_section("4", "အသံအမြင့် (Pitch)")
            pitch_value = st.slider(
                "Pitch",
                min_value=-50,
                max_value=50,
                value=0,
                step=5,
                format="%d%%",
                label_visibility="collapsed"
            )

        st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)
        action_col1, action_col2 = st.columns(2)
        with action_col1:
            test_btn = st.button("🔊 အသံစမ်းမည် (Test)", use_container_width=True)
        with action_col2:
            run_btn = st.button("🎧 အသံဖန်တီးမည် (Generate Audio)", use_container_width=True)

    if run_btn or test_btn:
        action_text = text.strip() if text.strip() else "အားလုံးပဲ မင်္ဂလာပါ။ Mg Khant AI မှ ကြိုဆိုပါတယ်။"
        with st.spinner("⏳ အသံဖိုင် ဖန်တီးနေပါသည်... ခဏစောင့်ပါ။"):
                try:
                    # Use the TTS engine's rate control so Streamlit Cloud does
                    # not need the external ffmpeg binary.
                    rate_percent = (speed - 1.0) * 100.0
                    rate_str = f"{rate_percent:+.0f}%"
                    pitch_str = f"{pitch_value:+d}Hz"

                    audio_path, srt_path = run_tts_to_file(
                        action_text,
                        voice_id,
                        pitch_str,
                        rate=rate_str,
                        suffix="custom",
                        api_key=google_api_key if voice_id.startswith("google:") else None,
                    )
                    
                    st.session_state.last_audio = audio_path
                    st.session_state.last_srt = srt_path
                    st.success("✅ အသံဖိုင် အောင်မြင်စွာ ဖန်တီးပြီးပါပြီ။")
                except Exception as e:
                    error_text = str(e)
                    # Google quota exhaustion normally returns HTTP 429. Forget
                    # the session key and show the key field again for a new key.
                    error_lower = error_text.lower()
                    quota_exhausted = (
                        voice_id.startswith("google:")
                        and ("429" in error_text or "quota" in error_lower or "resource_exhausted" in error_lower)
                    )
                    project_denied = (
                        voice_id.startswith("google:")
                        and ("403" in error_text or "permission_denied" in error_lower or "denied access" in error_lower)
                    )
                    if quota_exhausted:
                        st.session_state.pop("saved_google_api_key", None)
                        st.session_state["reset_google_key_input"] = True
                        st.warning("⚠️ ဒီ API Key ရဲ့ Google quota/Limit ပြည့်သွားပါပြီ။ Key အသစ်ထည့်ရန် Key box ပြန်ပေါ်လာပါမည်။")
                        st.rerun()
                    if project_denied:
                        st.session_state.pop("saved_google_api_key", None)
                        st.session_state["reset_google_key_input"] = True
                        st.error("❌ ဒီ API Key ရဲ့ Google Project ကို Access Denied လုပ်ထားပါသည်။ Project အသစ်ဖန်တီးပြီး API Key အသစ်ယူပါ။ Key box ပြန်ပေါ်လာပါမည်။")
                        st.rerun()
                    st.error(f"❌ အမှားအယွင်း ဖြစ်ပေါ်သည်: {error_text}")

    if "last_audio" in st.session_state:
        with st.container(border=True):
            st.markdown("### 🎧 ရလဒ်နှင့် အသံထုတ်ယူမှု")
            audio_player(st.session_state.last_audio)
            
            st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True)
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                st.download_button(
                    "⬇️ အသံဖိုင် ဒေါင်းလုဒ်",
                    data=st.session_state.last_audio.read_bytes(),
                    file_name=f"mgkhant_voice{st.session_state.last_audio.suffix}",
                    mime="audio/wav" if st.session_state.last_audio.suffix.lower() == ".wav" else "audio/mpeg",
                    use_container_width=True
                )
            with dl_col2:
                if "last_srt" in st.session_state and st.session_state.last_srt.exists():
                    st.download_button(
                        "📄 SRT စာတန်းထိုး",
                        data=st.session_state.last_srt.read_bytes(),
                        file_name="mgkhant_subtitle.srt",
                        mime="application/x-subrip",
                        use_container_width=True
                    )

# ---------------------------------------------------------------------------
# API Key Page
# ---------------------------------------------------------------------------

def api_key_page():
    """Collect and save a Google AI Studio key for the current session only."""
    if st.session_state.pop("reset_google_key_input", False):
        st.session_state["google_api_key_input"] = ""

    with st.container(border=True):
        st.markdown("### 🔑 Google AI Studio API Key")
        st.markdown(
            "Premium Google အသံ ၈ ခုသုံးရန် ကိုယ်ပိုင် API Key ထည့်ပါ။ "
            "Key ကို App ထဲမှာ file/GitHub သို့မဟုတ် Secrets ထဲ မသိမ်းဘဲ ဒီ session အတွင်းသာ အသုံးပြုပါမည်။"
        )
        st.markdown("[🔗 Google AI Studio မှ Key ယူရန် ဒီမှာနှိပ်ပါ](https://aistudio.google.com/app/apikey)")
        st.caption("Google AI Studio → Create API key → Project ရွေးပါ → Key ကို Copy လုပ်ပါ။")

        saved_key = st.session_state.get("saved_google_api_key")
        if saved_key:
            st.success("✅ API Key သိမ်းပြီးပါပြီ။ Premium အသံ ၈ ခုအတွက် အသုံးပြုနေပါသည်။")
            if st.button("🔄 Key ပြန်ပြောင်းမည်", key="change_google_key", use_container_width=True):
                st.session_state.pop("saved_google_api_key", None)
                st.session_state["reset_google_key_input"] = True
                st.rerun()
        else:
            entered_key = st.text_input(
                "Google AI Studio API Key ထည့်ရန်",
                type="password",
                placeholder="AIza... သင်၏ API Key ကို ဒီမှာထည့်ပါ",
                key="google_api_key_input",
                help="Key ကို မည်သူ့ကိုမျှ မမျှဝေပါနှင့်။",
            ).strip()
            if st.button("💾 Key သိမ်းမည်", key="save_google_key", use_container_width=True):
                if entered_key:
                    st.session_state["saved_google_api_key"] = entered_key
                    st.rerun()
                st.warning("သိမ်းရန် Google API Key အရင်ထည့်ပါ။")

        st.info("Google quota Limit ပြည့်ခြင်း သို့မဟုတ် Project Access Denied ဖြစ်ပါက Key ထည့်သည့်နေရာ ပြန်ပေါ်လာပြီး Key အသစ် ထည့်နိုင်ပါမည်။")

# ---------------------------------------------------------------------------
# Admin Page
# ---------------------------------------------------------------------------

def admin_page():
    with st.container(border=True):
        st.markdown("### 🔐 Admin Dashboard")
        pwd = st.text_input("Admin Password ထည့်ပါ", type="password", placeholder="Password ရိုက်ထည့်ပါ...")
        
        if pwd == ADMIN_PASSWORD:
            st.success("✅ Admin အဖြစ် အောင်မြင်စွာ ဝင်ရောက်ပြီးပါပြီ။")
            st.markdown("---")
            
            count = get_usage_count()
            col1, col2 = st.columns(2)
            with col1:
                st.metric("စုစုပေါင်း အသံထုတ်ယူမှု ကြိမ်ရေ", f"{count} ကြိမ်")
            with col2:
                if st.button("🔄 Usage Count ကို 0 သို့ ပြန်ထားမည်", use_container_width=True):
                    with open("usage_stats.json", "w") as f:
                        json.dump({"count": 0}, f)
                    st.rerun()
        elif pwd:
            st.error("❌ Password မှားယွင်းနေပါသည်။")

# ---------------------------------------------------------------------------
# Main Router
# ---------------------------------------------------------------------------

def main():
    with st.sidebar:
        st.markdown("<h2 style='text-align: center; color: #818cf8;'>🎙️ Mg Khant Pro</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 13px;'>Advanced Voice Changer</p>", unsafe_allow_html=True)
        st.markdown("---")
        
        selected = option_menu(
            menu_title=None,
            options=["🗣️ အသံထုတ်ရန်", "🔑 API Key", "🔐 Admin"],
            icons=["mic", "key", "lock"],
            default_index=0,
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "#818cf8", "font-size": "16px"},
                "nav-link": {
                    "font-size": "15px",
                    "text-align": "left",
                    "margin": "4px 0",
                    "border-radius": "10px",
                    "--hover-color": "rgba(99, 102, 241, 0.15)",
                },
                "nav-link-selected": {"background": "linear-gradient(135deg, #6366f1 0%, #ec4899 100%)", "color": "white"},
            }
        )
        st.markdown("---")
        st.markdown("<div style='text-align: center; color: #64748b; font-size: 12px;'>© 2026 Mg Khant Voice System<br>All Rights Reserved.</div>", unsafe_allow_html=True)

    if selected == "🗣️ အသံထုတ်ရန်":
        tts_page()
    elif selected == "🔑 API Key":
        api_key_page()
    else:
        admin_page()

if __name__ == "__main__":
    main()