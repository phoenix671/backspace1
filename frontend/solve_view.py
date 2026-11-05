# Display helpers for the solving screen: one function per kind of block
import time
import streamlit as st
import api_client
import auth
import config


def pretty_mistake(mistake_type):
    return mistake_type.replace("_", " ").capitalize()


def render_question(session):
    question = session["question"]
    st.caption(question["subject"] + " · " + question["topic"])
    st.markdown("### " + question["text"])
    if question["image_url"]:
        st.image(config.file_url(question["image_url"]), width=350)
    if session["status"] == "awaiting_attempt":
        st.caption(
            "Attempt "
            + str(min(session["attempts_used"] + 1, session["max_attempts"]))
            + " of "
            + str(session["max_attempts"])
        )
    else:
        st.caption(
            "Attempts used: "
            + str(session["attempts_used"])
            + " of "
            + str(session["max_attempts"])
        )


def render_diagnosis(diagnosis):
    for item in diagnosis:
        with st.container(border=True):
            st.markdown(
                "**Step "
                + str(item["step_number"])
                + " · "
                + pretty_mistake(item["mistake_type"])
                + "**"
            )
            st.write("You wrote: " + item["student_wrote"])
            st.write("Expected: " + item["expected"])
            st.caption(item["description"])


def render_efficient_method(method):
    st.markdown("**Most efficient method: " + method["title"] + "**")
    for i, step in enumerate(method["steps"], start=1):
        st.write(str(i) + ". " + step)


def render_result(result, session_id=None):
    stage = result["stage"]
    if stage == "hints":
        st.write(result["message"])
        render_diagnosis(result["diagnosis"])
        tf = result["topics_and_formulae"]
        if tf:
            st.markdown("**Topics you need**")
            st.markdown("\n".join("- " + t for t in tf["topics"]))
            st.markdown("**Formulae you need**")
            for formula in tf["formulae"]:
                st.code(formula, language=None)
    elif stage == "simplified":
        st.write(result["message"])
        render_diagnosis(result["diagnosis"])
        st.markdown("**Simpler version of the question**")
        st.info(result["simplified_question"]["text"])
        if session_id is not None:
            render_gif(session_id)
    elif stage == "revealed":
        st.write(result["message"])
        render_diagnosis(result["diagnosis"])
        full_solution = result["full_solution"]
        st.markdown("**Full solution**")
        for s in full_solution["steps"]:
            st.write("Step " + str(s["step_number"]) + ": " + s["text"])
        st.success("Final answer: " + full_solution["final_answer"])
        if full_solution["shortcuts"]:
            st.markdown("**Shortcuts**")
            for sc in full_solution["shortcuts"]:
                st.write("**" + sc["title"] + "**: " + sc["text"])
        if full_solution["efficient_method"]:
            render_efficient_method(full_solution["efficient_method"])
    elif stage == "solved":
        st.success(result["message"])
        if result["efficient_method"]:
            render_efficient_method(result["efficient_method"])
    elif stage == "retry":
        st.warning(result["message"])


def render_gif(session_id):
    cache_key = f"gif_{session_id}"
    cached = st.session_state.get(cache_key)
    if cached is None:
        status = "pending"
        url = None
        with st.spinner("Creating an explanation animation..."):
            for _ in range(15):
                ok, data = auth.safe_call(api_client.get_gif, session_id)
                if not ok:
                    status = "failed"
                    url = None
                    break
                status = data.get("status")
                url = data.get("url")
                if status in ("ready", "failed"):
                    break
                time.sleep(2)
        cached = {"status": status, "url": url}
        st.session_state[cache_key] = cached

    if cached["status"] == "ready" and cached.get("url"):
        st.image(config.file_url(cached["url"]))
    else:
        st.info("Animation is not available right now. Use the simplified question above.")


def render_videos_toggle(session_id):
    show_videos = st.toggle(
        "Show YouTube video explanations",
        key=f"videos_toggle_{session_id}",
    )
    if not show_videos:
        return
    cache_key = f"videos_{session_id}"
    videos = st.session_state.get(cache_key)
    if videos is None:
        ok, data = auth.safe_call(
            api_client.get_session_videos,
            session_id,
            spinner="Finding relevant YouTube videos...",
        )
        if not ok:
            return
        videos = data.get("videos", [])
        st.session_state[cache_key] = videos

    if not videos:
        st.info("No videos found for this topic yet.")
        return

    with st.container(border=True):
        st.markdown("**Recommended YouTube Videos**")
        for v in videos:
            kind_label = (
                "Question solution"
                if v.get("kind") == "question_solution"
                else "Topic explainer"
            )
            st.markdown(
                f"- **[{v['title']}]({v['url']})** · _{v.get('channel', 'YouTube')}_ ({kind_label})"
            )


def render_followups(session_id):
    st.subheader("Follow-up practice questions")
    st.caption(
        "Since this question took 3 trials, here are 2 PYQs and 1 AI-curated question on this topic. You can solve or skip each one."
    )
    ok, data = auth.safe_call(
        api_client.get_followups,
        session_id,
        spinner="Generating personalised follow-up questions...",
    )
    if not ok:
        return
    followups = data.get("followups", [])
    for f in followups:
        fid = f["id"]
        idx = f.get("followup_index") or 1
        source_label = "PYQ" if f.get("source") == "followup_pyq" else "AI Curated"
        status = f.get("status", "awaiting_attempt")
        with st.container(border=True):
            col_q, col_a, col_b = st.columns([4, 1, 1])
            with col_q:
                st.markdown(f"**Follow-up {idx} ({source_label})** · Status: `{status}`")
                st.write(f["question"]["text"])
            with col_a:
                if status == "awaiting_attempt":
                    if st.button("Solve", key=f"solve_followup_{fid}", type="primary", use_container_width=True):
                        st.session_state["active_session_id"] = fid
                        st.rerun()
                else:
                    if st.button("View", key=f"view_followup_{fid}", use_container_width=True):
                        st.session_state["active_session_id"] = fid
                        st.rerun()
            with col_b:
                if status == "awaiting_attempt":
                    if st.button("Skip", key=f"skip_followup_{fid}", use_container_width=True):
                        ok_skip, _ = auth.safe_call(
                            api_client.skip_session,
                            fid,
                            spinner="Skipping follow-up...",
                        )
                        if ok_skip:
                            st.rerun()


