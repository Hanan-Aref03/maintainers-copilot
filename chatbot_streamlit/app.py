from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st


API_URL = os.getenv("API_URL", "http://localhost:8010").rstrip("/")
MODEL_SERVER_URL = os.getenv("MODEL_SERVER_URL", "http://localhost:8011").rstrip("/")


def api_request(
    method: str,
    path: str,
    *,
    json_payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = 120,
) -> requests.Response:
    headers = {}
    token = st.session_state.get("auth_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{API_URL}{path}"
    return requests.request(
        method,
        url,
        headers=headers,
        json=json_payload,
        params=params,
        timeout=timeout,
    )


def model_request(
    path: str,
    *,
    json_payload: dict[str, Any],
    timeout: int = 120,
) -> requests.Response:
    url = f"{MODEL_SERVER_URL}{path}"
    return requests.post(url, json=json_payload, timeout=timeout)


def parse_response(response: requests.Response) -> dict[str, Any]:
    try:
        return response.json()
    except Exception:
        return {"detail": response.text}


def ensure_state() -> None:
    st.session_state.setdefault("auth_token", "")
    st.session_state.setdefault("current_user", None)
    st.session_state.setdefault("chat_messages", {})
    st.session_state.setdefault("thread_id", "demo-thread")
    st.session_state.setdefault("selected_widget", "demo123")
    st.session_state.setdefault("tool_text", "")
    st.session_state.setdefault("tool_model", "fine")
    st.session_state.setdefault("memory_text", "")
    st.session_state.setdefault("memory_type", "semantic")
    st.session_state.setdefault("widget_public_id", "")
    st.session_state.setdefault("widget_origins", "http://localhost:3000")
    st.session_state.setdefault("widget_greeting", "Hi! How can I help with issue triage?")


def set_auth(token: str, user: dict[str, Any]) -> None:
    st.session_state["auth_token"] = token
    st.session_state["current_user"] = user


def clear_auth() -> None:
    st.session_state["auth_token"] = ""
    st.session_state["current_user"] = None


def current_user() -> dict[str, Any] | None:
    return st.session_state.get("current_user")


def render_auth() -> None:
    auth_tab, register_tab = st.tabs(["Sign In", "Register"])

    with auth_tab:
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email", value="admin@copilot.local")
            password = st.text_input("Password", type="password", value="AdminDemo123!")
            submitted = st.form_submit_button("Sign in")
        if submitted:
            response = api_request("POST", "/auth/login", json_payload={"email": email, "password": password})
            if response.ok:
                payload = parse_response(response)
                set_auth(payload["access_token"], payload["user"])
                st.success("Signed in")
                st.rerun()
            else:
                st.error(parse_response(response).get("detail") or "Sign in failed")

    with register_tab:
        with st.form("register_form", clear_on_submit=False):
            email = st.text_input("New email", value="maintainer@copilot.local")
            password = st.text_input("New password", type="password", value="Maintainer123!")
            submitted = st.form_submit_button("Create account")
        if submitted:
            response = api_request("POST", "/auth/register", json_payload={"email": email, "password": password})
            if response.ok:
                payload = parse_response(response)
                set_auth(payload["access_token"], payload["user"])
                st.success("Account created")
                st.rerun()
            else:
                st.error(parse_response(response).get("detail") or "Registration failed")


def render_header() -> None:
    st.title("Maintainer's Copilot")
    st.caption("Authenticated chat, long-term memory, widget config, and issue tools in one place.")
    user = current_user()
    if user:
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.write(f"Signed in as `{user['email']}`")
        with col2:
            st.write(f"Role: `{user['role']}`")
        with col3:
            if st.button("Logout"):
                response = api_request("POST", "/auth/logout")
                if response.ok:
                    clear_auth()
                    st.success("Logged out")
                    st.rerun()
                else:
                    st.error(parse_response(response).get("detail") or "Logout failed")


def render_chat_tab() -> None:
    user = current_user()
    if not user:
        st.info("Sign in to use the authenticated chat.")
        return

    st.subheader("Chat")
    thread_id = st.text_input("Thread ID", key="thread_id")
    history = st.session_state["chat_messages"].setdefault(thread_id, [])

    for message in history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask about this repository")
    if prompt:
        history.append({"role": "user", "content": prompt})
        response = api_request(
            "POST",
            "/chat/",
            params={"message": prompt, "thread_id": thread_id},
        )
        if response.ok:
            payload = parse_response(response)
            answer = str(payload.get("response") or "")
        else:
            answer = parse_response(response).get("detail") or "Chat request failed"
        history.append({"role": "assistant", "content": answer})
        st.rerun()


def render_memory_tab() -> None:
    user = current_user()
    if not user:
        st.info("Sign in to inspect or write memory.")
        return

    st.subheader("Memory")
    response = api_request("GET", "/memory/")
    if response.ok:
        memories = parse_response(response)
    else:
        st.error(parse_response(response).get("detail") or "Could not load memory")
        memories = []

    with st.form("memory_form"):
        memory_type = st.selectbox("Memory type", ["semantic", "episodic", "procedural"], key="memory_type")
        memory_text = st.text_area("Memory content", key="memory_text", height=120)
        submitted = st.form_submit_button("Write memory")

    if submitted:
        write_response = api_request(
            "POST",
            "/memory/write",
            json_payload={"content": memory_text, "memory_type": memory_type, "metadata": {}},
        )
        if write_response.ok:
            st.success("Memory saved")
            st.rerun()
        else:
            st.error(parse_response(write_response).get("detail") or "Memory write failed")

    for memory in memories:
        with st.expander(f"{memory['type']} · {memory['id']}", expanded=False):
            st.write(memory["content"])


def render_widgets_tab() -> None:
    user = current_user()
    if not user:
        st.info("Sign in to manage widgets.")
        return

    st.subheader("Widget Configuration")
    widgets_response = api_request("GET", "/widgets/")
    widgets = parse_response(widgets_response) if widgets_response.ok else []

    if user["role"] == "admin":
        with st.form("widget_form"):
            public_id = st.text_input("Widget public ID", key="widget_public_id", placeholder="demo123")
            allowed_origins = st.text_input("Allowed origins", key="widget_origins", help="Comma-separated origins")
            greeting = st.text_input("Greeting", key="widget_greeting")
            submitted = st.form_submit_button("Create widget")
        if submitted:
            payload = {
                "public_id": public_id or None,
                "allowed_origins": [origin.strip() for origin in allowed_origins.split(",") if origin.strip()],
                "greeting": greeting,
                "enabled_tools": ["classify", "rag", "memory"],
                "theme": {"primary_color": "#0f766e", "position": "bottom-right"},
            }
            response = api_request("POST", "/widgets/", json_payload=payload)
            if response.ok:
                st.success("Widget saved")
                st.rerun()
            else:
                st.error(parse_response(response).get("detail") or "Widget save failed")

    for widget in widgets:
        with st.expander(f"{widget['public_id']} · {widget['greeting']}", expanded=widget["public_id"] == "demo123"):
            st.write("Allowed origins:", ", ".join(widget.get("allowed_origins") or []))
            st.write("Enabled tools:", ", ".join(widget.get("enabled_tools") or []))
            st.code(
                f'<script src="{API_URL}/widgets/widget.js?widget_id={widget["public_id"]}" data-widget-id="{widget["public_id"]}"></script>',
                language="html",
            )


def render_tools_tab() -> None:
    st.subheader("Model Tools")
    st.caption("Run the classifier, NER, and summarizer endpoints directly.")

    tool_model = st.selectbox("Classification model", ["rule", "fine", "few", "zero"], key="tool_model")
    tool_text = st.text_area(
        "Issue text",
        key="tool_text",
        height=160,
        placeholder="Paste a maintainer issue or thread here...",
    )

    if st.button("Classify issue"):
        response = model_request(
            "/classify",
            json_payload={"title": "Streamlit demo", "body": tool_text, "model": tool_model},
        )
        if response.ok:
            st.success(parse_response(response)["label"])
        else:
            st.error(parse_response(response).get("detail") or "Classification failed")

    if st.button("Extract entities"):
        response = model_request(
            "/ner",
            json_payload={"text": tool_text, "model": "rule"},
        )
        if response.ok:
            st.json(parse_response(response)["entities"])
        else:
            st.error(parse_response(response).get("detail") or "NER failed")

    if st.button("Summarize"):
        response = model_request(
            "/summarize",
            json_payload={"text": tool_text, "model": "rule", "max_sentences": 3},
        )
        if response.ok:
            st.write(parse_response(response)["summary"])
        else:
            st.error(parse_response(response).get("detail") or "Summarization failed")


def main() -> None:
    st.set_page_config(
        page_title="Maintainer's Copilot",
        page_icon="🛠️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    ensure_state()

    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top right, rgba(15, 118, 110, 0.14), transparent 25%),
                linear-gradient(180deg, #07111f 0%, #0f172a 100%);
            color: #e2e8f0;
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown("### Control Panel")
        st.write(f"API: `{API_URL}`")
        st.write(f"Model server: `{MODEL_SERVER_URL}`")
        health = api_request("GET", "/health")
        if health.ok:
            st.success("API healthy")
            st.json(parse_response(health))
        else:
            st.error("API health check failed")

        if current_user() is None:
            st.info("Use the sign-in form below the header to start a session.")
        else:
            st.write("Session active")

    render_header()
    if current_user() is None:
        render_auth()
        return

    chat_tab, memory_tab, widgets_tab, tools_tab = st.tabs(["Chat", "Memory", "Widgets", "Tools"])
    with chat_tab:
        render_chat_tab()
    with memory_tab:
        render_memory_tab()
    with widgets_tab:
        render_widgets_tab()
    with tools_tab:
        render_tools_tab()


if __name__ == "__main__":
    main()
