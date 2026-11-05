import streamlit as st
import auth
import theme

theme.apply_theme()

if auth.current_role() != "student":
    st.error("You are not allowed to view this page.")
    st.stop()

theme.page_header("DIY practice", "Pick how you want to practise.")

col1, col2 = st.columns(2)
with col1:
    if st.button("PYQ's", use_container_width=True):
        st.switch_page("pages/student/pyq.py")
with col2:
    if st.button("Upload a question", use_container_width=True, type="primary"):
        st.switch_page("pages/student/upload_question.py")
