"""Mg Khant အသံပြောင်းစနစ် Pro - Streamlit Voice Changer App with Modern UI."""

import base64
import streamlit as st
from streamlit_option_menu import option_menu
from pathlib import Path
import json

from voice_engine import (
    FEATURED_VOICES, EFFECTS, 
    change_tempo, get_usage_count, run_tts_to_file, apply_effects
)

# ---------------------------------------------------------------------------
# Page config & Custom CSS
# ---------------------------------------------------------------------------

ADMIN_PASSWORD = "saingmyanmar2026"

st.set_page_config(
    page_title="Mg Khant အသံပြောင်းစနစ် Pro",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Modern Dark Theme UI
def inject_custom_css():
    custom_css = """
    <style>
    :root {
        --primary-color: #6366f1;
        --primary-dark: #4f46e5;
        --secondary-color: #ec4899;
        --accent-color: #06b6d4;
        --bg-dark: #0f172a;
        --bg-darker: #020617;
        --text-light: #e2e8f0;
        --border-color: #1e293b;
    }
    
    /* Main background */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
        color: var(--text-light);
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e1b4b 0%, #0f172a 100%);
        border-right: 1px solid var(--border-color);
    }
    
    /* Section headers with numbers */
    .section-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 24px 0 16px 0;
        padding: 16px;
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(236, 72, 153, 0.1) 100%);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        border-left: 4px solid var(--primary-color);
    }
    
    .section-number {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
        border-radius: 50%;
        color: white;
        font-weight: bold;
        font-size: 18px;
        border: 2px solid rgba(255, 255, 255, 0.2);
    }
    
    .section-title {
        font-size: 20px;
        font-weight: 600;
        color: var(--text-light);
        margin: 0;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
        color: white;
        border: none;
        border-radius: 8px;
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
    
    /* Text inputs */
    .stTextArea > label,
    .stTextInput > label {
        color: var(--text-light);
        font-weight: 500;
    }
    
    .stTextArea textarea,
    .stTextInput input {
        background-color: rgba(30, 41, 59, 0.8) !important;
        color: var(--text-light) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 8px !important;
    }
    
    .stTextArea textarea:focus,
    .stTextInput input:focus {
        border-color: var(--primary-color) !important;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1) !important;
    }
    
    /* Select boxes */
    .stSelectbox > label,
    .stSelectbox > div > div {
        color: var(--text-light);
    }
    
    /* Sliders */
    .stSlider > label {
        color: var(--text-light);
        font-weight: 500;
    }
    
    /* Audio player */
    audio {
        width: 100%;
        border-radius: 8px;
        margin: 16px 0;
    }
    
    /* Success/Error messages */
    .stSuccess {
        background-color: rgba(34, 197, 94, 0.15) !important;
        border: 1px solid rgba(34, 197, 94, 0.3) !important;
        color: #86efac !important;
        border-radius: 8px !important;
    }
    
    .stError {
        background-color: rgba(239, 68, 68, 0.15) !important;
        border: 1px solid rgba(239, 68, 68, 0.3) !important;
        color: #fca5a5 !important;
        border-radius: 8px !important;
    }
    
    .stWarning {
        background-color: rgba(251, 146, 60, 0.15) !important;
        border: 1px solid rgba(251, 146, 60, 0.3) !important;
        color: #fed7aa !important;
        border-radius: 8px !important;
    }
    
    /* Metric styling */
    .stMetric {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(236, 72, 153, 0.1) 100%);
        padding: 16px;
        border-radius: 12px;
        border: 1px solid var(--border-color);
    }
    
    /* Divider */
    hr {
        border-color: var(--border-color) !important;
    }
    
    /* Telegram group banner */
    .telegram-banner {
        background: linear-gradient(135deg, #0088cc 0%, #0066aa 100%);
        padding: 16px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 24px;
        border: 1px solid rgba(0, 136, 204, 0.3);
        box-shadow: 0 4px 15px rgba(0, 136, 204, 0.2);
    }
    
    .telegram-banner a {
        color: white;
        text-decoration: none;
        font-weight: 600;
        font-size: 16px;
    }
    
    .telegram-banner a:hover {
        text-decoration: underline;
    }
    
    /* Download button */
    .stDownloadButton > button {
        background: linear-gradient(135deg, var(--accent-color) 0%, #06b6d4 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 12px 24px !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }
    
    .stDownloadButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(6, 182, 212, 0.4) !important;
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

inject_custom_css()

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def b64_audio(path):
    """Return base64-encoded audio data for the HTML audio player."""
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode()
    mime = "audio/mpeg"
    return f'data:{mime};base64,{b64}'

def audio_player(path):
    st.audio(b64_audio(path), format="audio/mp3")

def render_section_header(number, title):
    """Render a numbered section header."""
    st.markdown(f"""
    <div class="section-header">
        <div class="section-number">{number}</div>
        <div class="section-title">{title}</div>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# TTS page
# ---------------------------------------------------------------------------

def tts_page():
    # Telegram Group Banner
    st.markdown("""
    <div class="telegram-banner">
        <span style="font-size: 18px; margin-right: 12px;">📱</span>
        <strong>Group Join :</strong> အသံပြောင်းစနစ် အဆင်သင့်ဖြစ်ရန် Mg Khant Group မှ ကြည့်ရှုပါ။
        <br>
        <a href="https://t.me/fruitworld23" target="_blank">🔗 Mg Khant Group ကို ကြည့်ရှုပါ</a>
    </div>
    """, unsafe_allow_html=True)
    
    render_section_header("2", "စာသားထည့်သွင်းခြင်း")
    
    text = st.text_area(
        "စာသားထည့်ပါ (မြန်မာ / အင်္ဂလိပ်)",
        value="မင်္ဂလာပါ၊ ဒီစနစ်က နေ သင့်စာသားကို အသံအမျိုးမျိုးနဲ့ ဖတ်ပေးပါတယ်။",
        height=120,
        label_visibility="collapsed"
    )
    
    render_section_header("3", "အသံရွေးချယ်ခြင်း (Voice)")
    
    # Voice selection
    voice_options = [f"{name} - {label}" for _, _, name, label in FEATURED_VOICES]
    selected_voice_str = st.selectbox(
        "အသံရွေးပါ",
        options=voice_options,
        label_visibility="collapsed"
    )
    
    # Get selected voice index
    selected_idx = voice_options.index(selected_voice_str)
    voice_id, pitch_offset, name, label = FEATURED_VOICES[selected_idx]
    
    render_section_header("4", "အလျင်အမြန် (Speed)")
    speed = st.slider(
        "အသံအလျင်",
        min_value=0.5,
        max_value=2.0,
        value=1.0,
        step=0.1,
        format="%.1fx",
        label_visibility="collapsed"
    )
    
    render_section_header("5", "အသံအမြင့်အနိမ့် (Pitch)")
    pitch_value = st.slider(
        "Pitch ပြင်ဆင်မှု",
        min_value=-50,
        max_value=50,
        value=0,
        step=5,
        format="%d%%",
        label_visibility="collapsed"
    )
    
    render_section_header("6", "✨ အသံထုတ်ရန်")
    
    run_btn = st.button("🎧 အသံထုတ်ရန်", type="primary", use_container_width=True)
    
    if run_btn:
        if not text.strip():
            st.warning("⚠️ စာသားထည့်ပါ။")
        else:
            with st.spinner("⏳ အသံ generate လုပ်နေပါသည်..."):
                try:
                    # Convert pitch_value to pitch format
                    pitch_str = f"{pitch_value:+d}%" if pitch_value != 0 else "+0%"
                    
                    # Calculate rate from speed
                    rate_percent = (speed - 1) * 100
                    rate_str = f"{rate_percent:+.0f}%"
                    
                    audio_path, srt_path = run_tts_to_file(
                        text, 
                        voice_id, 
                        pitch_offset,
                        rate=rate_str,
                        suffix="custom"
                    )
                    
                    if speed != 1.0:
                        audio_path = change_tempo(audio_path, speed)
                    
                    st.session_state.last_audio = audio_path
                    st.session_state.last_srt = srt_path
                    st.success("✅ အသံဖန်တီးပြီးပါပြီ။")
                except Exception as e:
                    st.error(f"❌ အောင်မြင်စွာ မဖန်တီးနိုင်ပါ: {str(e)}")
    
    if "last_audio" in st.session_state:
        st.markdown("---")
        render_section_header("7", "အသံထုတ်ယူမှု အောင်မြင်ပြီး ✅")
        
        audio_player(st.session_state.last_audio)
        
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "⬇️ အသံ (MP3) ထုတ်ယူရန်",
                data=st.session_state.last_audio.read_bytes(),
                file_name="voice_output.mp3",
                mime="audio/mpeg",
                use_container_width=True
            )
        
        with col2:
            if "last_srt" in st.session_state and st.session_state.last_srt.exists():
                st.download_button(
                    "📄 SRT ထုတ်ယူရန်",
                    data=st.session_state.last_srt.read_bytes(),
                    file_name="voice_output.srt",
                    mime="text/plain",
                    use_container_width=True
                )

