import streamlit as st
import auth
import theme
import api_client

theme.apply_theme()

if auth.current_role() != "teacher":
    st.error("You are not allowed to view this page.")
    st.stop()

theme.page_header("View syllabus", "Browse and open PDFs uploaded by faculty for your subject.")

col_q, col_type = st.columns([3, 1])
with col_q:
    q = st.text_input("Search PDF by name", placeholder="Type book name...")
with col_type:
    btype = st.selectbox("Type", options=["All", "textbook", "pyq", "question_bank"])

ok, data = auth.safe_call(
    api_client.list_books,
    q=q.strip() or None,
    book_type=None if btype == "All" else btype,
    spinner="Loading syllabus PDFs...",
)
if not ok:
    st.stop()

books = data.get("books", [])
if not books:
    st.info("No syllabus PDFs found for your subject.")
    st.stop()

for b in books:
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"### {b['name']}")
            st.caption(
                f"Subject: **{b['subject']}** · Type: `{b['type']}` · Status: `{b['status']}` · Pages: {b.get('page_count', '-')}"
            )
        with c2:
            pdf_url = api_client.get_book_file_url(b["id"])
            st.markdown(f"[Open PDF]({pdf_url})")
