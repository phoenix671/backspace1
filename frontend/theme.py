# Shared page styling and small UI helpers
import streamlit as st


def apply_theme():
    st.markdown(
        """
        <style>
        #MainMenu, footer {
            visibility: hidden;
        }
        .block-container {
            padding-top: 2rem;
            max-width: 1100px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title, subtitle=None):
    st.title(title)
    if subtitle:
        st.caption(subtitle)

