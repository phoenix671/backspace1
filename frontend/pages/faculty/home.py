import streamlit as st
import auth
import theme
import api_client

theme.apply_theme()

if auth.current_role() != "faculty":
    st.error("You are not allowed to view this page.")
    st.stop()

user = auth.current_user()
theme.page_header("Faculty home", "Signed in as " + user["name"])

if st.button("Create teacher", use_container_width=True, type="primary"):
    st.switch_page("pages/faculty/create_teacher.py")

if st.button("Create class", use_container_width=True):
    st.switch_page("pages/faculty/create_class.py")

if st.button("Update syllabus", use_container_width=True):
    st.switch_page("pages/faculty/syllabus.py")

st.divider()
st.subheader("Classes")

ok_cls, cls_data = auth.safe_call(
    api_client.list_faculty_classes,
    spinner="Loading classes...",
)
if ok_cls and cls_data:
    classes = cls_data.get("classes", [])
    if not classes:
        st.info("No classes created yet.")
    for cls in classes:
        cid = cls["id"]
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"### Class {cls['name']}")
                st.caption(f"Students enrolled: {cls['student_count']}")
            with c2:
                if st.button("Edit", key=f"edit_cls_{cid}", use_container_width=True):
                    st.session_state["edit_class_id"] = cid
                    st.switch_page("pages/faculty/edit_class.py")

st.divider()
st.subheader("Teachers")
ok_t, t_data = auth.safe_call(
    api_client.list_teachers,
    spinner="Loading teachers...",
)
if ok_t and t_data:
    teachers = t_data.get("teachers", [])
    if not teachers:
        st.info("No teachers created yet.")
    else:
        for t in teachers:
            st.write(f"- **{t['name']}** ({t['subject']}) · `{t['email']}`")
