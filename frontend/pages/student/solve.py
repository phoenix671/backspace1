import importlib
import streamlit as st
import auth
import theme
import api_client
import solve_view
import session_cache

importlib.reload(theme)
theme.apply_student_theme()

if auth.current_role() != "student":
    st.error("You are not allowed to view this page.")
    st.stop()

theme.page_header("Solve")

session_id = st.session_state.get("active_session_id")
if session_id is None:
    st.info("No question selected yet.")
    st.page_link("pages/student/diy.py", label="Go to DIY")
    st.stop()

ok, data = auth.safe_call(
    api_client.get_session, session_id, spinner="Loading your question..."
)
if not ok:
    st.stop()
session = data["session"]

if session.get("followup_of") is not None:
    parent_id = session["followup_of"]
    f_idx = session.get("followup_index") or 1
    top_col1, top_col2 = st.columns([4, 1])
    with top_col1:
        st.info(f"Follow-up question {f_idx} of 3")
    with top_col2:
        if st.button("Back to main question", use_container_width=True):
            st.session_state["active_session_id"] = parent_id
            st.rerun()

solve_view.render_question(session)
solve_view.render_videos_toggle(session_id)

results = session_cache.load_results(session_id, session["created_at"])

if session["attempts_used"] > 0 and not results:
    st.info("Earlier hints are not available on this device.")

real = [r for r in results if r["stage"] != "retry"]
for i, r in enumerate(real):
    with st.expander(
        "Attempt " + str(r["attempt"]["trial_number"]) + " · " + r["stage"].capitalize(),
        expanded=(i == len(real) - 1),
    ):
        solve_view.render_result(r, session_id=session_id)

if results and results[-1]["stage"] == "retry":
    solve_view.render_result(results[-1], session_id=session_id)

if session["status"] == "awaiting_attempt":
    nonce = st.session_state.get("upload_nonce", 0)
    with st.form("solution_form_" + str(session_id) + "_" + str(nonce)):
        image = st.file_uploader(
            "Upload a photo of your solution",
            type=["png", "jpg", "jpeg"],
        )
        submitted = st.form_submit_button("Submit solution", type="primary")
    if submitted:
        ok, result = auth.safe_call(
            api_client.submit_attempt,
            session_id,
            image,
            spinner="Checking your solution. This can take up to a minute...",
        )
        if ok:
            session_cache.save_result(session_id, session["created_at"], result)
            st.session_state["upload_nonce"] = nonce + 1
            st.rerun()

    if session.get("followup_of") is not None:
        if st.button("Skip this follow-up question"):
            ok_skip, _ = auth.safe_call(
                api_client.skip_session,
                session_id,
                spinner="Skipping follow-up...",
            )
            if ok_skip:
                st.session_state["active_session_id"] = session["followup_of"]
                st.rerun()
else:
    if session["status"] in ("solved", "revealed"):
        st.success("This question is finished.")
    elif session["status"] == "skipped":
        st.warning("This follow-up question was skipped.")

    if session["followup_triggered"]:
        solve_view.render_followups(session_id)

    if session.get("followup_of") is not None:
        if st.button("Return to follow-up list", type="primary"):
            st.session_state["active_session_id"] = session["followup_of"]
            st.rerun()

    if session.get("source") == "homework":
        st.page_link("pages/student/homework.py", label="Back to Homework")
    else:
        st.page_link("pages/student/diy.py", label="Back to DIY")
