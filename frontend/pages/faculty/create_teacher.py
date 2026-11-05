import streamlit as st
import auth
import config
import theme
import api_client

theme.apply_theme()

if auth.current_role() != "faculty":
    st.error("You are not allowed to view this page.")
    st.stop()

theme.page_header("Create teacher", "Enter teacher details to create a teacher account.")

with st.form("create_teacher_form"):
    name = st.text_input("Teacher name", placeholder="e.g. Ravi K")
    subject = st.selectbox("Subject", options=config.SUBJECTS)
    phone = st.text_input("Phone (optional)", placeholder="e.g. 9876543210")
    submitted = st.form_submit_button("Create teacher", type="primary")

if submitted:
    if not name.strip():
        st.error("Enter the teacher's name.")
    else:
        ok, res = auth.safe_call(
            api_client.create_teacher,
            name=name.strip(),
            subject=subject,
            phone=phone.strip() or None,
            spinner="Creating teacher account...",
        )
        if ok:
            t = res["teacher"]
            creds = res["credentials"]
            st.success(f"Created teacher {t['name']} ({t['subject']}).")
            st.markdown("**Generated credentials (shown once — copy now):**")
            st.code(
                f"Email: {creds['email']}\nInitial password: {creds['initial_password']}",
                language=None,
            )

st.divider()
st.subheader("Existing teachers")
ok_list, data = auth.safe_call(api_client.list_teachers, spinner="Loading teachers...")
if ok_list and data:
    for t in data.get("teachers", []):
        st.write(f"- **{t['name']}** · {t['subject']} · `{t['email']}`")

st.page_link("pages/faculty/home.py", label="Back to Faculty home")
