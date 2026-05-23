from __future__ import annotations

from collections import Counter
from html import escape
from typing import Any
import os

import requests
import streamlit as st
import streamlit.components.v1 as components


APP_TITLE = "Maintainer's Copilot"
APP_SUBTITLE = (
    "A clearer operator console for authenticated chat, long-term memory, "
    "widget setup, and model tools."
)

API_URL = os.getenv("API_URL", "http://localhost:8010").rstrip("/")
MODEL_SERVER_URL = os.getenv("MODEL_SERVER_URL", "http://localhost:8011").rstrip("/")
VAULT_ADDR = os.getenv("VAULT_ADDR", "http://localhost:8200").rstrip("/")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "copilot-attachments")
MINIO_MODEL_BUCKET = os.getenv("MINIO_MODEL_BUCKET", "copilot-model-artifacts")
MINIO_EVAL_BUCKET = os.getenv("MINIO_EVAL_BUCKET", "copilot-eval-artifacts")
MINIO_SNAPSHOT_BUCKET = os.getenv("MINIO_SNAPSHOT_BUCKET", "copilot-conversation-snapshots")

DEFAULT_THREAD_ID = "demo-thread"
DEFAULT_WIDGET_PUBLIC_ID = "demo123"
DEFAULT_WIDGET_GREETING = "How can I help?"
DEFAULT_WIDGET_ORIGINS = "http://localhost:3000"
HOST_DEMO_URL = "http://localhost:3000"

MEMORY_TYPES = ("semantic", "episodic", "procedural")
CHAT_PROMPTS = [
    ("Summarize the latest issue themes in this repository.", "Summarize"),
    ("Classify this issue and explain the label choice.", "Classify"),
    ("What long-term memory should I keep for this thread?", "Memory"),
]


