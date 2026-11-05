# Neura API Contract v0.1

Source of truth for frontend (Streamlit), backend (FastAPI + MySQL) and AI module.
Built from `app_description2.docx`. If this file and the code disagree, the code is wrong. If this file is wrong, fix it, commit it, and tell the team.

- **Part A**: public REST API (Streamlit frontend <-> FastAPI backend)
- **Part B**: AI module interface (FastAPI backend <-> `/ai` Python package)
- **Part C**: assumptions and open questions (read these first, a few need a team decision)

---

## 0. Conventions

| Item | Rule |
|---|---|
| Base URL | `http://localhost:8000/api/v1` |
| Format | JSON in and out. Files use `multipart/form-data`. |
| Auth | `Authorization: Bearer <token>` on everything except login. Token comes from E1. |
| IDs | Integers. |
| Timestamps | ISO 8601 UTC, e.g. `2026-11-20T09:30:00Z`. |
| Files | Saved by the backend, served at `/files/<path>`. Responses contain `url` fields starting with `/files/`. |
| Slow endpoints | Marked with a timeout. Frontend must show a loading state and handle 504. |
| Priority | P1 = first end-to-end slice. P2 = rest of the core loop and setup. P3 = polish. Build in `E` order inside a tier. |

### Error shape (all non-2xx)

```json
{ "error": { "code": "validation_error", "message": "Human readable text", "details": {} } }
```

| HTTP | code | When |
|---|---|---|
| 401 | `unauthorized` | Missing/invalid token, wrong login |
| 403 | `forbidden` | Role not allowed, or resource belongs to someone else |
| 404 | `not_found` | ID does not exist |
| 404 | `question_not_found` | AI could not find the requested question in the book |
| 409 | `conflict` | e.g. session already closed, duplicate |
| 422 | `validation_error` | Bad or missing fields, unsupported file type |
| 422 | `image_unreadable` | AI could not read the uploaded image |
| 503 | `ai_unavailable` | AI call failed or returned invalid output after one retry |
| 504 | `ai_timeout` | AI call exceeded its timeout |

### Enums

| Name | Values |
|---|---|
| `role` | `faculty`, `teacher`, `student` |
| `mistake_type` | `sign_error`, `formula_misuse`, `unit_slip`, `concept_gap` |
| `book_type` | `textbook`, `pyq`, `question_bank` |
| `book_status` | `processing`, `ready`, `failed` |
| `session_source` | `homework`, `pyq`, `upload`, `followup_pyq`, `followup_generated` |
| `session_status` | `awaiting_attempt`, `solved`, `revealed`, `skipped` |
| `verdict` | `correct`, `incorrect`, `unclear` |
| `stage` | `hints`, `simplified`, `revealed`, `solved`, `retry` |

### Role access summary

| Group | faculty | teacher | student |
|---|---|---|---|
| `/auth/*` | yes | yes | yes |
| `/faculty/*` | yes | no | no |
| `/teacher/*` | no | yes (own classes only) | no |
| `/student/*` | no | no | yes (own data only) |
| `/books*` | yes | yes (own subjects only) | yes (all ready books) |

---

## 1. Endpoint index

