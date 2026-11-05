import streamlit as st
import auth
import theme

theme.apply_theme()

if auth.current_role() != "teacher":
    st.error("You are not allowed to view this page.")
    st.stop()

user = auth.current_user()
theme.page_header("Teacher home", "Signed in as " + user["name"])
st.write("Coming soon.")
