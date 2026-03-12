import json
import os
import random
from datetime import date
from pathlib import Path
from typing import Any, Generator

import httpx
import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from assignment_2.pdf_service import generate_certificate
from database import Base, ParticipantRecord, SessionLocal, engine
from schemas import CertificateRequest, ParticipantRecordCreate, ParticipantRecordRead

load_dotenv()

app = FastAPI(title="Adaptive EASA Quiz")

BASE_DIR = Path(__file__).parent
PUBLIC_DIR = BASE_DIR / "public"

PORT = int(os.getenv("PORT", "3000"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODELS = [m.strip() for m in os.getenv("GEMINI_MODELS", "gemini-1.5-flash").split(",") if m.strip()]
JWT_SECRET = os.getenv("QUIZ_JWT_SECRET", "change-me-in-env")
JWT_ALGORITHM = "HS256"
USE_MOCK_LLM = os.getenv("USE_MOCK_LLM", "false").strip().lower() in {"1", "true", "yes", "on"}
MAX_QUESTIONS = 10
MAX_LEVEL = 10
TOPICS = ["Aviation Navigation", "Aviation Meteorology"]

Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class AIResponseFormatError(Exception):
    pass


def clamp_level(level: int) -> int:
    return max(1, min(MAX_LEVEL, level))


def normalize_int(value: Any, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, parsed))


def extract_json(raw_text: str) -> str:
    text = str(raw_text or "").strip()
    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1 or last <= first:
        raise ValueError("No valid JSON object found in response text.")
    return text[first : last + 1]


def parse_model_json(text: str) -> dict[str, Any]:
    candidate = extract_json(text)
    return json.loads(candidate)


def encode_state_token(state: dict[str, Any]) -> str:
    return jwt.encode(state, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_state_token(token: str) -> dict[str, Any]:
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=401, detail=f"Invalid token: {error}") from error

    required = ["current_level", "correct_count", "question_count", "correct_answer_key", "topics_pool"]
    missing = [key for key in required if key not in decoded]
    if missing:
        raise HTTPException(status_code=400, detail=f"Invalid token payload. Missing: {', '.join(missing)}")

    if not isinstance(decoded.get("topics_pool"), list):
        raise HTTPException(status_code=400, detail="Invalid token payload. topics_pool must be a list.")

    return decoded


async def request_gemini_text(prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("Missing GEMINI_API_KEY. Set it in .env before starting the server.")

    last_error = None
    async with httpx.AsyncClient(timeout=45.0) as client:
        for model in GEMINI_MODELS:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.8, "responseMimeType": "application/json"},
            }
            response = await client.post(url, json=payload)
            if response.status_code >= 400:
                last_error = RuntimeError(
                    f"Gemini model '{model}' error ({response.status_code}): {response.text}"
                )
                continue

            data = response.json()
            text = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}])[0].get("text")
            if not text:
                last_error = RuntimeError(f"Gemini model '{model}' returned an empty response.")
                continue
            return text

    raise last_error or RuntimeError("Gemini request failed for all configured models.")


async def call_gemini_json(prompt: str) -> dict[str, Any]:
    raw = await request_gemini_text(prompt)
    try:
        return parse_model_json(raw)
    except Exception:
        retry_prompt = (
            f"{prompt}\n\nYour previous output was not parseable JSON. "
            "Reply with ONLY one valid JSON object and no markdown or extra text."
        )
        retry_raw = await request_gemini_text(retry_prompt)
        try:
            return parse_model_json(retry_raw)
        except Exception as retry_error:
            raise AIResponseFormatError(
                f"Failed to parse Gemini JSON after one retry: {retry_error}"
            ) from retry_error


