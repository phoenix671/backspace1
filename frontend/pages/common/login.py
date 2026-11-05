import streamlit as st
import auth
import api_client
import theme

theme.apply_theme()

_, middle, _ = st.columns([1, 2, 1])

with middle:
    theme.page_header("Welcome to Neura", "Sign in with your email and password.")

    notice = st.session_state.pop("login_notice", None)
    if notice:
        st.info(notice)

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="name@class.com")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        if not email.strip() or not password.strip():
            st.error("Enter your email and password.")
        else:
            ok = False
            with st.spinner("Signing in..."):
                try:
                    auth.login_user(email, password)
                    ok = True
                except api_client.ApiError as e:
                    st.error(e.message)
            if ok:
                st.rerun()
