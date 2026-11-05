import streamlit as st
import auth
import config
import theme
import api_client

theme.apply_theme()

if auth.current_role() != "faculty":
    st.error("You are not allowed to view this page.")
    st.stop()

theme.page_header(
    "Update syllabus",
    "Add textbooks, PYQs, or question banks (PDF) to build the RAG index.",
)

if "show_add_book_form" not in st.session_state:
    st.session_state["show_add_book_form"] = True

if st.button("Add book", type="primary"):
    st.session_state["show_add_book_form"] = True

if st.session_state.get("show_add_book_form"):
    with st.form("add_book_form"):
        pdf_file = st.file_uploader("Upload PDF file", type=["pdf"])
        book_name = st.text_input("Specific name of the PDF", placeholder="e.g. Maths Class 10 PYQs")
        book_type = st.selectbox(
            "Book type",
            options=["textbook", "pyq", "question_bank"],
        )
        subject = st.selectbox("Subject", options=config.SUBJECTS)
        submitted = st.form_submit_button("Upload & index book", type="primary")

    if submitted:
        if pdf_file is None or not book_name.strip():
            st.error("Select a PDF file and enter a book name.")
        else:
            ok_up, book = auth.safe_call(
                api_client.upload_book,
                file=pdf_file,
                name=book_name.strip(),
                book_type=book_type,
                subject=subject,
                spinner="Uploading PDF and starting RAG indexing...",
            )
            if ok_up:
                st.success(
                    f"Uploaded '{book['name']}' (status: {book['status']})."
                )

st.divider()
st.subheader("Uploaded syllabus books")

ok, data = auth.safe_call(api_client.list_books, spinner="Loading books...")
if ok and data:
    books = data.get("books", [])
    if not books:
        st.info("No books uploaded yet.")
    for b in books:
        bid = b["id"]
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.markdown(f"### {b['name']}")
                st.caption(
                    f"Subject: **{b['subject']}** · Type: `{b['type']}` · Status: `{b['status']}` · Pages: {b.get('page_count', '-')}"
                )
            with c2:
                if st.button("Check status", key=f"chk_book_{bid}", use_container_width=True):
                    ok_b, b_info = auth.safe_call(
                        api_client.get_book,
                        bid,
                        spinner="Checking status...",
                    )
                    if ok_b:
                        st.info(f"Status: {b_info['status']}")
            with c3:
                pdf_url = api_client.get_book_file_url(bid)
                st.markdown(f"[Open PDF]({pdf_url})")

st.page_link("pages/faculty/home.py", label="Back to Faculty home")
