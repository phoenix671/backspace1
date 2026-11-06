import importlib
import streamlit as st
import auth
import theme
import api_client
import solve_view

importlib.reload(theme)
theme.apply_teacher_theme()

if auth.current_role() != "teacher":
    st.error("You are not allowed to view this page.")
    st.stop()

theme.page_header(
    "Class status",
    "See which topics students are struggling with and inspect recent student queries.",
)

ok_cls, cls_data = auth.safe_call(
    api_client.list_teacher_classes,
    spinner="Loading classes...",
)
if not ok_cls:
    st.stop()

classes = cls_data.get("classes", [])
if not classes:
    st.info("No classes assigned to you.")
    st.stop()

class_map = {f"{c['name']} ({c['subject']})": c["class_id"] for c in classes}
default_cid = st.session_state.get("teacher_class_id")
labels = list(class_map.keys())
default_idx = 0
for i, lbl in enumerate(labels):
    if class_map[lbl] == default_cid:
        default_idx = i
        break

selected_label = st.selectbox("Select class", options=labels, index=default_idx)
class_id = class_map[selected_label]
st.session_state["teacher_class_id"] = class_id

ok, status_data = auth.safe_call(
    api_client.get_class_status,
    class_id,
    spinner="Loading class status...",
)
if not ok:
    st.stop()

st.subheader(f"Struggling topics ({status_data.get('subject', '')})")
struggling = status_data.get("struggling_topics", [])
if not struggling:
    st.info("No struggling topics identified yet.")
else:
    chart = {item["topic"]: item["struggling_students"] for item in struggling}
    st.bar_chart(chart)
    for item in struggling:
        with st.container(border=True):
            st.markdown(
                f"**{item['topic']}** — **{item['struggling_students']} / {item['total_students']}** students struggling"
            )
            st.caption(
                "Most common mistake: "
                + solve_view.pretty_mistake(item.get("top_mistake_type", ""))
            )

st.divider()
st.subheader("Recent student queries")
queries = status_data.get("recent_queries", [])
if not queries:
    st.info("No student queries recorded yet.")
else:
    for q in queries:
        with st.container(border=True):
            st.markdown(
                f"**{q['student']['name']}** · Topic: **{q['topic']}** (`{q['source']}`)"
            )
            st.write(q["question_text"])
            mistake_str = (
                solve_view.pretty_mistake(q["last_mistake_type"])
                if q.get("last_mistake_type")
                else "None"
            )
            st.caption(
                f"Status: `{q['status']}` · Attempts used: {q['attempts_used']} · Last mistake: {mistake_str} · At: {q['at']}"
            )
