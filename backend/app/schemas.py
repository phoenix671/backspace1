from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: UserOut


class QuestionOut(BaseModel):
    id: int
    text: str
    topic: str
    subject: str
    image_url: Optional[str]


class SessionOut(BaseModel):
    id: int
    source: str
    status: str
    question: QuestionOut
    homework_id: Optional[int]
    followup_of: Optional[int]
    followup_index: Optional[int]
    attempts_used: int
    max_attempts: int
    followup_triggered: bool
    created_at: str


class AttemptOut(BaseModel):
    id: int
    trial_number: int
    image_url: Optional[str]
    verdict: str
    stage: str
    submitted_at: str


class SessionDetailOut(BaseModel):
    session: SessionOut
    attempts: list[AttemptOut]


class DiagnosisItem(BaseModel):
    step_number: int
    student_wrote: str
    expected: str
    mistake_type: str
    description: str


class AttemptInfo(BaseModel):
    id: int
    trial_number: int
    image_url: Optional[str] = None
    submitted_at: str


class TopicsAndFormulae(BaseModel):
    topics: list[str]
    formulae: list[str]


class GifInfo(BaseModel):
    status: str
    url: Optional[str] = None


class SimplifiedQuestion(BaseModel):
    text: str
    gif: GifInfo


class SolutionStep(BaseModel):
    step_number: int
    text: str


class Shortcut(BaseModel):
    title: str
    text: str


class EfficientMethod(BaseModel):
    title: str
    steps: list[str]


class FullSolution(BaseModel):
    steps: list[SolutionStep]
    final_answer: str
    shortcuts: list[Shortcut]
    efficient_method: EfficientMethod


class AttemptResponse(BaseModel):
    attempt: AttemptInfo
    verdict: str
    stage: str
    message: str
    diagnosis: list[DiagnosisItem]
    topics_and_formulae: Optional[TopicsAndFormulae] = None
    simplified_question: Optional[SimplifiedQuestion] = None
    full_solution: Optional[FullSolution] = None
    efficient_method: Optional[EfficientMethod] = None
    attempts_used: int
    session_status: str
    followup_triggered: bool




class GifResponse(BaseModel):
    status: str
    url: Optional[str] = None
    error: Optional[str] = None


class FollowupsResponse(BaseModel):
    followups: list[SessionOut]


class TeacherCreateRequest(BaseModel):
    name: str
    subject: str
    phone: Optional[str] = None


class TeacherInfo(BaseModel):
    id: int
    name: str
    subject: str
    email: Optional[str] = None


class TeacherCredentials(BaseModel):
    email: str
    initial_password: str


class TeacherCreateResponse(BaseModel):
    teacher: TeacherInfo
    credentials: TeacherCredentials


class TeacherListResponse(BaseModel):
    teachers: list[TeacherInfo]


class StudentInput(BaseModel):
    name: str
    roll_number: Optional[str] = None


class SubjectTeacherAssignment(BaseModel):
    subject: str
    teacher_id: int
    teacher_name: Optional[str] = None


class ClassCreateRequest(BaseModel):
    name: str
    students: list[StudentInput]
    subject_teachers: list[SubjectTeacherAssignment]


class ClassInfo(BaseModel):
    id: int
    name: str
    student_count: int


class StudentCredentials(BaseModel):
    student_id: int
    name: str
    email: str
    initial_password: str


class ClassCreateResponse(BaseModel):
    class_: ClassInfo = Field(..., alias="class")
    credentials: list[StudentCredentials]

    model_config = ConfigDict(populate_by_name=True)


class ClassListResponse(BaseModel):
    classes: list[ClassInfo]


class StudentDetail(BaseModel):
    id: int
    name: str
    roll_number: Optional[str] = None
    email: str


class ClassDetailResponse(BaseModel):
    id: int
    name: str
    students: list[StudentDetail]
    subject_teachers: list[SubjectTeacherAssignment]


class AddStudentRequest(BaseModel):
    name: str
    roll_number: Optional[str] = None


