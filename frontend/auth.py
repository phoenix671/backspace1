# Login state helpers using st.session_state: token, user, logout, 401 handling
import streamlit as st
import api_client


def is_logged_in():
    return bool(st.session_state.get("token") and st.session_state.get("user"))


def current_user():
    return st.session_state.get("user")


def current_role():
    if is_logged_in():
        return st.session_state["user"]["role"]
    return None


def login_user(email, password):
    result = api_client.login(email, password)
    st.session_state["token"] = result["token"]
    st.session_state["user"] = result["user"]
    return result["user"]


def logout():
    st.session_state.clear()


def handle_api_error(err):
    """The login page must NOT use this for its own 401 (wrong password), because that would loop."""
    if err.status == 401:
        logout()
        st.session_state["login_notice"] = "Your session expired. Please sign in again."
        st.rerun()
    else:
        st.error(err.message)

