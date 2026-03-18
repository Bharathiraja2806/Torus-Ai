import os
import time

import requests
import streamlit as st

API_URL = os.getenv("BACKEND_API_URL", "https://torus-ai.onrender.com")
REQUEST_TIMEOUT = 60

st.set_page_config(
    page_title="Torus AI",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        html, body, [class*="css"] {
            font-family: "Aptos", "Segoe UI", "Trebuchet MS", sans-serif;
        }

        /* Hide all Streamlit branding */
        header {visibility: hidden;}

        /* Remove extra spacing */
        .block-container {
            padding-top: 0rem;
            padding-bottom: 0rem;
        }

        /* Optional: make app full screen feel */
        .css-18e3th9 {
            padding-top: 0rem;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(59, 130, 246, 0.12), transparent 28%),
                radial-gradient(circle at bottom right, rgba(16, 185, 129, 0.12), transparent 24%),
                linear-gradient(180deg, #0b1020 0%, #111827 48%, #0f172a 100%);
            color: #e5eefc;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
            border-right: 1px solid rgba(148, 163, 184, 0.14);
        }

        .hero-card {
            padding: 1.4rem 1.5rem;
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 20px;
            background: rgba(15, 23, 42, 0.72);
            box-shadow: 0 24px 80px rgba(15, 23, 42, 0.36);
            backdrop-filter: blur(12px);
            margin-bottom: 1rem;
        }

        .hero-title {
            font-size: 2.2rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            margin-bottom: 0.35rem;
        }

        .hero-copy {
            color: #a5b4cc;
            font-size: 1rem;
        }

        .sidebar-section-title {
            color: #cbd5e1;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
            margin: 1.2rem 0 0.65rem;
        }

        .chat-shell {
            padding-bottom: 6rem;
        }

        .stChatMessage {
            background: rgba(15, 23, 42, 0.72);
            border: 1px solid rgba(148, 163, 184, 0.14);
            border-radius: 18px;
            padding: 0.35rem 0.35rem 0.2rem;
        }

        .stChatInput > div {
            border-radius: 18px;
        }

        .pill {
            display: inline-block;
            padding: 0.35rem 0.7rem;
            border-radius: 999px;
            background: rgba(30, 41, 59, 0.95);
            color: #cbd5e1;
            border: 1px solid rgba(148, 163, 184, 0.12);
            font-size: 0.84rem;
            margin-right: 0.45rem;
            margin-bottom: 0.4rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def auth_headers() -> dict:
    token = st.session_state.get("token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


def api_request(method: str, path: str, **kwargs):
    headers = kwargs.pop("headers", {})
    headers = {**auth_headers(), **headers}
    response = requests.request(
        method,
        f"{API_URL}{path}",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        **kwargs,
    )

    payload = {}
    if response.content:
        try:
            payload = response.json()
        except ValueError:
            payload = {"error": response.text}

    if response.status_code >= 400:
        raise RuntimeError(payload.get("error", f"Request failed with {response.status_code}"))

    return payload


def set_session_from_auth(payload: dict) -> None:
    st.session_state.token = payload["token"]
    st.session_state.user = payload["user"]


def ensure_chat_selected(chats: list[dict]) -> None:
    if not chats:
        st.session_state.pop("chat_id", None)
        return

    chat_ids = {chat["id"] for chat in chats}
    if st.session_state.get("chat_id") not in chat_ids:
        st.session_state.chat_id = chats[0]["id"]


def create_new_chat() -> None:
    payload = api_request("POST", "/chats", json={"title": "New chat"})
    st.session_state.chat_id = payload["chat"]["id"]


def render_auth_screen() -> None:
    left, center, right = st.columns([1, 1.2, 1])
    with center:
        st.markdown(
            """
            <div class="hero-card">
                <div class="hero-title">Torus AI</div>
                <div class="hero-copy">A cleaner, smarter chat workspace with persistent conversations and a ChatGPT-inspired flow.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        login_tab, register_tab = st.tabs(["Login", "Register"])

        with login_tab:
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("Sign in", use_container_width=True):
                try:
                    payload = api_request(
                        "POST",
                        "/login",
                        headers={},
                        json={"username": username, "password": password},
                    )
                    set_session_from_auth(payload)
                    st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc))

        with register_tab:
            username = st.text_input("Create username", key="register_user")
            password = st.text_input("Create password", type="password", key="register_pass")
            if st.button("Create account", use_container_width=True):
                try:
                    payload = api_request(
                        "POST",
                        "/register",
                        headers={},
                        json={"username": username, "password": password},
                    )
                    set_session_from_auth(payload)
                    create_new_chat()
                    st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc))


def render_sidebar(chats: list[dict]) -> None:
    st.sidebar.markdown("## Torus AI")
    st.sidebar.caption("Your conversations, organized.")

    if st.sidebar.button("+ New chat", use_container_width=True):
        create_new_chat()
        st.rerun()

    st.sidebar.markdown('<div class="sidebar-section-title">Recent chats</div>', unsafe_allow_html=True)

    for chat in chats:
        title = chat["title"] or "Untitled chat"
        is_active = st.session_state.get("chat_id") == chat["id"]
        button_label = f"{'* ' if is_active else ''}{title}"
        if st.sidebar.button(button_label, key=f"chat_open_{chat['id']}", use_container_width=True):
            st.session_state.chat_id = chat["id"]
            st.rerun()

        with st.sidebar.expander(f"Manage: {title}", expanded=False):
            new_title = st.text_input("Rename chat", value=title, key=f"rename_input_{chat['id']}")
            col1, col2 = st.columns(2)
            if col1.button("Save", key=f"rename_btn_{chat['id']}", use_container_width=True):
                try:
                    api_request("PATCH", f"/chats/{chat['id']}", json={"title": new_title})
                    st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc))
            if col2.button("Delete", key=f"delete_btn_{chat['id']}", use_container_width=True):
                try:
                    api_request("DELETE", f"/chats/{chat['id']}")
                    if st.session_state.get("chat_id") == chat["id"]:
                        st.session_state.pop("chat_id", None)
                    st.rerun()
                except RuntimeError as exc:
                    st.error(str(exc))

    st.sidebar.markdown('<div class="sidebar-section-title">Account</div>', unsafe_allow_html=True)
    if user := st.session_state.get("user"):
        st.sidebar.write(f"Signed in as `{user['username']}`")
    if st.sidebar.button("Log out", use_container_width=True):
        for key in ["token", "user", "chat_id"]:
            st.session_state.pop(key, None)
        st.rerun()


def render_empty_state() -> None:
    st.markdown(
        """
        <div class="hero-card">
            <div class="hero-title">Start a conversation</div>
            <div class="hero-copy">Create a new chat from the sidebar and ask anything. Your messages stay grouped by conversation like ChatGPT.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<span class="pill">Brainstorm ideas</span>'
        '<span class="pill">Write code</span>'
        '<span class="pill">Summarize text</span>'
        '<span class="pill">Explain concepts</span>',
        unsafe_allow_html=True,
    )


def stream_text(text: str, container) -> None:
    assembled = ""
    for token in text.split():
        assembled = f"{assembled} {token}".strip()
        container.markdown(assembled)
        time.sleep(0.015)
    if not text:
        container.markdown("")


def render_chat_view(messages: list[dict], chat_title: str) -> None:
    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-title">{chat_title}</div>
            <div class="hero-copy">A focused conversation workspace with persistent history and backend-managed AI responses.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown('<div class="chat-shell">', unsafe_allow_html=True)
        for message in messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        st.markdown("</div>", unsafe_allow_html=True)


inject_styles()

if "token" not in st.session_state:
    render_auth_screen()
    st.stop()

try:
    me_payload = api_request("GET", "/me")
    st.session_state.user = me_payload["user"]
except RuntimeError:
    for key in ["token", "user", "chat_id"]:
        st.session_state.pop(key, None)
    st.rerun()

try:
    chats_payload = api_request("GET", "/chats")
    chats = chats_payload["chats"]
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()

ensure_chat_selected(chats)
render_sidebar(chats)

if not chats or "chat_id" not in st.session_state:
    render_empty_state()
    st.stop()

current_chat = next((chat for chat in chats if chat["id"] == st.session_state.chat_id), None)
if current_chat is None:
    render_empty_state()
    st.stop()

try:
    messages_payload = api_request("GET", f"/chats/{current_chat['id']}/messages")
    messages = messages_payload["messages"]
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()

render_chat_view(messages, current_chat["title"])

prompt = st.chat_input("Message Torus AI")

if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        placeholder.markdown("Thinking...")
        try:
            payload = api_request(
                "POST",
                "/chat",
                json={"chat_id": current_chat["id"], "prompt": prompt},
            )
            stream_text(payload["reply"], placeholder)
            st.session_state.chat_id = payload["chat"]["id"]
        except RuntimeError as exc:
            placeholder.markdown(f"**Error:** {exc}")

    st.rerun()
