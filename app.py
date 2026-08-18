"""Mg Khant အသံပြောင်းစနစ် Pro - Streamlit Voice Changer App with Modern UI."""

import base64
import streamlit as st
from pathlib import Path
import json
import re
import requests

from voice_engine import (
    FEATURED_VOICES,
    change_tempo, get_usage_count, run_tts_to_file
)

# ---------------------------------------------------------------------------
# Page config & Custom CSS
# ---------------------------------------------------------------------------

ADMIN_PASSWORD = "Khant@6789"
TELEGRAM_GROUP = "@fruitworld23"


def _telegram_secret(name):
    value = None
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    return str(value or "").strip()



def _telegram_is_member(user_id):
    """Return True only for an active member, administrator, or group owner."""
    bot_token = _telegram_secret("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        return None
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getChatMember",
            params={"chat_id": TELEGRAM_GROUP, "user_id": int(user_id)},
            timeout=10,
        )
        if not response.ok:
            return False
        member = (response.json().get("result") or {})
        status = member.get("status")
        return status in {"creator", "administrator", "member"} or (
            status == "restricted" and bool(member.get("is_member"))
        )
    except (requests.RequestException, ValueError, TypeError):
        return False


def telegram_access_gate():
    """Require an active fruitworld23 membership before showing TTS controls."""
    if st.session_state.get("telegram_verified"):
        return True
    if not _telegram_secret("TELEGRAM_BOT_TOKEN"):
        st.error("⚠️ Telegram Bot Token မတွေ့ပါ။ Streamlit Secrets ထဲမှာ TELEGRAM_BOT_TOKEN ထည့်ပါ။")
        return False

    st.markdown("""
    <div class="telegram-banner">
      <div style="font-size:16px;font-weight:700;color:#f0f9ff;">🔒 အသံထုတ်ရန် Telegram Group ဝင်ထားရပါမည်</div>
      <div style="font-size:13px;color:#e0f2fe;margin:6px 0;">Group join ပြီးရင် Rose Bot က ပေးထားတဲ့ Telegram User ID ကို အောက်မှာထည့်ပြီး Verify လုပ်ပါ။</div>
      <a href="https://t.me/fruitworld23" target="_blank">🔗 fruitworld23 Group သို့ ဝင်မည်</a>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### Telegram Account Verify လုပ်ရန်")
    st.caption("Group join ပြီးတာနဲ့ Rose Bot က ပြပေးတဲ့ Telegram User ID ကို ကူးယူပြီး အောက်မှာထည့်ပါ။ User ID က @username မဟုတ်ဘဲ ဂဏန်းနံပါတ်ဖြစ်ရပါမယ်။")
    user_id_text = st.text_input(
        "Rose Bot ပေးထားတဲ့ Telegram User ID",
        key="telegram_user_id_input",
        placeholder="Rose Bot ကပေးတဲ့ ID ဥပမာ - 123456789",
    ).strip()
    if st.button("✅ Rose Bot ပေးထားတဲ့ ID ဖြင့် Verify လုပ်မည်", key="verify_telegram_member", use_container_width=True):
        if not user_id_text.isdigit():
            st.error("❌ Rose Bot ပေးထားတဲ့ User ID ဂဏန်းကို ထည့်ပါ။ @username မထည့်ပါနဲ့။")
        else:
            is_member = _telegram_is_member(user_id_text)
            if is_member:
                st.session_state["telegram_verified"] = True
                st.session_state["telegram_user_id"] = user_id_text
                st.rerun()
            elif is_member is False:
                st.warning("❌ ဒီ Telegram User ID က Group member မဟုတ်သေးပါ။ Group ဝင်ပြီး Verify ပြန်လုပ်ပါ။")
            else:
                st.error("❌ Telegram Bot Token ကို စစ်ပါ။")
    return False


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
    # No fixed character limit in the text box. The selected TTS provider's
    # credits/quota and the engine's safe chunking remain the practical limits.
    if not telegram_access_gate():
        return

    with st.container(border=True):
        st.markdown("### 🎙️ အသံဖန်တီးခြင်း")
        
        render_section("1", "စာသားထည့်သွင်းရန်")
        text = st.text_area(
            "စာသားထည့်ရန်",
            value="",
            height=180,
            label_visibility="collapsed",
            placeholder="ဒီမှာ စာသားရိုက်ထည့်ပါ..."
        )
        st.markdown(
            f"<div style='text-align:right; color:#64748b; font-size:13px; margin-top:-8px; margin-bottom:12px;'>လက်ရှိစာလုံးရေ — <b>{len(text):,}</b> လုံး (ကန့်သတ်ချက်မရှိပါ)</div>",
            unsafe_allow_html=True,
        )
        
        render_section("2", "အသံအမျိုးအစား ရွေးချယ်ခြင်း")
        # Keep the visible UI names explicit so old cached voice labels cannot reappear.
        voice_options = [
            "စိုင်းစိုင်း",
        ]
        selected_voice_str = st.radio(
            "အသံရွေးပါ",
            options=voice_options,
            index=0,
            horizontal=True,
            label_visibility="collapsed"
        )
        selected_idx = voice_options.index(selected_voice_str)
        voice_id, pitch_offset, name, label = FEATURED_VOICES[selected_idx]

        col_speed, col_pitch = st.columns(2)
        with col_speed:
            render_section("3", "အလျင်")
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
            st.caption(f"အလျင် — {speed_level}/100 • {speed:.2f} ဆ")
        with col_pitch:
            render_section("4", "အသံအမြင့်အနိမ့်")
            pitch_value = st.slider(
                "အသံအမြင့်အနိမ့်",
                min_value=-50,
                max_value=50,
                value=0,
                step=5,
                format="%d%%",
                label_visibility="collapsed"
            )

        st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)
        filename_input = st.text_input(
            "📁 ဖိုင်နာမည် သတ်မှတ်ရန်",
            value=st.session_state.get("output_filename_input", "mgkhant_voice"),
            placeholder="ဥပမာ - အင်ပါယာစတိတ်_ဇာတ်လမ်း",
            help="အသံဖိုင်နဲ့ SRT ဖိုင် နှစ်ခုလုံးကို ဒီနာမည်နဲ့ ဒေါင်းလုဒ်ရပါမယ်။ ဖိုင်အမျိုးအစားကို အလိုအလျောက် ထည့်ပေးပါမယ်။",
        )
        st.session_state["output_filename_input"] = filename_input
        action_col1, action_col2 = st.columns(2)
        with action_col1:
            test_btn = st.button("🔊 အသံစမ်းမည်", use_container_width=True)
        with action_col2:
            run_btn = st.button("🎧 အသံဖန်တီးမည်", use_container_width=True)

    if run_btn or test_btn:
        action_text = text.strip() if text.strip() else "အားလုံးပဲ မင်္ဂလာပါ။ Mg Khant AI မှ ကြိုဆိုပါတယ်။"
        with st.spinner("⏳ အသံဖိုင် ဖန်တီးနေပါသည်... စာလုံးရေများလို့ ခဏကြာနိုင်ပါတယ်။"):
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
                    )
                    
                    safe_filename = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", filename_input.strip()).strip(" ._")
                    if not safe_filename:
                        safe_filename = "mgkhant_voice"
                    st.session_state["output_filename"] = safe_filename
                    st.session_state.last_audio = audio_path
                    st.session_state.last_srt = srt_path
                    st.success("✅ အသံဖိုင် အောင်မြင်စွာ ဖန်တီးပြီးပါပြီ။")
                except Exception as e:
                    error_text = str(e)
                    # Keep the saved key on errors. The input box should not
                    # unexpectedly reappear after a long generation or a transient
                    # network/API failure. The user can use "Key ပြန်ပြောင်းမည်"
                    # manually when a different key is needed.
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
                    file_name=f"{st.session_state.get('output_filename', 'mgkhant_voice')}{st.session_state.last_audio.suffix}",
                    mime="audio/wav" if st.session_state.last_audio.suffix.lower() == ".wav" else "audio/mpeg",
                    use_container_width=True
                )
            with dl_col2:
                if "last_srt" in st.session_state and st.session_state.last_srt.exists():
                    st.download_button(
                        "📄 SRT စာတန်းထိုး",
                        data=st.session_state.last_srt.read_bytes(),
                        file_name=f"{st.session_state.get('output_filename', 'mgkhant_voice')}.srt",
                        mime="application/x-subrip",
                        use_container_width=True
                    )

# ---------------------------------------------------------------------------
# Admin Page
# ---------------------------------------------------------------------------

def admin_page():
    with st.container(border=True):
        st.markdown("### 🔐 စီမံခန့်ခွဲသူ စာမျက်နှာ")
        pwd = st.text_input("စီမံခန့်ခွဲသူ စကားဝှက် ထည့်ပါ", type="password", placeholder="Password ရိုက်ထည့်ပါ...")
        
        if pwd == ADMIN_PASSWORD:
            st.success("✅ Admin အဖြစ် အောင်မြင်စွာ ဝင်ရောက်ပြီးပါပြီ။")
            st.markdown("---")
            
            count = get_usage_count()
            col1, col2 = st.columns(2)
            with col1:
                st.metric("စုစုပေါင်း အသံထုတ်ယူမှု ကြိမ်ရေ", f"{count} ကြိမ်")
            with col2:
                if st.button("🔄 အသံထုတ်ယူမှု ကြိမ်ရေကို ၀ သို့ ပြန်ထားမည်", use_container_width=True):
                    with open("usage_stats.json", "w") as f:
                        json.dump({"count": 0}, f)
                    st.rerun()
        elif pwd:
            st.error("❌ Password မှားယွင်းနေပါသည်။")

# ---------------------------------------------------------------------------
# Main Router
# ---------------------------------------------------------------------------

def main():
    # New sessions open directly on TTS; the Admin password is never shown
    # unless the user explicitly selects the Admin menu.
    if "main_menu_initialized" not in st.session_state:
        st.session_state["main_menu_initialized"] = True
        st.session_state["main_menu"] = "🗣️ အသံထုတ်ရန်"

    with st.sidebar:
        st.markdown("<h2 style='text-align: center; color: #818cf8;'>🎙️ Mg Khant Pro</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 13px;'>အဆင့်မြင့် အသံပြောင်းစနစ်</p>", unsafe_allow_html=True)
        st.markdown("---")
        
        selected = st.radio(
            "မီနူးရွေးပါ",
            options=["🗣️ အသံထုတ်ရန်", "🔐 Admin"],
            index=0,
            key="main_menu",
            label_visibility="collapsed",
        )
        st.markdown("---")
        st.markdown("<div style='text-align: center; color: #64748b; font-size: 12px;'>© ၂၀၂၆ Mg Khant အသံစနစ်<br>မူပိုင်ခွင့်အားလုံး ရယူထားသည်</div>", unsafe_allow_html=True)

    if selected == "🗣️ အသံထုတ်ရန်":
        tts_page()
    else:
        admin_page()

if __name__ == "__main__":
    main()
        
