import html
import json
import os
import re
import tempfile
import wave
from pathlib import Path

import requests
import streamlit as st

APP_TITLE = "Mg Khant အသံပြောင်းစနစ် Pro"
ADMIN_PASSWORD = "Khant@6789"
USAGE_FILE = Path("usage_stats.json")
MAX_TEXT_CHARS = 10_000
CHUNK_SIZE = 2_400
SAMPLE_RATE = 24_000
SAMPLE_WIDTH = 2
CHANNELS = 1
TELEGRAM_GROUP = "@fruitworld23"
TELEGRAM_GROUP_URL = "https://t.me/fruitworld23"

# UI တွင် မြန်မာနာမည်ပဲ ပြပြီး Azure voice ID ကို နောက်ကွယ်မှာသာ သုံးသည်။
VOICE_CARDS = [
    ("နီလာ", "my-MM-NilarNeural"),
    ("အေမိဆန်", "en-US-AvaMultilingualNeural"),
    ("သင့်ဇာ", "en-US-EmmaMultilingualNeural"),
    ("စုမြတ်", "de-DE-SeraphinaMultilingualNeural"),
    ("ကြယ်စင်", "fr-FR-VivienneMultilingualNeural"),
    ("လမင်း", "zh-CN-XiaoxiaoMultilingualNeural"),
    ("သီဟ", "my-MM-ThihaNeural"),
    ("နေထူးနိုင်", "en-US-AndrewMultilingualNeural"),
    ("နေမျိုးအောင်", "en-US-BrianMultilingualNeural"),
    ("ကောင်ကောင်", "de-DE-FlorianMultilingualNeural"),
    ("အောင်ခန့်ပိုင်", "fr-FR-RemyMultilingualNeural"),
    ("နေတိုး", "it-IT-GiuseppeMultilingualNeural"),
]
VOICE_MAP = dict(VOICE_CARDS)


