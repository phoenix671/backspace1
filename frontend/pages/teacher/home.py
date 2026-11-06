import importlib
import streamlit as st
import auth
import theme
import api_client

importlib.reload(theme)
theme.apply_teacher_theme()

if auth.current_role() != "teacher":
    st.error("You are not allowed to view this page.")
    st.stop()

user = auth.current_user()
theme.page_header("Teacher home", "Signed in as " + user["name"])

top1, top2 = st.columns(2)
with top1:
    if st.button("View syllabus", use_container_width=True):
        st.switch_page("pages/teacher/syllabus.py")
with top2:
    if st.button("Class status", use_container_width=True):
        st.switch_page("pages/teacher/class_status.py")

st.divider()
st.subheader("Your assigned classes")

ok, data = auth.safe_call(
    api_client.list_teacher_classes,
    spinner="Loading your classes...",
)
if not ok:
    st.stop()

classes = data.get("classes", [])
if not classes:
    st.info("No classes assigned to you yet.")
    st.stop()

for cls in classes:
    cid = cls["class_id"]
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            st.markdown(f"### Class {cls['name']}")
            st.caption(
                f"Subject: **{cls['subject']}** · Students: {cls['student_count']}"
            )
        with c2:
            if st.button(
                "Assign / View homework",
                key=f"hw_cls_{cid}_{cls['subject']}",
                type="primary",
                use_container_width=True,
            ):
                st.session_state["teacher_class_id"] = cid
                st.session_state["teacher_class_name"] = cls["name"]
                st.switch_page("pages/teacher/class_homework.py")
        with c3:
            if st.button(
                "Class status",
                key=f"status_cls_{cid}_{cls['subject']}",
                use_container_width=True,
            ):
                st.session_state["teacher_class_id"] = cid
                st.session_state["teacher_class_name"] = cls["name"]
                st.switch_page("pages/teacher/class_status.py")
