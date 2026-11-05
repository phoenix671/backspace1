import streamlit as st
import auth
import theme
import api_client
import solve_view

theme.apply_theme()

if auth.current_role() != "student":
    st.error("You are not allowed to view this page.")
    st.stop()

user = auth.current_user()
theme.page_header("Student home", "Signed in as " + user["name"])

col1, col2 = st.columns(2)
with col1:
    if st.button("View homework", use_container_width=True):
        st.switch_page("pages/student/homework.py")
with col2:
    if st.button("DIY", use_container_width=True, type="primary"):
        st.switch_page("pages/student/diy.py")

st.divider()
st.subheader("Your learning statistics")

ok, stats = auth.safe_call(
    api_client.get_student_stats,
    spinner="Loading your statistics...",
)
if ok and stats:
    totals = stats.get("totals", {})
    m1, m2, m3 = st.columns(3)
    m1.metric("Total sessions", totals.get("sessions", 0))
    m2.metric("Solved", totals.get("solved", 0))
    m3.metric("Average attempts", totals.get("avg_attempts", 0))

    topics = stats.get("topics", [])
    if topics:
        st.markdown("#### Topics breakdown (Strong vs Weak)")
        status_badges = {
            "strong": "🟢 Strong",
            "learning": "🟡 Learning",
            "weak": "🔴 Weak",
        }
        for t in topics:
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{t['topic']}** ({t['subject']})")
                    mc = t.get("mistake_counts", {})
                    mc_parts = [
                        f"{solve_view.pretty_mistake(k)}: {v}"
                        for k, v in mc.items()
                        if v > 0
                    ]
                    st.caption(
                        f"Sessions: {t.get('sessions', 0)}"
                        + (" · Mistakes: " + ", ".join(mc_parts) if mc_parts else " · No mistakes recorded")
                    )
                with c2:
                    st.markdown(f"**{status_badges.get(t.get('status'), t.get('status', ''))}**")

    mistake_types = stats.get("mistake_types", [])
    if mistake_types:
        st.markdown("#### Mistake summary")
        chart_data = {
            solve_view.pretty_mistake(m["type"]): m["count"]
            for m in mistake_types
        }
        st.bar_chart(chart_data)