class StudentSummary(BaseModel):
    id: int
    name: str


class AddStudentResponse(BaseModel):
    student: StudentSummary
    credentials: TeacherCredentials


class UpdateSubjectTeachersRequest(BaseModel):
    subject_teachers: list[SubjectTeacherAssignment]


class BookInfo(BaseModel):
    id: int
    name: str
    type: str
    subject: str
    status: str
    page_count: Optional[int] = None
    error: Optional[str] = None


class BookListResponse(BaseModel):
    books: list[BookInfo]


class TeacherClassInfo(BaseModel):
    class_id: int
    name: str
    subject: str
    student_count: int


class TeacherClassesResponse(BaseModel):
    classes: list[TeacherClassInfo]


class HomeworkCreateRequest(BaseModel):
    book_id: int
    chapter: Optional[str] = None
    question_ref: str
    title: Optional[str] = None
    due_at: Optional[str] = None


class BookSummary(BaseModel):
    id: int
    name: str


class HomeworkDetail(BaseModel):
    id: int
    class_id: int
    title: Optional[str] = None
    book: BookSummary
    chapter: Optional[str] = None
    question_ref: str
    question_text: str
    topic: str
    assigned_at: str
    due_at: Optional[str] = None


class HomeworkSummaryItem(BaseModel):
    id: int
    title: Optional[str] = None
    topic: str
    assigned_at: str
    due_at: Optional[str] = None
    completed: int
    total: int


class TeacherHomeworkListResponse(BaseModel):
    homework: list[HomeworkSummaryItem]


class StudentCompletionInfo(BaseModel):
    student_id: int
    name: str
    completed: bool
    completed_at: Optional[str] = None


class HomeworkCompletionSummary(BaseModel):
    completed: int
    total: int
    students: list[StudentCompletionInfo]


class HomeworkGraphResponse(BaseModel):
    id: int
    title: Optional[str] = None
    question_text: str
    topic: str
    due_at: Optional[str] = None
    completion: HomeworkCompletionSummary


class StrugglingTopicInfo(BaseModel):
    topic: str
    struggling_students: int
    total_students: int
    top_mistake_type: Optional[str] = None


class RecentQueryItem(BaseModel):
    student: StudentSummary
    question_text: str
    topic: str
    source: str
    attempts_used: int
    status: str
    last_mistake_type: Optional[str] = None
    at: str


class ClassStatusResponse(BaseModel):
    class_id: int
    subject: str
    struggling_topics: list[StrugglingTopicInfo]
    recent_queries: list[RecentQueryItem]


class StudentHomeworkItem(BaseModel):
    homework_id: int
    title: Optional[str] = None
    subject: str
    topic: str
    teacher_name: str
    assigned_at: str
    due_at: Optional[str] = None
    status: str
    session_id: Optional[int] = None


class StudentHomeworkListResponse(BaseModel):
    homework: list[StudentHomeworkItem]


class StartHomeworkSessionRequest(BaseModel):
    homework_id: int


class StartPyqSessionRequest(BaseModel):
    book_id: int
    chapter: Optional[str] = None
    question_ref: str


class StudentTotals(BaseModel):
    sessions: int
    solved: int
    avg_attempts: float


class TopicMistakeCounts(BaseModel):
    sign_error: int = 0
    formula_misuse: int = 0
    unit_slip: int = 0
    concept_gap: int = 0


class TopicStatInfo(BaseModel):
    topic: str
    subject: str
    status: str
    sessions: int
    mistake_counts: TopicMistakeCounts


class MistakeTypeStat(BaseModel):
    type: str
    count: int


class StudentStatsResponse(BaseModel):
    totals: StudentTotals
    topics: list[TopicStatInfo]
    mistake_types: list[MistakeTypeStat]


class VideoItem(BaseModel):
    title: str
    url: str
    channel: str
    kind: str


class VideosResponse(BaseModel):
    videos: list[VideoItem]
