import importlib
import streamlit as st
import auth
import theme
import api_client

importlib.reload(theme)
theme.apply_teacher_theme()

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
    bid = b["id"]
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"### {b['name']}")
            st.caption(
                f"Subject: **{b['subject']}** · Type: `{b['type']}` · Status: `{b['status']}` · Pages: {b.get('page_count', '-')}"
            )
        with c2:
            pdf_key = f"pdf_bytes_{bid}"
            if pdf_key not in st.session_state:
                if st.button("Load PDF", key=f"load_pdf_t_{bid}", use_container_width=True):
                    ok_pdf, pdf_bytes = auth.safe_call(
                        api_client.get_book_file,
                        bid,
                        spinner="Fetching PDF...",
                    )
                    if ok_pdf and pdf_bytes:
                        st.session_state[pdf_key] = pdf_bytes
                        st.rerun()
            else:
                st.download_button(
                    "Download PDF",
                    data=st.session_state[pdf_key],
                    file_name=f"{b['name']}.pdf",
                    mime="application/pdf",
                    key=f"dl_pdf_t_{bid}",
                    use_container_width=True,
                )