def mock_question(topic: str, level: int, question_number: int) -> dict[str, Any]:
    correct_text = "Apply the published EASA-compliant operational procedure."
    distractors = [
        "Use an FAA-only exception without EU validation.",
        "Ignore regulatory minima for operational convenience.",
        "Delay all flights regardless of weather and constraints.",
    ]
    options = [correct_text] + distractors
    random.shuffle(options)
    correct_option = ["A", "B", "C", "D"][options.index(correct_text)]

    return {
        "topic": "navigation" if "Navigation" in topic else "meteorology",
        "question": f"MOCK Q{question_number} (Level {level}): Under EASA dispatch standards for {topic}, what is the best action?",
        "options": options,
        "correctOption": correct_option,
        "explanation": "MOCK EXPLANATION: The EASA-compliant operational procedure is the correct choice.",
    }


async def generate_question(level: int, question_number: int, topic: str, last_result: dict[str, Any] | None) -> dict[str, Any]:
    normalized_level = clamp_level(level)
    normalized_qn = normalize_int(question_number, 1, 1, MAX_QUESTIONS)

    if last_result:
        adapt_hint = (
            f"The previous answer was {'correct' if last_result.get('correct') else 'incorrect'}. "
            f"Use this to adapt wording while keeping difficulty at level {normalized_level}."
        )
    else:
        adapt_hint = "This is the first question."

    if USE_MOCK_LLM:
        return mock_question(topic, normalized_level, normalized_qn)

    prompt = f"""
You are an expert EASA Flight Dispatcher examiner. Generate a multiple-choice question on the topic of {topic} at a difficulty level of {normalized_level} out of 10. The question must strictly adhere to European Union Aviation Safety Agency (EASA) regulations and frameworks, not FAA.
You must respond ONLY with a raw, valid JSON object. Do not include markdown formatting, backticks, or any conversational text. The JSON must strictly adhere to this schema: {{"question": "...", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "correct_option": "A"}}

Constraints:
- Question number in session: {normalized_qn} of {MAX_QUESTIONS}
- Difficulty must match level {normalized_level}
- Keep question practical and exam-like
- Provide 4 distinct options labeled A, B, C, D
- Exactly one option must be correct
- `correct_option` must be one of A/B/C/D
- Optional: include `explanation` in one or two sentences if possible
- Avoid repeating exact question patterns from typical rote banks
- {adapt_hint}

Return strict JSON object only:
{{
  "question": "...",
  "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
  "correct_option": "A"
}}
"""

    parsed = await call_gemini_json(prompt)
    parsed_options = parsed.get("options")
    if isinstance(parsed_options, dict):
        options = [
            str(parsed_options.get("A", "")).strip(),
            str(parsed_options.get("B", "")).strip(),
            str(parsed_options.get("C", "")).strip(),
            str(parsed_options.get("D", "")).strip(),
        ]
    elif isinstance(parsed_options, list) and len(parsed_options) == 4:
        options = [str(opt).strip() for opt in parsed_options]
    else:
        options = []

    correct_option = str(parsed.get("correct_option") or parsed.get("correctOption") or "").strip().upper()
    explanation = str(parsed.get("explanation") or "Generated question without explanation.").strip()

    if not parsed.get("question") or len(options) != 4 or correct_option not in {"A", "B", "C", "D"}:
        raise RuntimeError("Invalid question JSON from Gemini.")

    return {
        "topic": str(parsed.get("topic") or topic),
        "question": str(parsed["question"]).strip(),
        "options": options,
        "correctOption": correct_option,
        "explanation": explanation,
    }


def normalize_selected_option(answer: str, options: list[str]) -> str:
    normalized = answer.strip().upper()
    if normalized in {"A", "B", "C", "D"}:
        return normalized

    for idx, option in enumerate(options):
        if answer.strip().lower() == option.strip().lower():
            return ["A", "B", "C", "D"][idx]

    return ""


def evaluate_mcq_answer(question_data: dict[str, Any], user_answer: str) -> dict[str, Any]:
    options = question_data["options"]
    selected_option = normalize_selected_option(user_answer, options)
    correct_option = str(question_data["correctOption"]).upper()
    correct = selected_option == correct_option

    if correct:
        feedback = "Correct. Good selection based on EASA flight dispatch principles."
    else:
        feedback = f"Incorrect. The correct option is {correct_option}."

    return {
        "correct": correct,
        "feedback": feedback,
        "score": 1.0 if correct else 0.0,
    }