| # | Method | Path | Role | Pri |
|---|---|---|---|---|
| E1 | POST | `/auth/login` | any | P1 |
| E2 | GET | `/auth/me` | any | P1 |
| E3 | POST | `/student/sessions/upload` | student | P1 |
| E4 | GET | `/student/sessions/{session_id}` | student | P1 |
| E5 | POST | `/student/sessions/{session_id}/attempts` | student | P1 |
| E6 | GET | `/student/sessions/{session_id}/gif` | student | P2 |
| E7 | POST | `/student/sessions/{session_id}/followups` | student | P2 |
| E8 | POST | `/student/sessions/{session_id}/skip` | student | P2 |
| E9 | POST | `/faculty/teachers` | faculty | P2 |
| E10 | GET | `/faculty/teachers` | faculty | P2 |
| E11 | POST | `/faculty/classes` | faculty | P2 |
| E12 | GET | `/faculty/classes` | faculty | P2 |
| E13 | GET | `/faculty/classes/{class_id}` | faculty | P2 |
| E14 | POST | `/faculty/books` | faculty | P2 |
| E15 | GET | `/books` | any | P2 |
| E16 | GET | `/books/{book_id}` | any | P2 |
| E17 | GET | `/books/{book_id}/file` | any | P2 |
| E18 | GET | `/teacher/classes` | teacher | P2 |
| E19 | POST | `/teacher/classes/{class_id}/homework` | teacher | P2 |
| E20 | GET | `/teacher/classes/{class_id}/homework` | teacher | P2 |
| E21 | GET | `/teacher/homework/{homework_id}` | teacher | P2 |
| E22 | GET | `/student/homework` | student | P2 |
| E23 | POST | `/student/sessions/homework` | student | P2 |
| E24 | POST | `/student/sessions/pyq` | student | P2 |
| E25 | GET | `/student/stats` | student | P3 |
| E26 | GET | `/teacher/classes/{class_id}/status` | teacher | P3 |
| E27 | GET | `/student/sessions/{session_id}/videos` | student | P3 |
| E28 | POST | `/faculty/classes/{class_id}/students` | faculty | P3 |
| E29 | DELETE | `/faculty/classes/{class_id}/students/{student_id}` | faculty | P3 |
| E30 | PUT | `/faculty/classes/{class_id}/subject-teachers` | faculty | P3 |

---

# PART A: Public API

## A1. Auth

### E1 `POST /auth/login` (P1, any)

The role is **not** sent by the client. The backend decides it from the email domain (see Part C, item 1).

Request:
```json
{ "email": "asha.r@student.class.com", "password": "mock1234" }
```

Response 200:
```json
{
  "token": "eyJhbGciOi...",
  "token_type": "bearer",
  "user": { "id": 12, "name": "Asha R", "email": "asha.r@student.class.com", "role": "student" }
}
```

Errors: 401 `unauthorized` (wrong email or password, or unknown domain).

### E2 `GET /auth/me` (P1, any)

Response 200: the same `user` object as above.

---

## A2. Student: solving a question

All solving goes through a **session**. A session is one question and up to 3 uploaded solutions. It is created from homework (E23), a PYQ (E24), or an uploaded question (E3). Follow-up questions (E7) are also sessions and follow the same flow.

### Session object

```json
{
  "id": 101,
  "source": "upload",
  "status": "awaiting_attempt",
  "question": {
    "id": 55,
    "text": "Solve x^2 - 5x + 6 = 0",
    "topic": "Quadratic equations",
    "subject": "Mathematics",
    "image_url": "/files/uploads/q_55.png"
  },
  "homework_id": null,
  "followup_of": null,
  "followup_index": null,
  "attempts_used": 0,
  "max_attempts": 3,
  "followup_triggered": false,
  "created_at": "2026-11-20T09:30:00Z"
}
```

- `image_url` is null unless the question was uploaded as an image.
- `followup_of` / `followup_index` (1 to 3) are set only on follow-up sessions.
- `followup_triggered` is true when the student needed all 3 attempts (see Part C, item 7). It is always false on follow-up sessions.

### E3 `POST /student/sessions/upload` (P1, student)

The "Upload a question" button under DIY. Timeout 60 s (vision call).

Request `multipart/form-data`: `image` (png/jpg, max 5 MB) **or** `text` (string). At least one is required.

Response 201: Session object. The AI fills in `question.text`, `topic` and `subject`.

Errors: 422 `validation_error` (nothing sent, wrong file type), 422 `image_unreadable`, 503, 504.

### E4 `GET /student/sessions/{session_id}` (P1, student)

Response 200: Session object plus the attempts so far.

```json
{
  "session": { "...Session object..." },
  "attempts": [
    {
      "id": 7,
      "trial_number": 1,
      "image_url": "/files/attempts/a_7.png",
      "verdict": "incorrect",
      "stage": "hints",
      "submitted_at": "2026-11-20T09:35:00Z"
    }
  ]
}
```

