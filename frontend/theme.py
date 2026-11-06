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


def apply_faculty_theme():
    """Faculty-only book and paper styling; leaves page behavior untouched."""
    apply_theme()
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600&display=swap');
        .stApp {
            background-color:#fffdf1;
            background-image:repeating-linear-gradient(to bottom, transparent 0, transparent 35px, rgba(185,169,119,.17) 36px, transparent 37px);
            color:#382a20;
            font-family:'DM Sans',sans-serif;
        }
        .block-container { max-width:1100px; padding-top:2.2rem; }
        h1, h2, h3 { color:#3b281c; font-family:'Playfair Display',Georgia,serif; }
        [data-testid="stSidebar"] {
            background:#f6f0dc;
            border-right:1px solid #e2d8bb;
            box-shadow:4px 0 18px rgba(65,44,28,.07);
        }
        [data-testid="stSidebar"] [data-testid="stSidebarNav"] { padding:1rem .75rem; }
        [data-testid="stSidebar"] [data-testid="stSidebarNav"] a {
            border:1px solid #e5dcc7;
            border-radius:8px;
            background:rgba(255,253,241,.9);
            color:#493a2e;
            margin:.38rem 0;
            min-height:3rem;
            transition:background-color .2s,border-color .2s,transform .2s,box-shadow .2s;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {
            background:#eae2ce;
            border-color:#b9a988;
            transform:translateX(3px);
            box-shadow:0 4px 10px rgba(69,41,28,.08);
        }
        [data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] {
            background:#e9e2d0;
            border-color:#c6b898;
            color:#382a20;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarNav"]::before {
            content:'NEURA  ·  FACULTY';
            display:block;
            color:#8d7a5b;
            font-size:.7rem;
            letter-spacing:.17em;
            padding:.4rem .55rem .8rem;
        }
        [data-testid="stSidebar"] button {
            background:#667b53;
            color:#fffdf3;
            border:0;
            transition:background-color .22s ease,transform .22s ease,box-shadow .22s ease;
        }
        [data-testid="stSidebar"] button:hover { background:#45291c; color:#fffdf3; transform:translateY(-1px); }
        .stButton button, .stFormSubmitButton button, .stDownloadButton button {
            background:#667b53;
            color:#fffdf3;
            border:0;
            transition:background-color .22s ease,transform .22s ease,box-shadow .22s ease;
        }
        .stButton button:hover, .stFormSubmitButton button:hover, .stDownloadButton button:hover {
            background:#45291c;
            color:#fffdf3;
            transform:translateY(-2px);
            box-shadow:0 7px 16px rgba(69,41,28,.16);
        }
        input, textarea, [data-baseweb="select"] > div, [data-testid="stFileUploaderDropzone"] {
            transition:border-color .2s ease,box-shadow .2s ease,background-color .2s ease;
        }
        input:hover, textarea:hover, [data-baseweb="select"] > div:hover, [data-testid="stFileUploaderDropzone"]:hover {
            border-color:#9b8a69;
            box-shadow:0 0 0 3px rgba(130,145,107,.12);
            background-color:#fffef8;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            transform:translateY(-2px);
            box-shadow:0 8px 18px rgba(69,41,28,.09);
            border-color:#c7b894;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_teacher_theme():
    """Apply the shared paper-and-book presentation to teacher pages."""
    apply_faculty_theme()
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] [data-testid="stSidebarNav"]::before {
            content:'NEURA  ·  TEACHER';
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_student_theme():
    """Apply the shared paper-and-book presentation to student pages."""
    apply_faculty_theme()
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] [data-testid="stSidebarNav"]::before {
            content:'NEURA  ·  STUDENT';
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