def secret_value(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
        if value:
            return str(value).strip()
    except Exception:
        pass
    return os.getenv(name, "").strip()


def telegram_is_member(user_id: str) -> bool | None:
    """Check membership using the Bot API. Bot must be an admin in the group."""
    token = secret_value("TELEGRAM_BOT_TOKEN")
    if not token:
        return None
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{token}/getChatMember",
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


def telegram_access_gate() -> bool:
    """Require Telegram Group membership before showing the TTS controls."""
    if st.session_state.get("telegram_verified"):
        return True
    if not secret_value("TELEGRAM_BOT_TOKEN"):
        st.error("Telegram Bot Token မတွေ့ပါ။ Streamlit Secrets ထဲမှာ TELEGRAM_BOT_TOKEN ထည့်ပါ။")
        return False

    st.markdown(
        f'''<div class="telegram-banner">
        <b>🔒 အသံထုတ်ရန် Telegram Group ဝင်ထားရပါမည်</b>
        <p>Group ထဲဝင်ပြီး Rose Bot ပေးသော Telegram User ID ကို ထည့်ကာ Verify လုပ်ပါ။</p>
        <a href="{TELEGRAM_GROUP_URL}" target="_blank">🔗 Group သို့ ဝင်မည်</a>
        </div>''',
        unsafe_allow_html=True,
    )
    user_id = st.text_input(
        "Telegram User ID",
        key="telegram_user_id_input",
        placeholder="ဥပမာ - 123456789",
        help="Rose Bot ပေးသော ဂဏန်း User ID ကိုသာ ထည့်ပါ။ @username မထည့်ပါနှင့်။",
    ).strip()
    if st.button("✅ Group Join Verify လုပ်မည်", use_container_width=True):
        if not user_id.isdigit():
            st.error("Telegram User ID ကို ဂဏန်းနံပါတ်ဖြင့် ထည့်ပါ။")
        else:
            result = telegram_is_member(user_id)
            if result is True:
                st.session_state["telegram_verified"] = True
                st.session_state["telegram_user_id"] = user_id
                st.rerun()
            elif result is False:
                st.warning("ဒီ User ID က Group member မဟုတ်သေးပါ။ Group ဝင်ပြီး Verify ပြန်လုပ်ပါ။")
            else:
                st.error("Telegram Bot Token ကို Streamlit Secrets ထဲ ထည့်ပါ။")
    return False


def get_usage_count() -> int:
    try:
        data = json.loads(USAGE_FILE.read_text(encoding="utf-8")) if USAGE_FILE.exists() else {}
        return int(data.get("count", 0))
    except Exception:
        return 0


def increment_usage() -> int:
    count = get_usage_count() + 1
    try:
        USAGE_FILE.write_text(json.dumps({"count": count}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return count


def azure_settings() -> tuple[str, str, str]:
    key = secret_value("AZURE_SPEECH_KEY")
    region = secret_value("AZURE_SPEECH_REGION") or "southeastasia"
    # api.cognitive.microsoft.com is not the regional TTS endpoint.
    endpoint = f"https://{region.lower()}.tts.speech.microsoft.com"
    return key, region.lower(), endpoint


def voice_locale(voice_id: str) -> str:
    parts = str(voice_id).split("-")
    return "-".join(parts[:2]) if len(parts) >= 2 else "my-MM"


def split_text(text: str, limit: int = CHUNK_SIZE) -> list[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return []
    sentences = [x.strip() for x in re.split(r"(?<=[။!?])\s+", cleaned) if x.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences or [cleaned]:
        while len(sentence) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sentence[:limit])
            sentence = sentence[limit:]
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > limit:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def make_ssml(text: str, voice_id: str, rate_percent: int, pitch_hz: int) -> str:
    safe_text = html.escape(text, quote=False)
    safe_voice = html.escape(voice_id, quote=True)
    locale = voice_locale(voice_id)
    rate = f"{rate_percent:+d}%" if rate_percent else "0%"
    pitch = f"{pitch_hz:+d}Hz" if pitch_hz else "0Hz"
    return (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{locale}">'
        f'<voice name="{safe_voice}"><prosody rate="{rate}" pitch="{pitch}">{safe_text}</prosody></voice>'
        "</speak>"
    )


def request_audio(chunk: str, voice_id: str, key: str, endpoint: str, rate: int, pitch: int) -> bytes:
    url = f"{endpoint}/cognitiveservices/v1"
    response = requests.post(
        url,
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "raw-24khz-16bit-mono-pcm",
            "User-Agent": "mg-khant-azure-tts",
        },
        data=make_ssml(chunk, voice_id, rate, pitch).encode("utf-8"),
        timeout=(10, 90),
    )
    if not response.ok:
        detail = (response.text or "").strip()[:500]
        raise RuntimeError(f"Azure Speech TTS error {response.status_code}: {detail or 'Azure က error detail မပြန်ပါ'}")
    audio = bytes(response.content or b"")
    if len(audio) < 480:
        raise RuntimeError("Azure က ပြန်ပေးသော အသံ data မပြည့်စုံပါ။")
    return audio


def pcm_to_wav(pcm: bytes) -> bytes:
    output = tempfile.SpooledTemporaryFile()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)
    output.seek(0)
    return output.read()


def srt_time(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def make_srt(chunks: list[str], segments: list[bytes]) -> str:
    lines: list[str] = []
    cursor = 0.0
    for index, (chunk, audio) in enumerate(zip(chunks, segments), start=1):
        duration = max(0.1, len(audio) / (SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS))
        lines.extend([str(index), f"{srt_time(cursor)} --> {srt_time(cursor + duration)}", chunk, ""])
        cursor += duration
    return "\n".join(lines)


def synthesize(text: str, voice_id: str, rate: int, pitch: int) -> tuple[bytes, str]:
    cleaned = str(text or "").strip()
    if not cleaned:
        raise ValueError("အသံပြောင်းရန် စာသားထည့်ပါ။")
    if len(cleaned) > MAX_TEXT_CHARS:
        raise ValueError(f"စာလုံးရေ {MAX_TEXT_CHARS:,} ထက် မကျော်ရပါ။")
    key, _region, endpoint = azure_settings()
    if not key:
        raise RuntimeError("AZURE_SPEECH_KEY ကို Streamlit Secrets ထဲ ထည့်ပါ။")
    chunks = split_text(cleaned)
    segments = [request_audio(chunk, voice_id, key, endpoint, rate, pitch) for chunk in chunks]
    return b"".join(segments), make_srt(chunks, segments)


def inject_css() -> None:
    st.markdown("""<style>
    :root { --ink:#f8fafc; --muted:#cbd5e1; --purple:#6366f1; --pink:#ec4899; }
    [data-testid="stAppViewContainer"] { background:radial-gradient(circle at top right,#312e81 0%,#171744 42%,#070b1d 100%); color:var(--ink); }
    [data-testid="stHeader"] { background:transparent; }
    h1,h2,h3,h4,p,label,[data-testid="stMarkdownContainer"] { color:var(--ink)!important; }
    [data-testid="stCaptionContainer"] p { color:var(--muted)!important; }
    .telegram-banner { background:linear-gradient(135deg,#075985,#1d4ed8); padding:20px; border-radius:18px; text-align:center; color:white; margin:12px 0 22px; border:1px solid #60a5fa66; box-shadow:0 12px 30px #02061780; }
    .telegram-banner b { color:#fff; font-size:17px; }
    .telegram-banner p { margin:8px 0 13px; color:#dbeafe!important; }
    .telegram-banner a { color:white; text-decoration:none; font-weight:800; background:#ffffff2e; padding:8px 17px; border-radius:24px; display:inline-block; }
    .stTextArea textarea,.stTextInput input { color:#fff!important; background:#101b35!important; border:1px solid #818cf8aa!important; border-radius:14px!important; }
    .stTextArea textarea::placeholder,.stTextInput input::placeholder { color:#94a3b8!important; }
    [data-testid="stButton"] > button { background:linear-gradient(135deg,#6366f1 0%,#ec4899 100%)!important; color:#fff!important; border:1px solid #c4b5fd55!important; border-radius:14px!important; box-shadow:0 8px 20px #4f46e540!important; font-weight:800!important; min-height:48px!important; }
    [data-testid="stButton"] > button:hover { transform:translateY(-2px); box-shadow:0 12px 25px #ec489966!important; }
    div[role="radiogroup"] { display:grid!important; grid-template-columns:repeat(3,minmax(0,1fr)); gap:20px!important; margin:18px 0 28px!important; }
    div[role="radiogroup"] > label { min-height:118px!important; padding:20px 12px!important; border:1px solid #818cf866!important; border-radius:16px!important; background:linear-gradient(145deg,#25245b,#10172f)!important; display:flex!important; align-items:center!important; justify-content:center!important; text-align:center!important; transition:.2s!important; }
    div[role="radiogroup"] > label:hover { border-color:#f9a8d4!important; transform:translateY(-2px); }
    div[role="radiogroup"] > label:has(input:checked) { background:linear-gradient(135deg,#6366f1,#db2777)!important; border:2px solid #fbcfe8!important; box-shadow:0 8px 22px #db277755!important; }
    div[role="radiogroup"] > label p { color:#fff!important; font-size:15px!important; font-weight:800!important; }
    @media (max-width:600px) { div[role="radiogroup"] { grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px!important; margin:14px 0 24px!important; } div[role="radiogroup"] > label { min-height:96px!important; padding:14px 5px!important; } div[role="radiogroup"] > label p { font-size:12px!important; } }
    </style>""", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="🎙️", layout="centered")
    inject_css()
    st.title("🎙️ Mg Khant အသံပြောင်းစနစ်")
    st.caption("စာရိုက်ပြီး Azure Speech API ဖြင့် အသံထုတ်ပါ။")

    with st.sidebar:
        st.markdown("### Admin")
        admin_password = st.text_input("Admin Password", type="password", key="admin_password")
        if admin_password == ADMIN_PASSWORD:
            st.success("Admin ဝင်ထားပါပြီ")
            st.metric("အသုံးပြုမှုအကြိမ်ရေ", get_usage_count())
        elif admin_password:
            st.error("Password မမှန်ပါ")

    if not telegram_access_gate():
        return

    st.success("Telegram Group Join Verify အောင်မြင်ပါပြီ။")
    text = st.text_area("အသံပြောင်းမည့်စာ", height=240, max_chars=MAX_TEXT_CHARS, placeholder="မြန်မာစာကို ဒီမှာ ထည့်ပါ…")
    st.caption(f"{len(text):,} / {MAX_TEXT_CHARS:,} စာလုံး")
    st.markdown("### အသံရွေးရန်")
    voice_names = [name for name, _voice in VOICE_CARDS]
    selected_name = st.radio("အသံရွေးရန်", voice_names, key="selected_voice_name", label_visibility="collapsed")
    selected_voice = VOICE_MAP[selected_name]
    st.info(f"ရွေးထားသောအသံ — {selected_name}")
    rate = st.slider("အသံမြန်နှုန်း", -40, 40, 0, 5, format="%d%%")
    pitch = st.slider("အသံအနိမ့်အမြင့်", -10, 10, 0, 1, format="%dHz")

    if st.button("🎧 အသံဖန်တီးမည်", type="primary", use_container_width=True):
        try:
            with st.spinner("အသံဖန်တီးနေပါသည်…"):
                pcm, srt = synthesize(text, selected_voice, rate, pitch)
            wav_data = pcm_to_wav(pcm)
            increment_usage()
            st.success("အသံဖန်တီးပြီးပါပြီ။")
            st.audio(wav_data, format="audio/wav")
            col_a, col_b = st.columns(2)
            with col_a:
                st.download_button("WAV ဒေါင်းရန်", wav_data, "mgkhant_voice.wav", "audio/wav", use_container_width=True)
            with col_b:
                st.download_button("SRT ဒေါင်းရန်", srt.encode("utf-8"), "mgkhant_voice.srt", "text/plain", use_container_width=True)
        except Exception as exc:
            st.error(f"အမှားအယွင်း ဖြစ်ပေါ်သည်: {exc}")


if __name__ == "__main__":
    main()
