import streamlit as st
import auth
import config
import theme
import api_client

theme.apply_theme()

if auth.current_role() != "student":
    st.error("You are not allowed to view this page.")
    st.stop()

theme.page_header("PYQ's & Books", "Search for a book or PYQ PDF by name and start solving a question.")

col_search, col_subj = st.columns([3, 1])
with col_search:
    query = st.text_input("Search PDF by name", placeholder="Type book or PYQ name...")
with col_subj:
    subj_filter = st.selectbox("Subject", options=["All"] + config.SUBJECTS)

ok, data = auth.safe_call(
    api_client.list_books,
    q=query.strip() or None,
    subject=None if subj_filter == "All" else subj_filter,
    spinner="Searching books...",
)
if not ok:
    st.stop()

books = data.get("books", [])
if not books:
    st.info("No matching books found.")
    st.stop()

st.subheader("Available PDFs")
for b in books:
    bid = b["id"]
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"**{b['name']}**")
            st.caption(
                f"Subject: {b['subject']} · Type: {b['type']} · Pages: {b.get('page_count', '-')}"
            )
        with c2:
            pdf_key = f"pdf_bytes_{bid}"
            if pdf_key not in st.session_state:
                if st.button("Load PDF", key=f"load_pdf_stu_{bid}", use_container_width=True):
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
                    key=f"dl_pdf_stu_{bid}",
                    use_container_width=True,
                )

st.divider()
st.subheader("Start solving a question from a book")

book_options = {f"{b['name']} ({b['subject']})": b["id"] for b in books}
with st.form("start_pyq_form"):
    selected_label = st.selectbox("Select book / PDF", options=list(book_options.keys()))
    chapter = st.text_input("Chapter (optional)", placeholder="e.g. Kinematics or Quadratic Equations")
    question_ref = st.text_input("Question reference", placeholder="e.g. Q3 or Exercise 1.1, Q1")
    submitted = st.form_submit_button("Start solving", type="primary")

if submitted:
    if not question_ref.strip():
        st.error("Enter a question reference.")
    else:
        book_id = book_options[selected_label]
        ok_pyq, session = auth.safe_call(
            api_client.start_pyq_session,
            book_id=book_id,
            question_ref=question_ref.strip(),
            chapter=chapter.strip() or None,
            spinner="Finding the question in the book...",
        )
        if ok_pyq:
            st.session_state["active_session_id"] = session["id"]
            st.switch_page("pages/student/solve.py")
