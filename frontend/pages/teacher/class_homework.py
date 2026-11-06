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

ok_cls, cls_data = auth.safe_call(
    api_client.list_teacher_classes,
    spinner="Loading classes...",
)
if not ok_cls:
    st.stop()

classes = cls_data.get("classes", [])
if not classes:
    st.info("No classes assigned to you.")
    st.stop()

class_map = {f"{c['name']} ({c['subject']})": c["class_id"] for c in classes}
default_cid = st.session_state.get("teacher_class_id")
labels = list(class_map.keys())
default_idx = 0
for i, lbl in enumerate(labels):
    if class_map[lbl] == default_cid:
        default_idx = i
        break

theme.page_header("Class homework", "Assign new homework and inspect completion.")

selected_class_label = st.selectbox("Class", options=labels, index=default_idx)
class_id = class_map[selected_class_label]
st.session_state["teacher_class_id"] = class_id

ok_books, books_data = auth.safe_call(
    api_client.list_books,
    spinner="Loading books...",
)
books = (books_data or {}).get("books", []) if ok_books else []
ready_books = [b for b in books if b.get("status") == "ready"]

st.subheader("Assign new homework")
if not ready_books:
    st.warning("No ready books found for your subject. Ask faculty to upload syllabus PDFs.")
else:
    book_options = {f"{b['name']} ({b['type']})": b["id"] for b in ready_books}
    with st.form("assign_homework_form"):
        book_label = st.selectbox("Book name", options=list(book_options.keys()))
        chapter = st.text_input("Chapter name", placeholder="e.g. Quadratic Equations")
        question_ref = st.text_input(
            "Specific question in chapter",
            placeholder="e.g. Exercise 4.2, Q3",
        )
        title = st.text_input("Homework title (optional)", placeholder="e.g. Quadratics practice")
        due_at = st.text_input(
            "Due timestamp ISO UTC (optional)",
            placeholder="e.g. 2026-11-22T18:00:00Z",
        )
        submitted = st.form_submit_button("Assign homework", type="primary")

    if submitted:
        if not chapter.strip() or not question_ref.strip():
            st.error("Specify the chapter name and the specific question reference.")
        else:
            ok_create, created = auth.safe_call(
                api_client.create_homework,
                class_id=class_id,
                book_id=book_options[book_label],
                chapter=chapter.strip(),
                question_ref=question_ref.strip(),
                title=title.strip() or None,
                due_at=due_at.strip() or None,
                spinner="Extracting question from book and assigning homework...",
            )
            if ok_create:
                st.success(
                    f"Assigned '{created['title']}' — Extracted question: {created['question_text']}"
                )

st.divider()
st.subheader("Previously assigned homework")

ok_hw, hw_data = auth.safe_call(
    api_client.list_class_homework,
    class_id,
    spinner="Loading assigned homework...",
)
if not ok_hw:
    st.stop()

hw_list = hw_data.get("homework", [])
if not hw_list:
    st.info("No homework assigned to this class yet.")
    st.stop()

selected_hw_id = st.session_state.get("selected_homework_id")

for hw in hw_list:
    hid = hw["id"]
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"**{hw['title']}** · Topic: `{hw['topic']}`")
            st.caption(
                f"Assigned: {hw['assigned_at']} · Due: {hw.get('due_at') or 'None'} · Completed: **{hw['completed']} / {hw['total']}**"
            )
        with c2:
            if st.button("View completion", key=f"view_hw_{hid}", use_container_width=True):
                st.session_state["selected_homework_id"] = hid
                selected_hw_id = hid

if selected_hw_id is not None:
    st.divider()
    ok_det, detail = auth.safe_call(
        api_client.get_homework_detail,
        selected_hw_id,
        spinner="Loading homework completion...",
    )
    if ok_det and detail:
        st.subheader(f"Completion details: {detail['title']}")
        st.write(f"**Question:** {detail['question_text']}")
        comp = detail["completion"]
        completed_num = comp["completed"]
        total_num = comp["total"]
        pending_num = max(0, total_num - completed_num)

        st.markdown("#### Completion bar graph")
        st.bar_chart({"Completed": completed_num, "Pending": pending_num})

        st.markdown("#### Student completion list")
        for s in comp.get("students", []):
            badge = "✅ Completed" if s["completed"] else "⏳ Not completed"
            ts = f" ({s['completed_at']})" if s.get("completed_at") else ""
            st.write(f"- **{s['name']}**: {badge}{ts}")
