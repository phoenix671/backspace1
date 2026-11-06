import streamlit as st
import auth
import api_client
import theme

theme.apply_theme()

# Keep this page's visual treatment local to the sign-in screen.
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@500;600&family=Caveat:wght@500;600&display=swap');

    .stApp {
        background-color: #fffdf1;
        background-image: repeating-linear-gradient(to bottom, transparent 0, transparent 35px, rgba(185, 169, 119, .19) 36px, transparent 37px);
        color: #382a20;
        font-family: 'DM Sans', sans-serif;
    }
    .block-container { max-width: 760px; padding-top: 2.5rem; }
    [data-testid="stHeader"] { background: transparent; }
    .login-topline { display:flex; justify-content:space-between; align-items:center; margin: 0 0 2.1rem; }
    .login-script { color:#63745d; font: 600 1.7rem 'Caveat', cursive; transform: rotate(-3deg); }
    .login-number { color:#9b9279; font-size:.75rem; letter-spacing:.16em; }
    .login-eyebrow { color:#9c8160; font-size:.76rem; letter-spacing:.18em; text-transform:uppercase; margin-bottom:.8rem; }
    .login-title { color:#3b281c; font: 500 2.7rem/1.1 'Playfair Display', Georgia, serif; letter-spacing:-.04em; margin:0 0 .45rem; }
    .login-subtitle { color:#8e8779; font-size:1rem; margin:0 0 1.7rem; }
    div[data-testid="stTextInput"] label { color:#493a2e; font-size:.9rem; font-weight:500; }
    div[data-testid="stTextInput"] input {
        height: 3.35rem; border:1px solid #ded8c5; border-radius:9px;
        background:rgba(255,255,255,.57); color:#33271e;
        box-shadow:none; transition:border-color .2s, box-shadow .2s, background .2s;
    }
    div[data-testid="stTextInput"] input:focus { border-color:#82916b; box-shadow:0 0 0 3px rgba(130,145,107,.15); background:#fffef8; }
    div[data-testid="stForm"] { border:0; padding:0; }
    div[data-testid="stFormSubmitButton"] button {
        min-height:3.7rem; border:0; border-radius:0; color:#fffdf3;
        background:#667b53; font-weight:700; font-size:1rem;
        clip-path:polygon(8% 0,92% 0,100% 50%,92% 100%,8% 100%,0 50%);
        transition:background-color .22s ease, transform .22s ease, box-shadow .22s ease;
    }
    div[data-testid="stFormSubmitButton"] button:hover {
        background:#45291c; color:#fffdf3; transform:translateY(-2px);
        box-shadow:0 8px 18px rgba(69,41,28,.17);
    }
    div[data-testid="stFormSubmitButton"] button:active { transform:translateY(0); }
    div[data-testid="stAlert"] { border-radius:9px; }
    .login-footnote { color:#928a78; font-size:.85rem; text-align:center; margin-top:1.2rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

_, middle, _ = st.columns([1, 2, 1])

with middle:
    st.markdown(
        """
        <div class="login-topline"><span class="login-script">hello again.</span><span class="login-number">NO. 01</span></div>
        <div class="login-eyebrow">Student · Teacher Portal</div>
        <h1 class="login-title">Welcome back</h1>
        <p class="login-subtitle">A fresh page, right where you left off.</p>
        """,
        unsafe_allow_html=True,
    )

    notice = st.session_state.pop("login_notice", None)
    if notice:
        st.info(notice)

    with st.form("login_form"):
        email = st.text_input("User ID", placeholder="name@class.com")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in   →", use_container_width=True)

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

    st.markdown('<div class="login-footnote">♙ &nbsp; Your space. Safely kept.</div>', unsafe_allow_html=True)
