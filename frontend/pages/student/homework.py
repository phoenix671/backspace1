import streamlit as st
import auth
import theme
import api_client

theme.apply_theme()

if auth.current_role() != "student":
    st.error("You are not allowed to view this page.")
    st.stop()

theme.page_header("Homework timeline", "View your assigned homework and start solving.")

ok, data = auth.safe_call(
    api_client.list_student_homework,
    spinner="Loading your homework...",
)
if not ok:
    st.stop()

homework_list = data.get("homework", [])
if not homework_list:
    st.info("No homework assigned yet.")
    st.stop()

status_labels = {
    "not_started": "Not started",
    "in_progress": "In progress",
    "completed": "Completed",
}

for hw in homework_list:
    hw_id = hw["homework_id"]
    status = hw.get("status", "not_started")
    with st.container(border=True):
        col_info, col_action = st.columns([4, 1])
        with col_info:
            st.markdown(f"### {hw['title']}")
            st.caption(
                f"{hw['subject']} · Topic: **{hw['topic']}** · Teacher: {hw['teacher_name']}"
            )
            due_text = hw.get("due_at") or "No due date"
            st.write(
                f"Assigned: `{hw['assigned_at']}` · Due: `{due_text}` · Status: **{status_labels.get(status, status)}**"
            )
        with col_action:
            btn_label = (
                "Start homework"
                if status == "not_started"
                else ("Continue" if status == "in_progress" else "View")
            )
            btn_type = "primary" if status != "completed" else "secondary"
            if st.button(btn_label, key=f"start_hw_{hw_id}", type=btn_type, use_container_width=True):
                ok_start, session = auth.safe_call(
                    api_client.start_homework_session,
                    hw_id,
                    spinner="Opening homework question...",
                )
                if ok_start:
                    st.session_state["active_session_id"] = session["id"]
                    st.switch_page("pages/student/solve.py")
