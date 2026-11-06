import streamlit as st
import auth
import config
import theme
import api_client

theme.apply_faculty_theme()

if auth.current_role() != "faculty":
    st.error("You are not allowed to view this page.")
    st.stop()

theme.page_header("Edit class", "Add or remove students and reassign subject teachers.")

ok_all, all_cls_data = auth.safe_call(api_client.list_faculty_classes, spinner="Loading classes...")
if not ok_all:
    st.stop()

classes = all_cls_data.get("classes", [])
if not classes:
    st.info("No classes available to edit.")
    st.page_link("pages/faculty/home.py", label="Back to Faculty home")
    st.stop()

cls_map = {c["name"]: c["id"] for c in classes}
default_id = st.session_state.get("edit_class_id")
cls_names = list(cls_map.keys())
default_idx = 0
for i, name in enumerate(cls_names):
    if cls_map[name] == default_id:
        default_idx = i
        break

selected_cls_name = st.selectbox("Select class", options=cls_names, index=default_idx)
class_id = cls_map[selected_cls_name]
st.session_state["edit_class_id"] = class_id

ok_det, detail = auth.safe_call(
    api_client.get_class_detail,
    class_id,
    spinner="Loading class details...",
)
if not ok_det:
    st.stop()

st.subheader(f"Students in {detail['name']}")
students = detail.get("students", [])
if not students:
    st.info("No active students in this class.")
else:
    for s in students:
        sid = s["id"]
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"**{s['name']}** (Roll: `{s.get('roll_number') or '-'}`)")
                st.caption(s.get("email", ""))
            with c2:
                if st.button("Delete", key=f"del_stu_{class_id}_{sid}", use_container_width=True):
                    ok_del, _ = auth.safe_call(
                        api_client.remove_class_student,
                        class_id,
                        sid,
                        spinner="Removing student...",
                    )
                    if ok_del:
                        st.rerun()

st.markdown("#### Add a student")
with st.form("add_student_form"):
    new_name = st.text_input("Student name", placeholder="e.g. Meera T")
    new_roll = st.text_input("Roll number (optional)", placeholder="e.g. 3")
    add_sub = st.form_submit_button("Add student", type="primary")

if add_sub:
    if not new_name.strip():
        st.error("Enter the student's name.")
    else:
        ok_add, add_res = auth.safe_call(
            api_client.add_class_student,
            class_id=class_id,
            name=new_name.strip(),
            roll_number=new_roll.strip() or None,
            spinner="Adding student...",
        )
        if ok_add:
            st.session_state["last_added_student_creds"] = add_res["credentials"]
            st.rerun()

added_creds = st.session_state.pop("last_added_student_creds", None)
if added_creds:
    st.success("Student added! Copy their initial credentials:")
    st.code(
        f"Email: {added_creds['email']}\nInitial password: {added_creds['initial_password']}",
        language=None,
    )

st.divider()
st.subheader("Subject teachers")

ok_t, t_data = auth.safe_call(api_client.list_teachers, spinner="Loading teachers...")
teachers = (t_data or {}).get("teachers", []) if ok_t else []
current_map = {
    item["subject"]: item["teacher_id"]
    for item in detail.get("subject_teachers", [])
}

with st.form("update_subject_teachers_form"):
    new_assignments = []
    for subj in config.SUBJECTS:
        subj_teachers = [t for t in teachers if t["subject"] == subj] or teachers
        options = {"-- None --": None}
        for t in subj_teachers:
            options[f"{t['name']} ({t['subject']})"] = t["id"]
        opt_labels = list(options.keys())
        cur_tid = current_map.get(subj)
        idx = 0
        for i, lbl in enumerate(opt_labels):
            if options[lbl] == cur_tid:
                idx = i
                break
        chosen = st.selectbox(
            f"{subj} teacher",
            options=opt_labels,
            index=idx,
            key=f"edit_cls_{class_id}_{subj}",
        )
        if options[chosen] is not None:
            new_assignments.append({"subject": subj, "teacher_id": options[chosen]})
    save_teachers = st.form_submit_button("Save teacher assignments", type="primary")

if save_teachers:
    ok_upd, _ = auth.safe_call(
        api_client.update_class_subject_teachers,
        class_id,
        new_assignments,
        spinner="Updating subject teachers...",
    )
    if ok_upd:
        st.success("Subject teachers updated.")
        st.rerun()

st.page_link("pages/faculty/home.py", label="Back to Faculty home")
