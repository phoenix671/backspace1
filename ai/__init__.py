from ai.exceptions import AIError
from ai.gif import generate_gif
from ai.rag import extract_question_from_book, find_pyqs, ingest_book
from ai.solution import (
    generate_question,
    get_topics_and_formulae,
    simplify_question,
    solve_question,
)
from ai.video import find_videos
from ai.vision import analyze_attempt, extract_question_from_image

__all__ = [
    "AIError",
    "ingest_book",
    "extract_question_from_book",
    "extract_question_from_image",
    "analyze_attempt",
    "get_topics_and_formulae",
    "simplify_question",
    "generate_gif",
    "solve_question",
    "find_pyqs",
    "generate_question",
    "find_videos",
]