# ---------------------------------------------------------------------------
# Voice effects page
# ---------------------------------------------------------------------------

def effects_page():
    render_section_header("2", "အသံဖိုင် Effect ပြောင်းခြင်း")
    
    st.markdown("Audio ဖိုင် upload လုပ်ပြီး voice effect ရွေးပါ။")
    
    uploaded = st.file_uploader(
        "Audio ဖိုင်တင်ပါ (mp3 / wav)",
        type=["mp3", "wav", "ogg", "m4a"],
        key="audio_uploader",
    )
    
    if uploaded is not None:
        st.session_state.uploaded_name = uploaded.name
        st.session_state.uploaded_data = uploaded.read()
    
    if "uploaded_data" in st.session_state and st.session_state.uploaded_data:
        audio_data = st.session_state.uploaded_data
        input_path = Path(f"/tmp/upload_{st.session_state.uploaded_name}")
        with open(input_path, "wb") as f:
            f.write(audio_data)
        
        render_section_header("3", "မူရင်းအသံ")
        st.audio(audio_data, format="audio/mp3")
        
        col1, col2 = st.columns(2)
        with col1:
            effect = st.selectbox("Effect ရွေးပါ", list(EFFECTS.keys()), label_visibility="collapsed")
        with col2:
            extra_tempo = st.slider("Extra Speed", 0.5, 2.0, 1.0, 0.05)
        
        render_section_header("4", "🎛️ Effect ပြောင်းရန်")
        
        convert_clicked = st.button("🎛️ Effect ပြောင်းရန်", type="primary", use_container_width=True)
        
        if convert_clicked:
            with st.spinner("⏳ Effect ပြောင်းနေပါသည်..."):
                try:
                    out_path = apply_effects(input_path, effect, tempo=extra_tempo)
                    st.session_state.effect_audio = out_path
                    st.session_state.effect_name = effect
                    st.success("✅ Effect ပြောင်းပြီးပါပြီ။")
                except Exception as e:
                    st.error(f"❌ ပြောင်းနိုင်ခြင်း မရှိပါ: {str(e)}")
        
        if "effect_audio" in st.session_state:
            st.markdown("---")
            render_section_header("5", f"ရလဒ် - {st.session_state.effect_name}")
            
            audio_player(st.session_state.effect_audio)
            st.download_button(
                "⬇️ အသံဖိုင် Download လုပ်ရန်",
                data=st.session_state.effect_audio.read_bytes(),
                file_name="voice_effect_output.mp3",
                mime="audio/mpeg",
                use_container_width=True
            )