Use this to resume a session after a Streamlit rerun.

### E5 `POST /student/sessions/{session_id}/attempts` (P1, student)

The core endpoint. The student uploads a photo of their solution. Timeout 60 s.

Request `multipart/form-data`: `image` (png/jpg, max 5 MB, required).

Response 200:

```json
{
  "attempt": {
    "id": 7,
    "trial_number": 1,
    "image_url": "/files/attempts/a_7.png",
    "submitted_at": "2026-11-20T09:35:00Z"
  },
  "verdict": "incorrect",
  "stage": "hints",
  "message": "You are close. Check step 2.",
  "diagnosis": [
    {
      "step_number": 2,
      "student_wrote": "x^2 - 5x = -6  ->  x(x - 5) = 6",
      "expected": "x(x - 5) = -6",
      "mistake_type": "sign_error",
      "description": "The sign flipped when moving a term across the equals sign."
    }
  ],
  "topics_and_formulae": null,
  "simplified_question": null,
  "full_solution": null,
  "efficient_method": null,
  "attempts_used": 1,
  "session_status": "awaiting_attempt",
  "followup_triggered": false
}
```

**What the backend does, in order**

| Result | attempts_used | `stage` | Fields filled | `session_status` |
|---|---|---|---|---|
| Image unclear / unreadable | unchanged (does not use a trial) | `retry` | `message` only, `diagnosis` is `[]` | `awaiting_attempt` |
| Correct | +1 | `solved` | `efficient_method` only if this was the first attempt, else null | `solved` |
| Wrong, 1st attempt | 1 | `hints` | `diagnosis`. Also `topics_and_formulae` if `source` is `pyq` or `followup_pyq` | `awaiting_attempt` |
| Wrong, 2nd attempt | 2 | `simplified` | `diagnosis`, `simplified_question` (GIF starts as `pending`, poll E6) | `awaiting_attempt` |
| Wrong, 3rd attempt | 3 | `revealed` | `diagnosis`, `full_solution` | `revealed` |

- `diagnosis` is present on every wrong attempt. The backend saves each item to the student's mistake history. The frontend shows it as hints on trial 1.
- `followup_triggered` is true when `attempts_used` reaches 3 (solved on the 3rd attempt, or revealed). Not set on follow-up sessions.
- Wrong or correct on a session that is not `awaiting_attempt` returns 409 `conflict`.

**`topics_and_formulae`** (PYQ only, trial 1):
```json
{ "topics": ["Factorisation", "Quadratic equations"], "formulae": ["ax^2 + bx + c = 0", "x = (-b ± sqrt(b^2 - 4ac)) / 2a"] }
```

**`simplified_question`** (trial 2):
```json
{
  "text": "Find two numbers that multiply to 6 and add up to -5, then use them to split the middle term.",
  "gif": { "status": "pending", "url": null }
}
```

**`full_solution`** (trial 3):
```json
{
  "steps": [
    { "step_number": 1, "text": "Split the middle term: x^2 - 2x - 3x + 6 = 0" },
    { "step_number": 2, "text": "Group: x(x - 2) - 3(x - 2) = 0" }
  ],
  "final_answer": "x = 2 or x = 3",
  "shortcuts": [ { "title": "Sum and product", "text": "Roots add to 5 and multiply to 6, so 2 and 3." } ],
  "efficient_method": { "title": "Factorise directly", "steps": ["(x - 2)(x - 3) = 0", "x = 2 or x = 3"] }
}
```

**`efficient_method`** (correct on 1st attempt): same shape as the one inside `full_solution`.

Errors: 404, 409 `conflict`, 422 `validation_error`, 503, 504.

### E6 `GET /student/sessions/{session_id}/gif` (P2, student)

Poll every 2 s after a `simplified` stage. The GIF is generated in the background.

Response 200:
```json
{ "status": "ready", "url": "/files/gifs/q_55.gif", "error": null }
```
`status` is `pending`, `ready` or `failed`. On `failed`, the frontend just shows the simplified text.

