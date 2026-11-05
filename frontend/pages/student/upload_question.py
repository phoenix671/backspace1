import streamlit as st
import auth
import theme
import api_client

theme.apply_theme()

if auth.current_role() != "student":
    st.error("You are not allowed to view this page.")
    st.stop()

theme.page_header("Upload a question", "Upload a photo of the question, or type it.")

with st.form("upload_question_form"):
    image = st.file_uploader("Photo of the question", type=["png", "jpg", "jpeg"])
    text = st.text_area("Or type the question")
    submitted = st.form_submit_button("Start solving", type="primary")

if submitted:
    ok, session = auth.safe_call(
        api_client.upload_question,
        image=image,
        text=None if image is not None else (text.strip() or None),
        spinner="Reading your question. This can take up to a minute...",
    )
    if ok:
        st.session_state["active_session_id"] = session["id"]
        st.switch_page("pages/student/solve.py")