def build_mock_explanation(
    *,
    question: str,
    options: list[str],
    selected_option: str,
    correct_option: str,
    is_correct: bool,
) -> str:
    option_map = {
        "A": options[0] if len(options) > 0 else "",
        "B": options[1] if len(options) > 1 else "",
        "C": options[2] if len(options) > 2 else "",
        "D": options[3] if len(options) > 3 else "",
    }

    correct_text = option_map.get(correct_option, "the EASA-compliant option")
    selected_text = option_map.get(selected_option, "an invalid or unknown option")
    question_context = question.strip().rstrip("?.")

    if is_correct:
        return (
            f"For '{question_context}', your selected answer is correct because it matches the EASA-compliant operational decision. "
            f"The key principle is regulatory adherence and safe dispatch practice, reflected by option {correct_option}: {correct_text}"
        )

    return (
        f"For '{question_context}', your selected answer ({selected_option}: {selected_text}) does not align with EASA dispatch requirements. "
        f"The correct choice is {correct_option}: {correct_text}, because it follows EASA-compliant operational procedure and safety framework."
    )


async def generate_answer_explanation(
    *,
    question: str,
    options: list[str],
    selected_option: str,
    correct_option: str,
    is_correct: bool,
) -> str:
    prompt = f"""
You are an expert EASA Flight Dispatcher instructor.

Question:
{question}

Options:
A. {options[0]}
B. {options[1]}
C. {options[2]}
D. {options[3]}

User selected: {selected_option}
Correct option: {correct_option}
Result: {'correct' if is_correct else 'incorrect'}

Write a brief explanation in exactly 2 sentences focused on EASA context.
Return strict JSON only:
{{
  "explanation": "..."
}}
"""

    parsed = await call_gemini_json(prompt)
    explanation = str(parsed.get("explanation", "")).strip()
    if not explanation:
        raise RuntimeError("Invalid explanation JSON from Gemini.")
    return explanation


