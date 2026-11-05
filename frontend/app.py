# Entry point: login check and role-based navigation (run with: streamlit run app.py --server.port 8501)
import streamlit as st
import auth

st.set_page_config(page_title="Neura", layout="wide")

if not auth.is_logged_in():
    pg = st.navigation(
        [st.Page("pages/common/login.py", title="Sign in")],
        position="hidden",
    )
else:
    role = auth.current_role()
    ROLE_PAGES = {
        "student": [
            st.Page("pages/student/home.py", title="Home", default=True),
            st.Page("pages/student/homework.py", title="View homework"),
            st.Page("pages/student/diy.py", title="DIY"),
            st.Page("pages/student/pyq.py", title="PYQ's"),
            st.Page("pages/student/upload_question.py", title="Upload a question"),
            st.Page("pages/student/solve.py", title="Solve", visibility="hidden"),
        ],
        "teacher": [
            st.Page("pages/teacher/home.py", title="Home", default=True),
            st.Page("pages/teacher/class_homework.py", title="Class homework"),
            st.Page("pages/teacher/syllabus.py", title="View syllabus"),
            st.Page("pages/teacher/class_status.py", title="Class status"),
        ],
        "faculty": [
            st.Page("pages/faculty/home.py", title="Home", default=True),
            st.Page("pages/faculty/create_teacher.py", title="Create teacher"),
            st.Page("pages/faculty/create_class.py", title="Create class"),
            st.Page("pages/faculty/edit_class.py", title="Edit class", visibility="hidden"),
            st.Page("pages/faculty/syllabus.py", title="Update syllabus"),
        ],
    }
    if role not in ROLE_PAGES:
        auth.logout()
        st.error("Unknown role.")
        st.stop()
    pg = st.navigation(ROLE_PAGES[role])

    with st.sidebar:
        user = auth.current_user()
        st.markdown("**" + user["name"] + "**")
        st.caption(user["role"].capitalize() + " · " + user["email"])
        if st.button("Log out", use_container_width=True):
            auth.logout()
            st.rerun()

pg.run()
