import importlib

import streamlit as st
import auth
import theme

importlib.reload(theme)
theme.apply_student_theme()

if auth.current_role() != "student":
    st.error("You are not allowed to view this page.")
    st.stop()

theme.page_header("Physics flash cards", "Class 11 · quick revision, one card at a time.")
st.caption("Demo study material · Use the arrows to browse and reveal each card.")

DECKS = {
    "Important keys": [
        ("Kinematics · equations of motion", "For constant acceleration: v = u + at; s = ut + ½at²; v² = u² + 2as. Choose a positive direction first and keep signs consistent.", "Motion in a straight line"),
        ("Projectile · time of flight", "For launch speed u at angle θ on level ground: T = 2u sin θ / g. This assumes air resistance is ignored and launch and landing heights are equal.", "Motion in a plane"),
        ("Newton's second law", "Net force equals the rate of change of momentum: F⃗net = dp⃗/dt. For constant mass, F⃗net = ma⃗. Draw a free-body diagram before resolving forces.", "Laws of motion"),
        ("Work–energy theorem", "Net work done on a particle equals its change in kinetic energy: Wnet = Kf − Ki. K = ½mv².", "Work, energy and power"),
        ("Circular motion", "Centripetal acceleration points toward the centre: ac = v²/r = ω²r. The required inward net force is mv²/r; it is supplied by real forces such as tension or friction.", "Motion in a plane"),
        ("Gravitation · near Earth's surface", "Gravitational force: F = GMm/r². Near Earth's surface, weight is W = mg. Gravitational potential energy near the surface is approximately mgh for small height changes.", "Gravitation"),
        ("Thermodynamics · first law", "Using the convention that W is work done by the system: Q = ΔU + W. Check the sign convention stated in the question before substituting values.", "Thermodynamics"),
        ("Waves · speed relation", "Wave speed v = fλ, where f is frequency and λ is wavelength. When a wave enters a different medium, its frequency stays fixed while its speed and wavelength may change.", "Oscillations and waves"),
    ],
    "Memory cards": [
        ("Scalar or vector?", "Displacement, velocity, acceleration, force and momentum are vectors. Distance, speed, mass, time and energy are scalars.", "Quick recall"),
        ("Newton's laws in a phrase", "First: inertia. Second: net force changes momentum. Third: forces come in equal and opposite pairs acting on different bodies.", "Laws of motion"),
        ("Conservative force", "Work done by a conservative force depends only on the initial and final positions, not the path. Its work around a closed path is zero. Gravity is conservative.", "Work, energy and power"),
        ("Centre of mass", "The centre of mass moves as if the system's total mass were concentrated there and the net external force acted on it: M a⃗CM = F⃗external.", "System of particles"),
        ("Stress and strain", "Stress is restoring force per area. Strain is the fractional change in dimension. Within the elastic limit, Young's modulus = longitudinal stress / longitudinal strain.", "Mechanical properties of solids"),
        ("Heat versus temperature", "Heat is energy transferred because of a temperature difference. Temperature describes the thermal state; two bodies in thermal equilibrium have the same temperature.", "Thermal properties of matter"),
        ("Simple harmonic motion", "In SHM, acceleration is proportional to displacement and directed toward equilibrium: a = −ω²x. The minus sign carries the restoring direction.", "Oscillations"),
        ("Standing wave nodes", "At a node, displacement amplitude is always zero. At an antinode, amplitude is maximum. Adjacent nodes are separated by λ/2.", "Waves"),
    ],
    "Exam tips": [
        ("Start with a sketch", "For mechanics questions, sketch the situation and draw a separate free-body diagram. Label directions and angles before writing equations.", "Problem setup"),
        ("Keep units visible", "Convert to SI units before calculation. Write units with intermediate values so dimensional mistakes are easier to catch.", "Accuracy"),
        ("Choose a sign convention", "State the positive direction once, then use it consistently for displacement, acceleration, force and components.", "Mechanics"),
        ("Check limiting cases", "After solving, ask whether the result behaves sensibly at zero, very large or equal values. A quick estimate can reveal an algebra slip.", "Answer check"),
        ("Use graphs carefully", "Read slope and area from the correct graph: slope of a displacement–time graph is velocity; area under a velocity–time graph is displacement.", "Motion graphs"),
        ("Write the principle first", "Name the law or conservation principle before substituting numbers. This makes assumptions and the choice of equation clear.", "Clear working"),
        ("Round at the end", "Keep a few extra digits during intermediate calculations, then round the final result to the precision supported by the given data.", "Numerical questions"),
        ("Review common traps", "Check vector directions, squared terms, degrees versus radians where relevant, and whether the question asks for magnitude or direction.", "Final check"),
    ],
}