def _response_from_error(url: str, error: Exception) -> requests.Response:
    response = requests.Response()
    response.status_code = 0
    response._content = str(error).encode("utf-8")
    response.encoding = "utf-8"
    response.url = url
    response.reason = str(error)
    return response


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
    try:
        return requests.request(
            method,
            url,
            headers=headers,
            json=json_payload,
            params=params,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return _response_from_error(url, exc)


def api_upload_request(
    path: str,
    *,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    timeout: int = 120,
) -> requests.Response:
    headers = {}
    token = st.session_state.get("auth_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{API_URL}{path}"
    try:
        return requests.post(
            url,
            headers=headers,
            data=data,
            files=files,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return _response_from_error(url, exc)


def model_request(
    path: str,
    *,
    json_payload: dict[str, Any],
    timeout: int = 120,
) -> requests.Response:
    url = f"{MODEL_SERVER_URL}{path}"
    try:
        return requests.post(url, json=json_payload, timeout=timeout)
    except requests.RequestException as exc:
        return _response_from_error(url, exc)


def parse_response(response: requests.Response) -> dict[str, Any]:
    try:
        return response.json()
    except Exception:
        return {"detail": response.text}


def ensure_state() -> None:
    st.session_state.setdefault("auth_token", "")
    st.session_state.setdefault("current_user", None)
    st.session_state.setdefault("chat_messages", {})
    st.session_state.setdefault("thread_id", DEFAULT_THREAD_ID)
    st.session_state.setdefault("tool_text", "")
    st.session_state.setdefault("tool_model", "fine")
    st.session_state.setdefault("tool_results", {})
    st.session_state.setdefault("memory_text", "")
    st.session_state.setdefault("memory_type", "semantic")
    st.session_state.setdefault("memory_filter", "all")
    st.session_state.setdefault("widget_public_id", "")
    st.session_state.setdefault("widget_origins", DEFAULT_WIDGET_ORIGINS)
    st.session_state.setdefault("widget_greeting", DEFAULT_WIDGET_GREETING)
    st.session_state.setdefault("widget_primary_color", "#0f766e")
    st.session_state.setdefault("widget_position", "bottom-right")
    st.session_state.setdefault("selected_widget", "")


def set_auth(token: str, user: dict[str, Any]) -> None:
    st.session_state["auth_token"] = token
    st.session_state["current_user"] = user


def clear_auth() -> None:
    st.session_state["auth_token"] = ""
    st.session_state["current_user"] = None


def current_user() -> dict[str, Any] | None:
    return st.session_state.get("current_user")


def parse_csv_list(raw: str) -> list[str]:
    cleaned: list[str] = []
    for item in raw.split(","):
        value = item.strip()
        if value and value not in cleaned:
            cleaned.append(value)
    return cleaned


def text_preview(text: str, limit: int = 120) -> str:
    sanitized = " ".join(str(text or "").split())
    if len(sanitized) <= limit:
        return sanitized
    return sanitized[: limit - 1].rstrip() + "..."


def format_bytes(value: int | float) -> str:
    size = float(value or 0)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024


def service_probe(url: str) -> dict[str, Any]:
    try:
        response = requests.get(url, timeout=5)
        payload: Any = None
        try:
            payload = response.json()
        except Exception:
            payload = None

        return {
            "ok": response.ok,
            "status_code": response.status_code,
            "payload": payload,
            "detail": response.text.strip(),
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "status_code": None,
            "payload": None,
            "detail": str(exc),
        }


def summarize_api_health(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "Ready" if payload else "Unavailable"

    parts = []
    if "vault_loaded" in payload:
        parts.append(f"Vault {'loaded' if payload.get('vault_loaded') else 'local'}")
    if "gemini_ready" in payload:
        parts.append(f"Gemini {'ready' if payload.get('gemini_ready') else 'off'}")
    if "voyage_ready" in payload:
        parts.append(f"Voyage {'ready' if payload.get('voyage_ready') else 'off'}")
    storage_buckets = payload.get("storage_buckets_ready")
    if isinstance(storage_buckets, dict) and storage_buckets:
        ready = sum(1 for value in storage_buckets.values() if value)
        parts.append(f"Storage {ready}/{len(storage_buckets)} ready")
    elif "minio_ready" in payload:
        parts.append(f"Storage {'ready' if payload.get('minio_ready') else 'off'}")
    return " | ".join(parts) if parts else "Ready"


def summarize_model_health(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "Ready" if payload else "Unavailable"

    parts = []
    if "fine_tuned_ready" in payload:
        parts.append(f"Fine-tuned {'ready' if payload.get('fine_tuned_ready') else 'off'}")
    if "model_artifacts_ready" in payload:
        parts.append(f"Artifacts {'ready' if payload.get('model_artifacts_ready') else 'off'}")
    if "gemini_ready" in payload:
        parts.append(f"Gemini {'ready' if payload.get('gemini_ready') else 'off'}")
    if "gemini_model" in payload:
        parts.append(str(payload.get("gemini_model")))
    return " | ".join(parts) if parts else "Ready"


def summarize_vault_health(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "Dev server reachable" if payload else "Unavailable"

    parts = []
    if "initialized" in payload:
        parts.append(f"Initialized: {'yes' if payload.get('initialized') else 'no'}")
    if "sealed" in payload:
        parts.append(f"Sealed: {'yes' if payload.get('sealed') else 'no'}")
    if "version" in payload:
        parts.append(f"Version: {payload.get('version')}")
    return " | ".join(parts) if parts else "Dev server reachable"


def set_tool_result(name: str, payload: Any) -> None:
    results = dict(st.session_state.get("tool_results") or {})
    results[name] = payload
    st.session_state["tool_results"] = results


def render_style() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(15, 118, 110, 0.10), transparent 30%),
                radial-gradient(circle at top right, rgba(59, 130, 246, 0.10), transparent 28%),
                linear-gradient(180deg, #f8fafc 0%, #edf2f7 100%);
            color: #0f172a;
        }
        .main .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
        }
        section[data-testid="stSidebar"] * {
            color: #e2e8f0;
        }
        section[data-testid="stSidebar"] code,
        section[data-testid="stSidebar"] pre {
            background: rgba(255, 255, 255, 0.08) !important;
            color: #f8fafc !important;
        }
        .mc-hero {
            display: grid;
            grid-template-columns: minmax(0, 1.7fr) minmax(280px, 0.9fr);
            gap: 1rem;
            align-items: stretch;
            margin-bottom: 1rem;
        }
        .mc-hero-copy,
        .mc-hero-side,
        .mc-stat-card,
        .mc-callout {
            border: 1px solid rgba(15, 23, 42, 0.10);
            border-radius: 22px;
            background: rgba(255, 255, 255, 0.88);
            box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
            backdrop-filter: blur(12px);
        }
        .mc-hero-copy {
            padding: 1.4rem 1.5rem;
            background: linear-gradient(135deg, rgba(15, 118, 110, 0.12), rgba(255, 255, 255, 0.96));
        }
        .mc-kicker {
            margin: 0 0 0.45rem;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.18em;
            color: #0f766e;
            font-weight: 800;
        }
        .mc-hero-copy h1 {
            margin: 0;
            font-size: clamp(2rem, 4vw, 3.1rem);
            line-height: 1.02;
            color: #0f172a;
        }
        .mc-hero-subtitle {
            margin-top: 0.8rem;
            max-width: 64ch;
            font-size: 1rem;
            line-height: 1.65;
            color: #334155;
        }
        .mc-hero-side {
            padding: 1.2rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            gap: 0.85rem;
        }
        .mc-side-title,
        .mc-stat-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            color: #64748b;
            font-weight: 800;
        }
        .mc-side-value,
        .mc-stat-value {
            margin-top: 0.35rem;
            font-size: 1.16rem;
            font-weight: 800;
            color: #0f172a;
        }
        .mc-side-copy,
        .mc-stat-copy {
            margin-top: 0.45rem;
            font-size: 0.9rem;
            line-height: 1.5;
            color: #475569;
        }
        .mc-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 1rem;
        }
        .mc-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.4rem 0.7rem;
            border-radius: 999px;
            background: rgba(15, 118, 110, 0.08);
            color: #0f766e;
            font-size: 0.8rem;
            font-weight: 800;
        }
        .mc-chip--muted {
            background: rgba(15, 23, 42, 0.06);
            color: #334155;
        }
        .mc-stat-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.9rem;
            margin: 0 0 1rem;
        }
        .mc-stat-card {
            padding: 1rem 1rem 0.95rem;
        }
        .mc-stat-card--ok {
            border-color: rgba(34, 197, 94, 0.24);
        }
        .mc-stat-card--warn {
            border-color: rgba(245, 158, 11, 0.24);
        }
        .mc-panel {
            padding: 1rem;
            border-radius: 20px;
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid rgba(15, 23, 42, 0.10);
            box-shadow: 0 14px 30px rgba(15, 23, 42, 0.06);
        }
        .mc-callout {
            padding: 0.95rem 1rem;
            background: linear-gradient(135deg, rgba(15, 118, 110, 0.08), rgba(255, 255, 255, 0.92));
            color: #0f172a;
        }
        .mc-callout strong {
            display: block;
            margin-bottom: 0.25rem;
        }
        .mc-empty-state {
            padding: 1rem;
            border-radius: 18px;
            border: 1px dashed rgba(15, 23, 42, 0.15);
            background: rgba(255, 255, 255, 0.7);
            color: #475569;
        }
        .mc-result {
            margin-top: 0.75rem;
        }
        .mc-result h4 {
            margin: 0 0 0.4rem;
            color: #0f172a;
        }
        .mc-dataframe {
            margin-top: 0.75rem;
        }
        @media (max-width: 1100px) {
            .mc-hero,
            .mc-stat-grid {
                grid-template-columns: 1fr 1fr;
            }
        }
        @media (max-width: 720px) {
            .mc-hero,
            .mc-stat-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_chip_row(items: list[str], *, muted: bool = False) -> None:
    if not items:
        return

    classes = "mc-chip mc-chip--muted" if muted else "mc-chip"
    chips = "".join(f'<span class="{classes}">{escape(item)}</span>' for item in items if item)
    st.markdown(f'<div class="mc-chip-row">{chips}</div>', unsafe_allow_html=True)


def render_status_card(label: str, value: str, detail: str, tone: str = "neutral") -> None:
    st.markdown(
        f"""
        <div class="mc-stat-card mc-stat-card--{escape(tone)}">
            <div class="mc-stat-label">{escape(label)}</div>
            <div class="mc-stat-value">{escape(value)}</div>
            <div class="mc-stat-copy">{escape(detail)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_widget_preview(public_id: str) -> None:
    preview_url = f"{HOST_DEMO_URL}/?widget_id={public_id}"
    st.markdown(
        """
        <div class="mc-callout">
            <strong>Live host preview</strong>
            The widget below runs inside the demo host page, so you can see the floating assistant in a real app shell.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("The frame uses the same public widget bundle that the host page serves in production.")
    components.iframe(preview_url, height=980, scrolling=False)


def render_hero(healths: dict[str, dict[str, Any]]) -> None:
    user = current_user()
    session_value = f"{user['email']}" if user else "Visitor mode"
    session_detail = (
        f"Role: {user['role']}"
        if user
        else "Sign in to unlock chat, memory, widgets, and tools."
    )

    st.markdown(
        f"""
        <div class="mc-hero">
            <div class="mc-hero-copy">
                <div class="mc-kicker">Operator console</div>
                <h1>{escape(APP_TITLE)}</h1>
                <p class="mc-hero-subtitle">{escape(APP_SUBTITLE)}</p>
                <div class="mc-chip-row">
                    <span class="mc-chip">Authenticated chat</span>
                    <span class="mc-chip">Long-term memory</span>
                    <span class="mc-chip">Widget setup</span>
                    <span class="mc-chip">Model tools</span>
                </div>
            </div>
            <div class="mc-hero-side">
                <div>
                    <div class="mc-side-title">Session</div>
                    <div class="mc-side-value">{escape(session_value)}</div>
                    <div class="mc-side-copy">{escape(session_detail)}</div>
                </div>
                <div class="mc-side-copy">
                    Use the sidebar for launch commands and service health, then sign in to access the workspace.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    api_health = healths["api"]
    model_health = healths["model"]
    vault_health = healths["vault"]
    session_health = {
        "ok": bool(user),
        "label": "Session",
        "value": "Active" if user else "Visitor",
        "detail": f"{user['email']} | {user['role']}" if user else "Sign in to continue",
    }

    cards = [
        (
            "API",
            "Healthy" if api_health["ok"] else "Unavailable",
            summarize_api_health(api_health.get("payload")),
            "ok" if api_health["ok"] else "warn",
        ),
        (
            "Model server",
            "Healthy" if model_health["ok"] else "Unavailable",
            summarize_model_health(model_health.get("payload")),
            "ok" if model_health["ok"] else "warn",
        ),
        (
            "Vault",
            "Healthy" if vault_health["ok"] else "Unavailable",
            summarize_vault_health(vault_health.get("payload")),
            "ok" if vault_health["ok"] else "warn",
        ),
        (
            session_health["label"],
            session_health["value"],
            session_health["detail"],
            "ok" if session_health["ok"] else "warn",
        ),
    ]

    columns = st.columns(4)
    for column, card in zip(columns, cards):
        with column:
            render_status_card(*card)


def render_auth() -> None:
    st.markdown(
        """
        <div class="mc-callout">
            <strong>Sign in to unlock the workspace.</strong>
            Use the demo account for a quick walkthrough or register a new user if you want a fresh session.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("#### Sign in")
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email", value="admin@copilot.local")
            password = st.text_input("Password", type="password", value="AdminDemo123!")
            submitted = st.form_submit_button("Sign in", use_container_width=True)
        if submitted:
            with st.spinner("Signing in..."):
                response = api_request("POST", "/auth/login", json_payload={"email": email, "password": password})
            if response.ok:
                payload = parse_response(response)
                set_auth(payload["access_token"], payload["user"])
                st.success("Signed in successfully.")
                st.rerun()
            else:
                st.error(parse_response(response).get("detail") or "Sign in failed")

    with right:
        st.markdown("#### Register")
        with st.form("register_form", clear_on_submit=False):
            email = st.text_input("New email", value="maintainer@copilot.local")
            password = st.text_input("New password", type="password", value="Maintainer123!")
            submitted = st.form_submit_button("Create account", use_container_width=True)
        if submitted:
            with st.spinner("Creating account..."):
                response = api_request("POST", "/auth/register", json_payload={"email": email, "password": password})
            if response.ok:
                payload = parse_response(response)
                set_auth(payload["access_token"], payload["user"])
                st.success("Account created.")
                st.rerun()
            else:
                st.error(parse_response(response).get("detail") or "Registration failed")

    st.caption("Demo credentials: admin@copilot.local / AdminDemo123!")


def submit_chat_message(thread_id: str, prompt: str) -> None:
    prompt = prompt.strip()
    if not prompt or not current_user():
        return

    history = st.session_state["chat_messages"].setdefault(thread_id, [])
    history.append({"role": "user", "content": prompt})

    with st.spinner("Thinking..."):
        response = api_request(
            "POST",
            "/chat/",
            params={"message": prompt, "thread_id": thread_id},
        )

    if response.ok:
        payload = parse_response(response)
        history.append(
            {
                "role": "assistant",
                "content": str(payload.get("response") or ""),
                "meta": {
                    "provider": payload.get("llm_provider") or "local",
                    "usedFallback": bool(payload.get("used_fallback")),
                    "fallbackReason": payload.get("fallback_reason"),
                    "retrievedDocIds": payload.get("retrieved_doc_ids") or [],
                },
            }
        )
    else:
        history.append(
            {
                "role": "assistant",
                "content": parse_response(response).get("detail") or "Chat request failed",
                "meta": {
                    "provider": "local",
                    "usedFallback": True,
                    "retrievedDocIds": [],
                },
            }
        )

    st.rerun()


def render_chat_tab() -> None:
    user = current_user()
    if not user:
        st.info("Sign in to use the authenticated chat.")
        return

    left, right = st.columns([2.1, 0.95], gap="large")

    with left:
        st.markdown("#### Conversation")
        st.caption("Each thread keeps its own message history.")
        thread_id = (st.text_input("Thread ID", key="thread_id") or DEFAULT_THREAD_ID).strip() or DEFAULT_THREAD_ID
        history = st.session_state["chat_messages"].setdefault(thread_id, [])

        control_left, control_right = st.columns([1, 1])
        with control_left:
            if st.button("Reset thread", use_container_width=True):
                st.session_state["chat_messages"][thread_id] = []
                st.rerun()
        with control_right:
            st.caption(f"{len(history)} message(s)")

        if not history:
            st.markdown(
                """
                <div class="mc-empty-state">
                    Start with a question or pick one of the suggested prompts on the right.
                </div>
                """,
                unsafe_allow_html=True,
            )

        for message in history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                meta = message.get("meta") or {}
                if meta:
                    provider = str(meta.get("provider") or "local")
                    chips = [
                        f"Provider: {provider}",
                        "Fallback" if meta.get("usedFallback") else "Primary path",
                    ]
                    if meta.get("fallbackReason"):
                        chips.append(f"Reason: {meta.get('fallbackReason')}")
                    retrieved = meta.get("retrievedDocIds") or []
                    chips.append(
                        f"{len(retrieved)} source{'s' if len(retrieved) != 1 else ''}"
                        if retrieved
                        else "No sources"
                    )
                    render_chip_row(chips, muted=True)

        prompt = st.chat_input("Ask about this repository")
        if prompt:
            submit_chat_message(thread_id, prompt)

    with right:
        st.markdown("#### Quick prompts")
        st.caption("The assistant surfaces provider and retrieval metadata so fallback usage stays visible.")

        for index, (prompt, label) in enumerate(CHAT_PROMPTS):
            if st.button(label, key=f"chat_prompt_{index}", use_container_width=True):
                submit_chat_message(thread_id, prompt)

        st.markdown("#### Tips")
        st.markdown(
            """
            <div class="mc-callout">
                <strong>Best results</strong>
                Mention an issue title, a label, or a specific thread topic so the assistant can use memory and retrieved context.
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_memory_tab() -> None:
    user = current_user()
    if not user:
        st.info("Sign in to inspect or write memory.")
        return

    response = api_request("GET", "/memory/")
    if response.ok:
        memories = parse_response(response)
    else:
        st.error(parse_response(response).get("detail") or "Could not load memory")
        memories = []

    counts = Counter(str(memory.get("type") or "unknown") for memory in memories)
    metric_cols = st.columns(4)
    metric_data = [
        ("Total", str(len(memories)), "Stored memory entries", "ok"),
        ("Semantic", str(counts.get("semantic", 0)), "Facts and durable notes", "neutral"),
        ("Episodic", str(counts.get("episodic", 0)), "Events and thread history", "neutral"),
        ("Procedural", str(counts.get("procedural", 0)), "How-to guidance", "neutral"),
    ]
    for column, card in zip(metric_cols, metric_data):
        with column:
            render_status_card(*card)

    st.write("")
    left, right = st.columns([1, 1.2], gap="large")

    with left:
        st.markdown("#### Write memory")
        st.caption("Use semantic memory for facts, episodic memory for events, and procedural memory for how-to guidance.")
        with st.form("memory_form"):
            memory_type = st.selectbox("Memory type", list(MEMORY_TYPES), key="memory_type")
            memory_text = st.text_area(
                "Memory content",
                key="memory_text",
                height=160,
                placeholder="Write a durable note or incident summary...",
            )
            submitted = st.form_submit_button("Store memory", use_container_width=True)

        if submitted:
            if not memory_text.strip():
                st.warning("Add content before storing a memory.")
            else:
                with st.spinner("Saving memory..."):
                    write_response = api_request(
                        "POST",
                        "/memory/write",
                        json_payload={"content": memory_text, "memory_type": memory_type, "metadata": {}},
                    )
                if write_response.ok:
                    st.success("Memory saved.")
                    st.rerun()
                else:
                    st.error(parse_response(write_response).get("detail") or "Memory write failed")

    with right:
        st.markdown("#### Inventory")
        filter_options = ["all", *MEMORY_TYPES]
        memory_filter = st.selectbox("Filter", filter_options, key="memory_filter")
        filtered_memories = [
            memory
            for memory in memories
            if memory_filter == "all" or str(memory.get("type")) == memory_filter
        ]

        if not filtered_memories:
            st.info("No memories match the current filter.")
            return

        summary_rows = [
            {
                "Type": memory.get("type"),
                "ID": memory.get("id"),
                "Preview": text_preview(memory.get("content") or "", 100),
            }
            for memory in filtered_memories
        ]
        st.dataframe(summary_rows, use_container_width=True, hide_index=True)

        for memory in filtered_memories[:8]:
            with st.expander(f"{memory.get('type', 'memory')} | {memory.get('id', '')}", expanded=False):
                st.write(memory.get("content"))
                metadata = memory.get("metadata") or {}
                if metadata:
                    st.json(metadata)


def render_widgets_tab() -> None:
    user = current_user()
    if not user:
        st.info("Sign in to manage widgets.")
        return

    widgets_response = api_request("GET", "/widgets/")
    if widgets_response.ok:
        widgets = parse_response(widgets_response)
    else:
        st.error(parse_response(widgets_response).get("detail") or "Could not load widgets")
        widgets = []

    total_allowed_origins = sum(len(widget.get("allowed_origins") or []) for widget in widgets)
    widget_metrics = st.columns(4)
    widget_metric_data = [
        ("Widgets", str(len(widgets)), "Available widget configs", "ok"),
        ("Allowed origins", str(total_allowed_origins), "Origin restrictions across widgets", "neutral"),
        ("Role", str(user.get("role") or "unknown"), "Current session privileges", "neutral"),
        ("Selected", st.session_state.get("selected_widget") or "none", "Preview target", "neutral"),
    ]
    for column, card in zip(widget_metrics, widget_metric_data):
        with column:
            render_status_card(*card)

    st.write("")
    left, right = st.columns([1, 1.2], gap="large")

    with left:
        if user.get("role") == "admin":
            st.markdown("#### Create widget")
            st.caption("Embed the widget with one script tag and lock it to approved origins.")
            with st.form("widget_form"):
                public_id = st.text_input("Widget public ID", key="widget_public_id", placeholder="demo123")
                allowed_origins = st.text_input(
                    "Allowed origins",
                    key="widget_origins",
                    help="Comma-separated origins such as http://localhost:3000, http://127.0.0.1:3000",
                )
                greeting = st.text_input("Greeting", key="widget_greeting")
                accent_color = st.color_picker("Accent color", key="widget_primary_color")
                position = st.selectbox(
                    "Launcher position",
                    ["bottom-right", "bottom-left"],
                    key="widget_position",
                )
                enabled_tools = st.multiselect(
                    "Enabled tools",
                    ["classify", "rag", "memory"],
                    default=["classify", "rag", "memory"],
                )
                submitted = st.form_submit_button("Save widget", use_container_width=True)

            if submitted:
                payload = {
                    "public_id": public_id or None,
                    "allowed_origins": parse_csv_list(allowed_origins),
                    "greeting": greeting,
                    "enabled_tools": enabled_tools,
                    "theme": {"primary_color": accent_color, "position": position},
                }
                with st.spinner("Saving widget..."):
                    response = api_request("POST", "/widgets/", json_payload=payload)
                if response.ok:
                    created = parse_response(response)
                    st.session_state["selected_widget"] = created.get("public_id") or DEFAULT_WIDGET_PUBLIC_ID
                    st.success("Widget saved.")
                    st.rerun()
                else:
                    st.error(parse_response(response).get("detail") or "Widget save failed")
        else:
            st.markdown(
                """
                <div class="mc-callout">
                    <strong>Read-only access</strong>
                    You can review widget embeds here, but only admins can create or update widget configurations.
                </div>
                """,
                unsafe_allow_html=True,
            )

    with right:
        st.markdown("#### Preview and embed")
        st.caption("Copy the script tag, or use the live host preview below.")

        if not widgets:
            st.info("No widgets yet. Create one on the left to generate an embed snippet.")
        else:
            widget_ids = [widget.get("public_id") for widget in widgets if widget.get("public_id")]
            if not widget_ids:
                st.info("Widgets are loaded, but none have a public ID yet.")
                return
            if st.session_state.get("selected_widget") not in widget_ids:
                st.session_state["selected_widget"] = widget_ids[0]
            default_index = 0
            selected_public_id = st.selectbox(
                "Preview widget",
                widget_ids,
                index=default_index,
                key="selected_widget",
            )
            selected = next(
                (widget for widget in widgets if widget.get("public_id") == selected_public_id),
                widgets[0],
            )
            origins = selected.get("allowed_origins") or []
            tools = selected.get("enabled_tools") or []

            st.markdown(
                """
                <div class="mc-callout">
                    <strong>Widget profile</strong>
                    Review the greeting, origin allow-list, and tool chips before pasting the embed snippet into your host app.
                </div>
                """,
                unsafe_allow_html=True,
            )
            render_chip_row([f"Position: {selected.get('theme', {}).get('position', 'bottom-right')}"])
            render_chip_row([f"Tools: {', '.join(tools) or 'none'}"], muted=True)
            render_chip_row([f"Origins: {len(origins)}"], muted=True)
            st.write("")
            st.caption(f"Greeting: {selected.get('greeting')}")
            st.code(
                f'<script src="{API_URL}/widgets/widget.js?widget_id={selected_public_id}" '
                f'data-widget-id="{selected_public_id}"></script>',
                language="html",
            )
            if origins:
                st.caption(f"Allowed origins: {', '.join(origins)}")

            st.write("")
            render_widget_preview(selected_public_id)

        if widgets:
            st.write("")
            st.markdown("#### All widgets")
            summary_rows = [
                {
                    "Public ID": widget.get("public_id"),
                    "Greeting": widget.get("greeting"),
                    "Origins": len(widget.get("allowed_origins") or []),
                    "Tools": ", ".join(widget.get("enabled_tools") or []),
                }
                for widget in widgets
            ]
            st.dataframe(summary_rows, use_container_width=True, hide_index=True)


def render_attachments_tab() -> None:
    user = current_user()
    if not user:
        st.info("Sign in to upload or browse attachments.")
        return

    attachments_response = api_request("GET", "/attachments/")
    if attachments_response.ok:
        attachments = parse_response(attachments_response)
    else:
        st.error(parse_response(attachments_response).get("detail") or "Could not load attachments")
        attachments = []

    total_size = sum(int(attachment.get("size_bytes") or 0) for attachment in attachments)
    attachment_metrics = st.columns(4)
    attachment_metric_data = [
        ("Files", str(len(attachments)), "Objects stored in MinIO", "ok"),
        ("Total size", format_bytes(total_size), "Combined stored bytes", "neutral"),
        ("Bucket", MINIO_BUCKET, "Target MinIO bucket", "neutral"),
        ("Role", str(user.get("role") or "unknown"), "Current session privileges", "neutral"),
    ]
    for column, card in zip(attachment_metrics, attachment_metric_data):
        with column:
            render_status_card(*card)

    st.write("")
    left, right = st.columns([1, 1.2], gap="large")

    with left:
        st.markdown("#### Upload file")
        st.caption("Files are stored in MinIO and indexed in Postgres with owner metadata.")
        with st.form("attachment_form", clear_on_submit=True):
            upload = st.file_uploader("Attachment", key="attachment_upload")
            notes = st.text_area(
                "Context note",
                key="attachment_notes",
                placeholder="Optional note for your future self or the next maintainer...",
                height=120,
            )
            submitted = st.form_submit_button("Store file", use_container_width=True)

        if submitted:
            if upload is None:
                st.warning("Choose a file before uploading.")
            else:
                with st.spinner("Uploading attachment..."):
                    response = api_upload_request(
                        "/attachments/",
                        data={"notes": notes},
                        files={
                            "file": (
                                upload.name,
                                upload.getvalue(),
                                upload.type or "application/octet-stream",
                            )
                        },
                    )
                if response.ok:
                    st.success("Attachment stored.")
                    st.rerun()
                else:
                    st.error(parse_response(response).get("detail") or "Attachment upload failed")

    with right:
        st.markdown("#### Stored files")
        st.caption("Download files back through the API or inspect their MinIO metadata below.")

        if not attachments:
            st.info("No attachments yet. Upload a file to populate the MinIO bucket.")
            return

        summary_rows = [
            {
                "Filename": attachment.get("filename"),
                "Size": format_bytes(int(attachment.get("size_bytes") or 0)),
                "Bucket": attachment.get("bucket_name"),
                "Notes": text_preview(attachment.get("notes") or "", 64) if attachment.get("notes") else "",
            }
            for attachment in attachments
        ]
        st.dataframe(summary_rows, use_container_width=True, hide_index=True)

        for attachment in attachments[:8]:
            attachment_id = attachment.get("id")
            with st.expander(f"{attachment.get('filename', 'attachment')} | {format_bytes(int(attachment.get('size_bytes') or 0))}", expanded=False):
                render_chip_row(
                    [
                        f"Bucket: {attachment.get('bucket_name')}",
                        f"Type: {attachment.get('content_type') or 'application/octet-stream'}",
                        f"Uploaded: {attachment.get('created_at') or 'unknown'}",
                    ],
                    muted=True,
                )
                if attachment.get("notes"):
                    st.write(attachment.get("notes"))
                st.caption(f"SHA256: {attachment.get('sha256')}")
                download_response = api_request("GET", f"/attachments/{attachment_id}/download")
                if download_response.ok:
                    st.download_button(
                        "Download file",
                        data=download_response.content,
                        file_name=str(attachment.get("filename") or "attachment"),
                        mime=str(attachment.get("content_type") or "application/octet-stream"),
                        key=f"download_{attachment_id}",
                        use_container_width=True,
                    )
                else:
                    st.error(parse_response(download_response).get("detail") or "Download failed")


def render_tools_tab() -> None:
    user = current_user()
    if not user:
        st.info("Sign in to run the model tools.")
        return

    st.markdown("#### Model tools")
    st.caption(
        "The classifier includes fallback metadata so you can tell when local logic handled a request."
    )

    model_choice = st.radio(
        "Classification model",
        ["fine", "rule", "few", "zero"],
        horizontal=True,
        key="tool_model",
    )
    issue_text = st.text_area(
        "Issue text",
        key="tool_text",
        height=180,
        placeholder="Paste an issue title, body, or maintainer note...",
    )

    classify_tab, ner_tab, summary_tab = st.tabs(["Classify", "NER", "Summarize"])

    with classify_tab:
        st.caption("Recommended for the demo: fine.")
        if st.button("Run classification", key="run_classification"):
            if not issue_text.strip():
                st.warning("Add text before running classification.")
            else:
                with st.spinner("Classifying..."):
                    response = model_request(
                        "/classify",
                        json_payload={"title": "Streamlit demo", "body": issue_text, "model": model_choice},
                    )
                if response.ok:
                    payload = parse_response(response)
                    set_tool_result("classify", payload)
                else:
                    payload = {"error": parse_response(response).get("detail") or "Classification failed"}
                    set_tool_result("classify", payload)

        result = st.session_state.get("tool_results", {}).get("classify")
        if result:
            if result.get("error"):
                st.error(result["error"])
            else:
                st.markdown(
                    f"""
                    <div class="mc-result">
                        <h4>Classification result</h4>
                        <div class="mc-callout">
                            <strong>Label: {escape(str(result.get('label') or 'unknown'))}</strong>
                            Source: {escape(str(result.get('classifier_source') or 'unknown'))}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                render_chip_row(
                    [
                        f"Fallback: {'yes' if result.get('used_fallback') else 'no'}",
                        f"Reason: {result.get('fallback_reason') or 'none'}",
                    ],
                    muted=True,
                )
                with st.expander("Raw classification response"):
                    st.json(result)

    with ner_tab:
        if st.button("Run NER", key="run_ner"):
            if not issue_text.strip():
                st.warning("Add text before running NER.")
            else:
                with st.spinner("Extracting entities..."):
                    response = model_request("/ner", json_payload={"text": issue_text, "model": "rule"})
                if response.ok:
                    payload = parse_response(response)
                    set_tool_result("ner", payload)
                else:
                    payload = {"error": parse_response(response).get("detail") or "NER failed"}
                    set_tool_result("ner", payload)

        result = st.session_state.get("tool_results", {}).get("ner")
        if result:
            if result.get("error"):
                st.error(result["error"])
            else:
                entities = result.get("entities") or []
                if entities:
                    st.dataframe(entities, use_container_width=True, hide_index=True)
                else:
                    st.info("No entities found.")
                with st.expander("Raw NER response"):
                    st.json(result)

    with summary_tab:
        if st.button("Run summarization", key="run_summary"):
            if not issue_text.strip():
                st.warning("Add text before summarizing.")
            else:
                with st.spinner("Summarizing..."):
                    response = model_request(
                        "/summarize",
                        json_payload={"text": issue_text, "model": "rule", "max_sentences": 3},
                    )
                if response.ok:
                    payload = parse_response(response)
                    set_tool_result("summary", payload)
                else:
                    payload = {"error": parse_response(response).get("detail") or "Summarization failed"}
                    set_tool_result("summary", payload)

        result = st.session_state.get("tool_results", {}).get("summary")
        if result:
            if result.get("error"):
                st.error(result["error"])
            else:
                st.markdown(
                    f"""
                    <div class="mc-result">
                        <h4>Summary</h4>
                        <div class="mc-callout">
                            {escape(str(result.get('summary') or ''))}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                with st.expander("Raw summary response"):
                    st.json(result)


def render_sidebar(healths: dict[str, dict[str, Any]]) -> None:
    user = current_user()

    st.sidebar.markdown("### Launch")
    st.sidebar.code(
        "powershell -ExecutionPolicy Bypass -File scripts/run_full_stack.ps1",
        language="powershell",
    )
    st.sidebar.caption(
        "Starts Postgres, Redis, Minio, Vault, pgAdmin, Jaeger, API, model server, Streamlit, widget, and host."
    )

    st.sidebar.markdown("### Local UI")
    st.sidebar.code(
        "streamlit run chatbot_streamlit/app.py --server.address 0.0.0.0 --server.port 8501",
        language="powershell",
    )
    st.sidebar.code("cd widget; npm install; npm run dev", language="powershell")
    st.sidebar.caption(
        "Use the widget dev server for UI work and the host demo at http://localhost:3000 for the embedded preview."
    )
    st.sidebar.markdown("### Storage")
    st.sidebar.caption("MinIO console: http://localhost:9001")
    st.sidebar.caption(f"Bucket: {MINIO_BUCKET}")
    st.sidebar.caption(f"Model artifacts: {MINIO_MODEL_BUCKET}")
    st.sidebar.caption(f"Eval reports: {MINIO_EVAL_BUCKET}")
    st.sidebar.caption(f"Snapshots: {MINIO_SNAPSHOT_BUCKET}")

    st.sidebar.markdown("### Health")
    st.sidebar.metric("API", "Healthy" if healths["api"]["ok"] else "Unavailable")
    st.sidebar.caption(summarize_api_health(healths["api"].get("payload")))
    st.sidebar.metric("Model", "Healthy" if healths["model"]["ok"] else "Unavailable")
    st.sidebar.caption(summarize_model_health(healths["model"].get("payload")))
    st.sidebar.metric("Vault", "Healthy" if healths["vault"]["ok"] else "Unavailable")
    st.sidebar.caption(summarize_vault_health(healths["vault"].get("payload")))

    st.sidebar.markdown("### Session")
    if user:
        st.sidebar.write(f"Signed in as `{user['email']}`")
        st.sidebar.write(f"Role: `{user['role']}`")
        if st.sidebar.button("Log out"):
            with st.spinner("Logging out..."):
                response = api_request("POST", "/auth/logout")
            if response.ok:
                clear_auth()
                st.success("Logged out.")
                st.rerun()
            else:
                st.sidebar.error(parse_response(response).get("detail") or "Logout failed")
    else:
        st.sidebar.info("Sign in in the main view to unlock chat, memory, widgets, and tools.")

    st.sidebar.markdown("### Endpoints")
    st.sidebar.markdown(
        f"""
- API: `{API_URL}`
- Model server: `{MODEL_SERVER_URL}`
- Vault: `{VAULT_ADDR}`
"""
    )


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="MC",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    ensure_state()
    render_style()

    healths = {
        "api": service_probe(f"{API_URL}/health"),
        "model": service_probe(f"{MODEL_SERVER_URL}/health"),
        "vault": service_probe(
            f"{VAULT_ADDR}/v1/sys/health?standbyok=true&sealedcode=503&uninitcode=503"
        ),
    }

    render_sidebar(healths)
    render_hero(healths)

    if current_user() is None:
        render_auth()
        return

    chat_tab, memory_tab, widgets_tab, attachments_tab, tools_tab = st.tabs(
        ["Chat", "Memory", "Widgets", "Attachments", "Tools"]
    )
    with chat_tab:
        render_chat_tab()
    with memory_tab:
        render_memory_tab()
    with widgets_tab:
        render_widgets_tab()
    with attachments_tab:
        render_attachments_tab()
    with tools_tab:
        render_tools_tab()


if __name__ == "__main__":
    main()