### E7 `POST /student/sessions/{session_id}/followups` (P2, student)

Creates the three follow-up questions: 2 PYQs and 1 AI-generated question based on the topic the student failed and their mistake history. Timeout 60 s. Idempotent: calling again returns the same three.

No request body.

Response 201:
```json
{
  "followups": [
    { "...Session object...", "source": "followup_pyq", "followup_of": 101, "followup_index": 1 },
    { "...Session object...", "source": "followup_pyq", "followup_of": 101, "followup_index": 2 },
    { "...Session object...", "source": "followup_generated", "followup_of": 101, "followup_index": 3 }
  ]
}
```

Rules: allowed only if the parent session has `followup_triggered: true`, else 409 `conflict`. If fewer than 2 PYQs exist for the topic, the AI fills with generated questions so there are always 3. Errors: 404, 409, 503, 504.

### E8 `POST /student/sessions/{session_id}/skip` (P2, student)

Skips one follow-up question. Only follow-up sessions can be skipped. Homework, PYQ and upload sessions return 403 `forbidden`.

Response 200: Session object with `status: "skipped"`.

### E23 `POST /student/sessions/homework` (P2, student)

Starts a homework question. Idempotent: if the student already has a session for this homework, it returns that session (resume).

Request:
```json
{ "homework_id": 9 }
```
Response 201 (or 200 when resumed): Session object with `source: "homework"` and `homework_id` set. The question text is the one the AI extracted when the teacher created the homework (E19). Errors: 403 (homework is not for the student's class), 404.

### E24 `POST /student/sessions/pyq` (P2, student)

Starts a PYQ question from a book. Timeout 30 s (RAG lookup).

Request:
```json
{ "book_id": 4, "chapter": "Quadratic Equations", "question_ref": "Q3" }
```
`chapter` is optional. Response 201: Session object with `source: "pyq"`. Errors: 404 `question_not_found`, 404 (book), 409 (book not `ready`), 503, 504.

### E22 `GET /student/homework` (P2, student)

Response 200:
```json
{
  "homework": [
    {
      "homework_id": 9,
      "title": "Quadratics practice",
      "subject": "Mathematics",
      "topic": "Quadratic equations",
      "teacher_name": "Ravi K",
      "assigned_at": "2026-11-18T08:00:00Z",
      "due_at": "2026-11-22T18:00:00Z",
      "status": "not_started",
      "session_id": null
    }
  ]
}
```
`status` is `not_started`, `in_progress` or `completed`. `session_id` is set once the student has started. Sorted by `due_at` ascending, nulls last.

### E25 `GET /student/stats` (P3, student)

Home page statistics.

Response 200:
```json
{
  "totals": { "sessions": 24, "solved": 20, "avg_attempts": 1.8 },
  "topics": [
    {
      "topic": "Quadratic equations",
      "subject": "Mathematics",
      "status": "weak",
      "sessions": 5,
      "mistake_counts": { "sign_error": 3, "formula_misuse": 1, "unit_slip": 0, "concept_gap": 0 }
    }
  ],
  "mistake_types": [ { "type": "sign_error", "count": 9 } ]
}
```
`status` is `strong`, `learning` or `weak`. Rule v1 (tune later): looking at the last 5 sessions on a topic, `weak` if there are at least 2 and at least half used all 3 attempts. `strong` if there are at least 3 and at least 70% were solved on attempt 1 or 2. Otherwise `learning`.

### E27 `GET /student/sessions/{session_id}/videos` (P3, student)

The YouTube toggle. Available at any time in a session. Timeout 20 s. Cached per question.

Response 200:
```json
{
  "videos": [
    { "title": "Quadratic equations by factorisation", "url": "https://www.youtube.com/watch?v=abc123", "channel": "Example Channel", "kind": "topic_explainer" },
    { "title": "Solving x^2 - 5x + 6 = 0", "url": "https://www.youtube.com/watch?v=def456", "channel": "Example Channel", "kind": "question_solution" }
  ]
}
```
`kind` is `topic_explainer` or `question_solution`. An empty list is valid.

---

## A3. Faculty

### E9 `POST /faculty/teachers` (P2, faculty)

Request:
```json
{ "name": "Ravi K", "subject": "Mathematics", "phone": "9876543210" }
```
`phone` is optional.

Response 201:
```json
{
  "teacher": { "id": 3, "name": "Ravi K", "subject": "Mathematics" },
  "credentials": { "email": "ravi.k@teacher.class.com", "initial_password": "mock4821" }
}
```
The email is generated from the name. If it already exists, a number is added (`ravi.k2@...`). Credentials are returned only in this response.

### E10 `GET /faculty/teachers` (P2, faculty)

Response 200:
```json
{ "teachers": [ { "id": 3, "name": "Ravi K", "subject": "Mathematics", "email": "ravi.k@teacher.class.com" } ] }
```

### E11 `POST /faculty/classes` (P2, faculty)

The student count in the UI is only used to show that many rows. The request just carries the list.

Request:
```json
{
  "name": "10-A",
  "students": [ { "name": "Asha R", "roll_number": "1" }, { "name": "Kiran S", "roll_number": "2" } ],
  "subject_teachers": [ { "subject": "Mathematics", "teacher_id": 3 }, { "subject": "Physics", "teacher_id": 5 } ]
}
```
`roll_number` is optional. `students` needs at least 1 entry. Each `teacher_id` must exist.

Response 201:
```json
{
  "class": { "id": 2, "name": "10-A", "student_count": 2 },
  "credentials": [
    { "student_id": 12, "name": "Asha R", "email": "asha.r@student.class.com", "initial_password": "mock7310" },
    { "student_id": 13, "name": "Kiran S", "email": "kiran.s@student.class.com", "initial_password": "mock2290" }
  ]
}
```
Credentials are shown once. The frontend should let faculty download or copy them.

Errors: 422 (empty students, unknown teacher), 409 (class name already exists).

### E12 `GET /faculty/classes` (P2, faculty)

Response 200:
```json
{ "classes": [ { "id": 2, "name": "10-A", "student_count": 2 } ] }
```

### E13 `GET /faculty/classes/{class_id}` (P2, faculty)

The edit page.

Response 200:
```json
{
  "id": 2,
  "name": "10-A",
  "students": [ { "id": 12, "name": "Asha R", "roll_number": "1", "email": "asha.r@student.class.com" } ],
  "subject_teachers": [ { "subject": "Mathematics", "teacher_id": 3, "teacher_name": "Ravi K" } ]
}
```

### E28 `POST /faculty/classes/{class_id}/students` (P3, faculty)

Request: `{ "name": "Meera T", "roll_number": "3" }`
Response 201: `{ "student": { "id": 14, "name": "Meera T" }, "credentials": { "email": "...", "initial_password": "..." } }`

### E29 `DELETE /faculty/classes/{class_id}/students/{student_id}` (P3, faculty)

Removes the student from the class and deactivates the account. Their mistake history is kept. Response 204.

### E30 `PUT /faculty/classes/{class_id}/subject-teachers` (P3, faculty)

Replaces the class's subject-teacher assignments.

Request:
```json
{ "subject_teachers": [ { "subject": "Mathematics", "teacher_id": 4 } ] }
```
Response 200: the `subject_teachers` array as in E13.

### E14 `POST /faculty/books` (P2, faculty)

"Update syllabus" -> "Add book". Upload a PDF and name it.

Request `multipart/form-data`: `file` (pdf, max 50 MB), `name` (string), `type` (`textbook`, `pyq` or `question_bank`), `subject` (string).

Response 202:
```json
{ "id": 4, "name": "Maths Class 10 PYQs", "type": "pyq", "subject": "Mathematics", "status": "processing" }
```
The RAG indexing runs in the background. Poll E16 until `ready`. Errors: 422 (not a pdf, too large, missing fields), 409 (a book with this name already exists).

---

## A4. Books (shared)

### E15 `GET /books` (P2, any)

Query params (all optional): `q` (case-insensitive name contains), `type`, `subject`.

Visibility: faculty sees all. A teacher sees only books whose subject they teach. A student sees all books with `status: "ready"`.

Response 200:
```json
{ "books": [ { "id": 4, "name": "Maths Class 10 PYQs", "type": "pyq", "subject": "Mathematics", "status": "ready", "page_count": 120 } ] }
```

### E16 `GET /books/{book_id}` (P2, any)

Response 200: one book object as above, plus `"error": null` (a message when `status` is `failed`).

### E17 `GET /books/{book_id}/file` (P2, any)

Returns the PDF (`application/pdf`). Same visibility rules as E15.

---

## A5. Teacher

### E18 `GET /teacher/classes` (P2, teacher)

Response 200:
```json
{ "classes": [ { "class_id": 2, "name": "10-A", "subject": "Mathematics", "student_count": 30 } ] }
```
One row per class and subject the teacher teaches.

### E19 `POST /teacher/classes/{class_id}/homework` (P2, teacher)

Request:
```json
{
  "book_id": 4,
  "chapter": "Quadratic Equations",
  "question_ref": "Exercise 4.2, Q3",
  "title": "Quadratics practice",
  "due_at": "2026-11-22T18:00:00Z"
}
```
`title` and `due_at` are optional. The backend asks the AI to find the question in the book (RAG) at creation time and stores the text and topic. Timeout 30 s.

Response 201:
```json
{
  "id": 9,
  "class_id": 2,
  "title": "Quadratics practice",
  "book": { "id": 4, "name": "Maths Class 10 PYQs" },
  "chapter": "Quadratic Equations",
  "question_ref": "Exercise 4.2, Q3",
  "question_text": "Solve x^2 - 5x + 6 = 0",
  "topic": "Quadratic equations",
  "assigned_at": "2026-11-18T08:00:00Z",
  "due_at": "2026-11-22T18:00:00Z"
}
```
Errors: 404 `question_not_found` (nothing is created, the teacher fixes the reference), 403 (not the teacher of this class), 409 (book not `ready`), 503, 504.

### E20 `GET /teacher/classes/{class_id}/homework` (P2, teacher)

Response 200:
```json
{
  "homework": [
    { "id": 9, "title": "Quadratics practice", "topic": "Quadratic equations", "assigned_at": "2026-11-18T08:00:00Z", "due_at": "2026-11-22T18:00:00Z", "completed": 12, "total": 30 }
  ]
}
```
Newest first.

### E21 `GET /teacher/homework/{homework_id}` (P2, teacher)

Data for the bar graph. A student counts as **completed** when their session for this homework has status `solved` or `revealed`.

Response 200:
```json
{
  "id": 9,
  "title": "Quadratics practice",
  "question_text": "Solve x^2 - 5x + 6 = 0",
  "topic": "Quadratic equations",
  "due_at": "2026-11-22T18:00:00Z",
  "completion": {
    "completed": 12,
    "total": 30,
    "students": [
      { "student_id": 12, "name": "Asha R", "completed": true, "completed_at": "2026-11-19T10:00:00Z" },
      { "student_id": 13, "name": "Kiran S", "completed": false, "completed_at": null }
    ]
  }
}
```

### E26 `GET /teacher/classes/{class_id}/status` (P3, teacher)

"Class status" page. Only covers the teacher's subject for that class. Built from the students' mistake history.

Response 200:
```json
{
  "class_id": 2,
  "subject": "Mathematics",
  "struggling_topics": [
    { "topic": "Quadratic equations", "struggling_students": 9, "total_students": 30, "top_mistake_type": "sign_error" }
  ],
  "recent_queries": [
    {
      "student": { "id": 12, "name": "Asha R" },
      "question_text": "Solve x^2 - 5x + 6 = 0",
      "topic": "Quadratic equations",
      "source": "upload",
      "attempts_used": 3,
      "status": "revealed",
      "last_mistake_type": "sign_error",
      "at": "2026-11-19T10:00:00Z"
    }
  ]
}
```
"Struggling" uses the same `weak` rule as E25. `recent_queries` is the latest 50 sessions in the class for that subject. Sorted newest first.

---

# PART B: AI module interface (backend <-> `/ai`)

The AI module is a Python package. The backend imports and calls these functions directly. They are plain functions: JSON-like `dict` in, `dict` out. **The AI module never touches MySQL.** The backend reads the data, passes it in, and saves what comes back.

Rules for all functions:
- Output must match the shapes below. Validate against a schema and retry once on invalid output, then raise `AIError`.
- On failure raise `AIError(code, message)` with code `ai_unavailable`, `ai_timeout` or `image_unreadable`. The backend maps these to the HTTP errors in section 0.
- Image inputs are file paths on disk, not bytes.

### Mistake history row (input to several functions)

Newest first, capped at the 50 most recent. The AI module applies the recency weighting itself.
```json
{ "topic": "Quadratic equations", "mistake_type": "sign_error", "step_number": 2, "description": "The sign flipped...", "created_at": "2026-11-18T09:00:00Z" }
```

### B1 `ingest_book(book_id, file_path, name, subject, type) -> dict`
Builds the RAG index for a PDF. Blocking, run in a background task by the backend (used by E14).
```json
{ "status": "ready", "page_count": 120, "chunk_count": 640, "error": null }
```

### B2 `extract_question_from_book(book_id, chapter, question_ref) -> dict`
Searches the RAG index for the question the teacher or student named (used by E19, E24).
```json
{ "found": true, "question_text": "Solve x^2 - 5x + 6 = 0", "topic": "Quadratic equations", "subject": "Mathematics", "confidence": 0.9 }
```
`found: false` -> backend returns 404 `question_not_found`.

### B3 `extract_question_from_image(image_path) -> dict`
Reads a photographed question (used by E3).
```json
{ "readable": true, "question_text": "Solve x^2 - 5x + 6 = 0", "topic": "Quadratic equations", "subject": "Mathematics" }
```
`readable: false` -> backend returns 422 `image_unreadable`.

### B4 `analyze_attempt(question, solution_image_path, trial_number, mistake_history) -> dict`
Reads the student's handwritten solution and compares it to the correct solution. `question` is `{ "text", "topic", "subject" }`.
```json
{
  "verdict": "incorrect",
  "message": "You are close. Check step 2.",
  "diagnosis": [
    { "step_number": 2, "student_wrote": "...", "expected": "...", "mistake_type": "sign_error", "description": "..." }
  ]
}
```
- `verdict: "unclear"` when the image cannot be read or no judgement can be made. Then `diagnosis` is `[]`.
- `verdict: "correct"` -> `diagnosis` is `[]`.
- `mistake_type` must be one of the 4 fixed values. `mistake_history` should shape the hint wording, e.g. mention a repeated mistake.
- Hints must not reveal the final answer.

### B5 `get_topics_and_formulae(question_text, topic) -> dict`
Used for PYQ trial-1 hints (E5).
```json
{ "topics": ["Factorisation"], "formulae": ["ax^2 + bx + c = 0"] }
```

### B6 `simplify_question(question_text, topic, diagnosis) -> dict`
Used for the trial-2 stage.
```json
{ "simplified_text": "Find two numbers that multiply to 6 and add up to -5..." }
```

### B7 `generate_gif(question_text, simplified_text, out_path) -> dict`
Creates an explanatory GIF at `out_path`. Blocking, run in a background task (E6 polls it).
```json
{ "status": "ready", "gif_path": "/files/gifs/q_55.gif" }
```
`status` is `ready` or `failed`.

### B8 `solve_question(question_text, topic, diagnosis) -> dict`
Full solution with shortcuts and the most efficient method. Used for trial 3, and for the `efficient_method` on a first-attempt correct answer (the backend can pass an empty `diagnosis`).
```json
{
  "steps": [ { "step_number": 1, "text": "..." } ],
  "final_answer": "x = 2 or x = 3",
  "shortcuts": [ { "title": "Sum and product", "text": "..." } ],
  "efficient_method": { "title": "Factorise directly", "steps": ["..."] }
}
```

### B9 `find_pyqs(topic, subject, n, exclude_question_texts) -> dict`
Finds past-year questions for a topic from the RAG index (used by E7).
```json
{ "questions": [ { "question_text": "...", "topic": "...", "subject": "...", "book_id": 4, "reference": "2023 Q5" } ] }
```
May return fewer than `n`.

### B10 `generate_question(topic, subject, mistake_history) -> dict`
Creates one new question aimed at the student's weak spots (used by E7).
```json
{ "question_text": "...", "topic": "Quadratic equations", "subject": "Mathematics" }
```

### B11 `find_videos(topic, question_text) -> dict`
Uses the YouTube Data API (used by E27).
```json
{ "videos": [ { "title": "...", "url": "https://www.youtube.com/watch?v=...", "channel": "...", "kind": "topic_explainer" } ] }
```

---

# PART C: Assumptions and open questions

The description did not cover these, so this contract makes a choice. Confirm or change each one **before** building. Changing one later means everyone updates their copy.

1. **Login domains.** The description says the role comes from the email domain (e.g. `name@class.com`) but not the exact domains. Contract assumes three domains set in the backend `.env`: `FACULTY_DOMAIN`, `TEACHER_DOMAIN`, `STUDENT_DOMAIN`, with examples `faculty.class.com`, `teacher.class.com`, `student.class.com`.
2. **Teacher details.** Faculty enters name and subject (phone optional). The description only says "details of the teacher".
3. **Student details.** Name, with an optional roll number.
4. **Books carry a `subject` and a `type`.** Needed so a teacher sees only PDFs for their subject. Faculty picks both on upload.
5. **Homework due date.** The student view shows a "timeline", so `due_at` is optional on homework and `assigned_at` is always set.
6. **What a "query" means on the teacher's class status page.** Interpreted as the questions students worked on, with attempts used and the last mistake type (`recent_queries`).
7. **When follow-ups trigger.** Description says "more than two trials". Interpreted as the student used all 3 attempts (solved on the 3rd, or answer revealed).
8. **Unclear photos do not count as an attempt.** The student is asked to re-upload, the trial is not used.
9. **Efficient method on first-attempt correct only.** If solved on attempt 2 or 3, the response has no `efficient_method`. The `revealed` stage includes it.
10. **PYQ questions are picked by reference.** The student chooses a book and types a question number or reference (same as how teachers pick homework). The description only says the student finds the PDF by name.
11. **Homework completion.** A student counts as completed when the session ends `solved` or `revealed`.
12. **Skipping.** Only the three follow-up questions can be skipped, one at a time.
13. **Removing a student** deactivates the account and keeps their history.
14. **No change-password endpoint.** Initial passwords are "mock". Add one later if needed.
15. **Weak/strong topic rule** in E25 is a first version, tune it after testing with real data.

---

## Appendix: tables the API implies (MySQL)

`users` (id, name, email, password_hash, role, is_active) · `teachers` (user_id, subject, phone) · `classes` (id, name) · `class_students` (class_id, student_id, roll_number, is_active) · `class_subject_teachers` (class_id, subject, teacher_id) · `books` (id, name, type, subject, file_path, status, page_count, error) · `questions` (id, text, topic, subject, image_path, source_book_id, reference) · `homework` (id, class_id, teacher_id, book_id, chapter, question_ref, question_id, title, assigned_at, due_at) · `sessions` (id, student_id, question_id, source, status, homework_id, followup_of, followup_index, attempts_used, gif_status, gif_path, created_at) · `attempts` (id, session_id, trial_number, image_path, verdict, stage, submitted_at) · `mistake_history` (id, student_id, session_id, attempt_id, question_id, topic, subject, mistake_type, step_number, description, created_at) · `video_cache` (question_id, videos_json)
