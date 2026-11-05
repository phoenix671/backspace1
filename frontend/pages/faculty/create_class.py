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
    "Create class",
    "Enter the number of students, fill in their details, and assign subject teachers.",
)

ok_t, t_data = auth.safe_call(api_client.list_teachers, spinner="Loading teachers...")
teachers = (t_data or {}).get("teachers", []) if ok_t else []

student_count = st.number_input(
    "Number of students present in the class",
    min_value=1,
    max_value=100,
    value=2,
    step=1,
)

with st.form("create_class_form"):
    class_name = st.text_input("Class name", placeholder="e.g. 10-A")

    st.markdown("#### Student details")
    student_rows = []
    for i in range(int(student_count)):
        c1, c2 = st.columns([3, 1])
        with c1:
            sname = st.text_input(
                f"Student {i + 1} name",
                key=f"create_cls_sname_{i}",
                placeholder=f"Student {i + 1} full name",
            )
        with c2:
            sroll = st.text_input(
                f"Roll no. {i + 1} (optional)",
                value=str(i + 1),
                key=f"create_cls_sroll_{i}",
            )
        student_rows.append({"name": sname, "roll_number": sroll})

    st.markdown("#### Assign subject teachers")
    subject_teacher_selections = {}
    for subj in config.SUBJECTS:
        subj_teachers = [t for t in teachers if t["subject"] == subj] or teachers
        options = {"-- None --": None}
        for t in subj_teachers:
            options[f"{t['name']} ({t['subject']})"] = t["id"]
        chosen_label = st.selectbox(
            f"{subj} teacher",
            options=list(options.keys()),
            key=f"create_cls_subj_{subj}",
        )
        if options[chosen_label] is not None:
            subject_teacher_selections[subj] = options[chosen_label]

    saved = st.form_submit_button("Save class", type="primary")

if saved:
    filled_students = [
        {"name": s["name"].strip(), "roll_number": s["roll_number"].strip() or None}
        for s in student_rows
        if s["name"].strip()
    ]
    if not class_name.strip():
        st.error("Enter a class name.")
    elif not filled_students:
        st.error("Enter at least one student's name.")
    else:
        subject_teachers = [
            {"subject": subj, "teacher_id": tid}
            for subj, tid in subject_teacher_selections.items()
        ]
        ok_create, res = auth.safe_call(
            api_client.create_class,
            name=class_name.strip(),
            students=filled_students,
            subject_teachers=subject_teachers,
            spinner="Creating class and generating student accounts...",
        )
        if ok_create:
            st.session_state["last_created_class_result"] = res

last_res = st.session_state.get("last_created_class_result")
if last_res:
    cls_info = last_res["class"]
    creds = last_res.get("credentials", [])
    st.success(f"Class '{cls_info['name']}' created with {cls_info['student_count']} students!")
    if creds:
        st.markdown("**Generated student credentials (shown once — download or copy):**")
        lines = ["name,email,initial_password"]
        for c in creds:
            lines.append(f"{c['name']},{c['email']},{c['initial_password']}")
        csv_text = "\n".join(lines)
        st.code(csv_text, language=None)
        st.download_button(
            "Download credentials CSV",
            data=csv_text,
            file_name=f"class_{cls_info['name']}_credentials.csv",
            mime="text/csv",
        )
    if st.button("Back to Faculty home", type="primary"):
        st.session_state.pop("last_created_class_result", None)
        st.switch_page("pages/faculty/home.py")
else:
    st.page_link("pages/faculty/home.py", label="Back to Faculty home")
