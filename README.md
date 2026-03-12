# Daiwang-Khera--IFOA-assignment

AI/Automation/Data Systems technical assignment submission.

## Assignment 1 - AI-Driven Adaptive Quiz (EASA Flight Dispatcher)

This project is a local web app that uses the Gemini API to:
- Generate MCQ quiz questions dynamically (no pre-made question bank)
- Adapt level progression over 10 levels
- Evaluate answers immediately after each submission
- Provide feedback and final level after 10 questions

## Tech Stack
- FastAPI (Python backend)
- Vanilla HTML/CSS/JS (frontend)
- Gemini API (configured via `GEMINI_MODELS`, with `gemini-2.5-pro` supported)

## Setup
1. Install Python 3.10+.
2. In project folder, install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create `.env` from `.env.example`:
   ```bash
   copy .env.example .env
   ```
4. Open `.env` and set your key:
   ```env
   GEMINI_API_KEY=PASTE_YOUR_KEY_HERE
   GEMINI_MODELS=gemini-2.5-pro,gemini-2.5-flash,gemini-2.0-flash
   QUIZ_JWT_SECRET=PASTE_A_LONG_RANDOM_SECRET
   PORT=3000
   ```
5. Start server:
   ```bash
   uvicorn main:app --reload --port 3000
   ```
6. Open `http://localhost:3000`.

## How Adaptation Works
- Quiz runs for exactly 10 questions.
- Current level starts at 1.
- If answer is correct: level increases by 1 (up to level 10).
- If answer is incorrect: level remains the same.
- Final level after question 10 is shown as user competency outcome.
- Topic coverage is guaranteed per run with 5 Navigation and 5 Meteorology questions shuffled across the session.

## System Design & Logic
- Backend is stateless. It does not store per-user progress in server memory.
- Backend signs quiz state in a JWT (`stateToken`) with `current_level`, `correct_count`, `question_count`, and `correct_answer_key`.
- Frontend (`public/app.js`) stores and sends this `stateToken` on submit/generate calls.
- Backend decodes JWT and performs deterministic correctness checks server-side, preventing score tampering.
- `POST /api/start` generates the first question from incoming `currentLevel` and `questionCount`.
- `POST /api/submit` evaluates the user answer using the incoming current question and state, then returns the next computed level and counters.
- `POST /api/generate` generates the next question from the updated state sent by the frontend.
- Adaptive leveling rule: The user starts at Level 1. A correct answer increases the level by 1 (max 10). An incorrect answer keeps the user at the current level. The final level out of 10 reflects total correct answers, naturally capping the difficulty based on mistakes.
- Question format is MCQ: each question includes 4 options (A-D) with exactly one correct answer.

## API Endpoints
- `POST /api/start` -> generates question 1 from frontend-provided `currentLevel` and `questionCount`
- `POST /api/submit` -> evaluates answer from frontend-provided question/state and returns updated level/counters
- `POST /api/generate` -> generates the next question from updated frontend state

## UI Behavior Note
- After each answer, feedback is shown.
- The user advances manually with a Next Question button after reading the feedback.
- When the next question is loaded, the previous feedback panel is automatically hidden so incorrect feedback does not persist into the next question.

## Deliverable Notes
- Working demo: run locally as above.
- Source code: all files in this folder.
- Questions are generated at runtime via Gemini and are not hardcoded.
- For local development without live Gemini calls, set `USE_MOCK_LLM=true`.