category = st.radio(
    "Choose a deck",
    list(DECKS.keys()),
    horizontal=True,
    label_visibility="collapsed",
    key="physics_flashcard_deck",
)
cards = DECKS[category]
state_key = f"physics_flashcard_index_{category}"
flip_key = f"physics_flashcard_revealed_{category}"
index = st.session_state.get(state_key, 0) % len(cards)
prompt, answer, chapter = cards[index]
revealed = st.session_state.get(flip_key, False)

st.markdown(
    """
    <style>
    .flash-card {
        min-height:290px; padding:2rem 2.2rem; margin:.6rem auto 1.2rem;
        max-width:760px; display:flex; flex-direction:column; justify-content:space-between;
        background:linear-gradient(145deg,rgba(255,255,249,.97),rgba(250,245,225,.96));
        border:1px solid #ded4ba; border-radius:18px;
        box-shadow:0 16px 35px rgba(69,41,28,.12), inset 0 1px rgba(255,255,255,.9);
        transition:transform .25s ease,box-shadow .25s ease;
    }
    .flash-card:hover { transform:translateY(-4px) rotate(-.25deg); box-shadow:0 22px 42px rgba(69,41,28,.17); }
    .flash-card-tag { color:#8d7a5b; font-size:.72rem; letter-spacing:.16em; text-transform:uppercase; }
    .flash-card-title { color:#3b281c; font:500 1.9rem/1.25 'Playfair Display',Georgia,serif; margin:1rem 0; }
    .flash-card-copy { color:#55483a; font-size:1.08rem; line-height:1.75; }
    .flash-card-hint { color:#9a8d75; font-size:.86rem; margin-top:1.6rem; }
    @media(max-width:640px) { .flash-card { min-height:260px; padding:1.5rem; } .flash-card-title { font-size:1.55rem; } }
    </style>
    """,
    unsafe_allow_html=True,
)

st.caption(f"{category}  ·  {index + 1:02d} / {len(cards):02d}  ·  {chapter}")
if revealed:
    title = "Quick answer"
    copy = answer
    hint = "Tap ‘Show prompt’ to hide the answer."
else:
    title = prompt
    copy = "Think of the key idea or formula, then reveal the back of the card."
    hint = "Your turn · recall it before you reveal."

st.markdown(
    f'<div class="flash-card"><div><div class="flash-card-tag">{category} · Class 11 Physics</div>'
    f'<div class="flash-card-title">{title}</div><div class="flash-card-copy">{copy}</div></div>'
    f'<div class="flash-card-hint">{hint}</div></div>',
    unsafe_allow_html=True,
)

left, middle, right = st.columns([1, 1.3, 1])
with left:
    if st.button("← Previous", use_container_width=True, key="physics_flashcard_previous"):
        st.session_state[state_key] = (index - 1) % len(cards)
        st.session_state[flip_key] = False
        st.rerun()
with middle:
    if st.button("Show prompt" if revealed else "Reveal answer", type="primary", use_container_width=True, key="physics_flashcard_flip"):
        st.session_state[flip_key] = not revealed
        st.rerun()
with right:
    if st.button("Next →", use_container_width=True, key="physics_flashcard_next"):
        st.session_state[state_key] = (index + 1) % len(cards)
        st.session_state[flip_key] = False
        st.rerun()

st.progress((index + 1) / len(cards), text=f"Card {index + 1} of {len(cards)}")
st.info("Demo revision aid for common Class 11 Physics topics. Check your prescribed textbook and syllabus for exact coverage.")