# ---------------------------------------------------------------------------
# Admin Page
# ---------------------------------------------------------------------------

def admin_page():
    render_section_header("🔐", "Admin Dashboard")
    
    pwd = st.text_input("Admin Password ကိုထည့်ပါ", type="password", label_visibility="collapsed")
    
    if pwd == ADMIN_PASSWORD:
        st.success("✅ Welcome, Admin!")
        st.markdown("---")
        
        count = get_usage_count()
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("စုစုပေါင်း အသံထုတ်ယူမှု", f"{count} ကြိမ်")
        
        with col2:
            if st.button("🔄 Usage Count ကို Reset လုပ်ရန်", use_container_width=True):
                with open("usage_stats.json", "w") as f:
                    json.dump({"count": 0}, f)
                st.rerun()
    elif pwd:
        st.error("❌ Password မှားနေပါသည်။")

# ---------------------------------------------------------------------------
# About page
# ---------------------------------------------------------------------------

def about_page():
    render_section_header("ℹ️", "App အကြောင်း")
    
    st.markdown(f"""
    ### 🎙️ Mg Khant အသံပြောင်းစနစ် Pro
    
    ဒီ app ကို အသံပေါင်း ၁၀ မျိုးနဲ့ အသုံးပြုရလွယ်ကူအောင် ပြင်ဆင်ထားပါတယ်။
    
    **✨ အဓိက အင်္ဂါရပ်များ**
    - 🎙️ အသံ ၁၀ မျိုး (Celebrity voices)
    - ⚡ အလျင်အမြန် ပြင်ဆင်နိုင်
    - 🎚️ အသံ Effect ၉ မျိုး
    - 📄 SRT Subtitle ထုတ်ယူနိုင်
    - 🎯 Admin Dashboard နဲ့ Usage Tracking
    
    **🛠️ Technology Stack**
    - **Python** — ပင်မ programming language
    - **Streamlit** — web app framework
    - **edge-tts** — Microsoft Neural Voices Engine
    - **ffmpeg** — Audio processing engine
    
    **👨‍💻 Developed with ❤️**
    
    ---
    
    📱 **Group Link**: [Mg Khant Group](https://t.me/fruitworld23)
    """)

# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main():
    # Sidebar navigation
    with st.sidebar:
        st.markdown("### 🎙️ Mg Khant အသံပြောင်းစနစ်")
        st.markdown("---")
        selected = option_menu(
            menu_title=None,
            options=["🗣️ အသံထုတ်ရန်", "🎚️ Effect ပြောင်းရန်", "ℹ️ အကြောင်း", "🔐 Admin"],
            icons=["mic", "sliders", "info-circle", "lock"],
            default_index=0,
        )
        st.markdown("---")
        st.caption("© 2024 Mg Khant Voice System")

    if selected == "🗣️ အသံထုတ်ရန်":
        tts_page()
    elif selected == "🎚️ Effect ပြောင်းရန်":
        effects_page()
    elif selected == "ℹ️ အကြောင်း":
        about_page()
    else:
        admin_page()

if __name__ == "__main__":
    main()