@app.post("/api/start")
async def api_start(payload: dict[str, Any]):
    try:
        level = 1
        qn = 1
        correct_count = 0
        topics_pool = ["Aviation Navigation"] * 5 + ["Aviation Meteorology"] * 5
        random.shuffle(topics_pool)
        topic = topics_pool.pop()

        q = await generate_question(level, qn, topic, None)

        state_token = encode_state_token(
            {
                "current_level": level,
                "correct_count": correct_count,
                "question_count": qn,
                "correct_answer_key": q["correctOption"],
                "topics_pool": topics_pool,
            }
        )

        return {
            "questionNumber": qn,
            "level": level,
            "maxQuestions": MAX_QUESTIONS,
            "question": q["question"],
            "topic": q["topic"],
            "options": q["options"],
            "correctOption": q["correctOption"],
            "explanation": q["explanation"],
            "stateToken": state_token,
        }
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.post("/api/generate")
async def api_generate(payload: dict[str, Any]):
    try:
        token = payload.get("stateToken")
        if not isinstance(token, str) or not token.strip():
            raise HTTPException(status_code=400, detail="stateToken is required.")

        state = decode_state_token(token)

        if state["question_count"] >= 10 or not state["topics_pool"]:
            return {
                "status": "complete",
                "final_level": state["current_level"],
                "correct_count": state["correct_count"],
                "message": "Quiz completed."
            }

        level = clamp_level(normalize_int(state.get("current_level"), 1, 1, MAX_LEVEL))
        qn = normalize_int(state.get("question_count"), 1, 1, MAX_QUESTIONS)
        topics_pool = list(state.get("topics_pool", []))
        if not topics_pool:
            raise HTTPException(status_code=400, detail="No topics remaining in topics_pool.")
        topic = str(topics_pool.pop())
        last_result = payload.get("lastResult")
        try:
            q = await generate_question(level, qn, topic, last_result if isinstance(last_result, dict) else None)
        except AIResponseFormatError:
            try:
                q = await generate_question(level, qn, topic, last_result if isinstance(last_result, dict) else None)
            except AIResponseFormatError:
                return JSONResponse(
                    status_code=500,
                    content={"error": "AI failed to generate a valid response. Please try again."}
                )

        state_token = encode_state_token(
            {
                "current_level": level,
                "correct_count": normalize_int(state.get("correct_count"), 0, 0, MAX_QUESTIONS),
                "question_count": qn,
                "correct_answer_key": q["correctOption"],
                "topics_pool": topics_pool,
            }
        )

        return {
            "questionNumber": qn,
            "level": level,
            "maxQuestions": MAX_QUESTIONS,
            "question": q["question"],
            "topic": q["topic"],
            "options": q["options"],
            "correctOption": q["correctOption"],
            "explanation": q["explanation"],
            "stateToken": state_token,
        }
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.post("/api/submit")
async def api_submit(payload: dict[str, Any]):
    try:
        token = payload.get("stateToken")
        if not isinstance(token, str) or not token.strip():
            raise HTTPException(status_code=400, detail="stateToken is required.")

        state = decode_state_token(token)
        answer = payload.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise HTTPException(status_code=400, detail="A non-empty answer is required.")

        current_question = payload.get("currentQuestion")
        if (
            not isinstance(current_question, dict)
            or not current_question.get("question")
            or not isinstance(current_question.get("options"), list)
            or len(current_question.get("options")) != 4
            or str(current_question.get("correctOption", "")).upper() not in {"A", "B", "C", "D"}
        ):
            raise HTTPException(
                status_code=400,
                detail="currentQuestion with question, 4 options, and correctOption is required.",
            )

        level = clamp_level(normalize_int(state.get("current_level"), 1, 1, MAX_LEVEL))
        qn = normalize_int(state.get("question_count"), 1, 1, MAX_QUESTIONS)
        cc = normalize_int(state.get("correct_count"), 0, 0, MAX_QUESTIONS)
        token_correct_key = str(state.get("correct_answer_key", "")).upper()
        topics_pool = list(state.get("topics_pool", []))

        evaluation = evaluate_mcq_answer(
            {
                "question": str(current_question.get("question")),
                "options": [str(opt) for opt in current_question.get("options", [])],
                "correctOption": token_correct_key,
                "explanation": str(current_question.get("explanation", "")),
            },
            answer.strip(),
        )

        selected_option = normalize_selected_option(answer.strip(), [str(opt) for opt in current_question.get("options", [])])
        if USE_MOCK_LLM:
            ai_explanation = build_mock_explanation(
                question=str(current_question.get("question")),
                options=[str(opt) for opt in current_question.get("options", [])],
                selected_option=selected_option or "?",
                correct_option=token_correct_key,
                is_correct=evaluation["correct"],
            )
        else:
            try:
                ai_explanation = await generate_answer_explanation(
                    question=str(current_question.get("question")),
                    options=[str(opt) for opt in current_question.get("options", [])],
                    selected_option=selected_option or "(no valid option)",
                    correct_option=token_correct_key,
                    is_correct=evaluation["correct"],
                )
            except AIResponseFormatError:
                try:
                    ai_explanation = await generate_answer_explanation(
                        question=str(current_question.get("question")),
                        options=[str(opt) for opt in current_question.get("options", [])],
                        selected_option=selected_option or "(no valid option)",
                        correct_option=token_correct_key,
                        is_correct=evaluation["correct"],
                    )
                except AIResponseFormatError:
                    return JSONResponse(
                        status_code=500,
                        content={"error": "AI failed to generate a valid response. Please try again."}
                    )

        updated_correct_count = cc + (1 if evaluation["correct"] else 0)
        updated_level = clamp_level(level + 1 if evaluation["correct"] else level)
        finished = qn >= MAX_QUESTIONS

        if finished:
            accuracy = round((updated_correct_count / MAX_QUESTIONS) * 100, 1)
            return {
                "finished": True,
                "correct": evaluation["correct"],
                "feedback": evaluation["feedback"],
                "explanation": ai_explanation,
                "finalLevel": updated_level,
                "totalCorrect": updated_correct_count,
                "totalQuestions": MAX_QUESTIONS,
                "accuracy": accuracy,
                "summary": f"Final Level: {updated_level}/{MAX_LEVEL}. Accuracy: {accuracy}%.",
                "nextLevel": updated_level,
                "nextQuestionCount": qn,
                "updatedCorrectCount": updated_correct_count,
            }

        progress_token = encode_state_token(
            {
                "current_level": updated_level,
                "correct_count": updated_correct_count,
                "question_count": qn + 1,
                "correct_answer_key": "PENDING",
                "topics_pool": topics_pool,
            }
        )

        return {
            "finished": False,
            "correct": evaluation["correct"],
            "feedback": evaluation["feedback"],
            "explanation": ai_explanation,
            "nextLevel": updated_level,
            "nextQuestionCount": qn + 1,
            "updatedCorrectCount": updated_correct_count,
            "maxQuestions": MAX_QUESTIONS,
            "stateToken": progress_token,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.get("/", response_class=HTMLResponse)
async def index():
    return (BASE_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/quiz")
async def quiz_page():
    return FileResponse(PUBLIC_DIR / "index.html")


@app.get("/records", response_model=list[ParticipantRecordRead])
def get_records(db: Session = Depends(get_db)):
    return db.query(ParticipantRecord).order_by(ParticipantRecord.id.asc()).all()


@app.post("/seed", response_model=list[ParticipantRecordRead])
def seed_records(db: Session = Depends(get_db)):
    sample_payloads = [
        {
            "participant_name": "Aarav Mehta",
            "company": "SkyBridge Aviation",
            "department": "Operations",
            "type_of_training": "Recurrent",
            "training_date": date(2026, 1, 15),
        },
        {
            "participant_name": "Neha Kapoor",
            "company": "Nimbus Air",
            "department": "Dispatch",
            "type_of_training": "Initial",
            "training_date": date(2026, 2, 2),
        },
        {
            "participant_name": "Rohan Verma",
            "company": "AeroLine Services",
            "department": "Safety",
            "type_of_training": "Human Factors",
            "training_date": date(2026, 2, 20),
        },
    ]

    inserted_rows: list[ParticipantRecord] = []
    for payload in sample_payloads:
        validated = ParticipantRecordCreate(**payload)
        record = ParticipantRecord(
            participant_name=validated.participant_name,
            company=validated.company,
            department=validated.department,
            type_of_training=validated.type_of_training,
            training_date=validated.training_date,
        )
        db.add(record)
        inserted_rows.append(record)

    db.commit()
    for row in inserted_rows:
        db.refresh(row)

    return inserted_rows


@app.post("/generate/{record_id}")
def generate_certificate_endpoint(
    record_id: int,
    request: CertificateRequest,
    db: Session = Depends(get_db),
):
    record = db.query(ParticipantRecord).filter(ParticipantRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    if record.type_of_training == "Recurrent" and not request.modules:
        raise HTTPException(status_code=400, detail="Modules are required for Recurrent training")

    pdf_path = generate_certificate(record, request.modules)
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=os.path.basename(pdf_path),
    )


@app.get("/{file_path:path}")
async def static_files(file_path: str, request: Request):
    if request.url.path.startswith("/api"):
        raise HTTPException(status_code=404, detail="Not found")

    full_path = (PUBLIC_DIR / file_path).resolve()
    if not str(full_path).startswith(str(PUBLIC_DIR.resolve())):
        raise HTTPException(status_code=404, detail="Not found")

    if full_path.is_file():
        return FileResponse(full_path)

    raise HTTPException(status_code=404, detail="Not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
