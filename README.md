# Daiwang-Khera--IFOA-assignment

## 1. Project Overview

This repository contains both required tasks:
- Assignment 1: AI-Driven Adaptive Quiz (EASA Flight Dispatcher topics: Navigation and Meteorology)
- Assignment 2: Automated Certificate Generation System (database records + template-based PDF output)

Live Demo URLs:
- Assignment 1: Not deployed (local setup provided below)
- Assignment 2: Not deployed (local setup provided below)

Submission link:
- GitHub repository: https://github.com/daiwangk/Daiwang-Khera--IFOA-assignment

## 2. System Design & Workflow (Required Deliverable)

Architecture:
- I implemented a monolithic FastAPI backend with SQLite to minimize external dependencies and keep local testing frictionless for reviewers.
- A single service exposes API endpoints for quiz flow, record management, and certificate generation.
- SQLite + SQLAlchemy were selected for simple setup, deterministic behavior, and easy portability.

The PDF Engine:
- Instead of generating certificates from scratch (brittle and style-inconsistent), I used the provided template PDFs and mapped exact (X, Y) pixel coordinates.
- I used PyMuPDF (fitz) to overlay dynamic values from database records onto those templates.
- This coordinate-mapping strategy keeps visual fidelity with official templates while supporting automation.

Workflow summary:
- Assignment 1: start quiz -> submit answer -> adaptive level update -> next question generation -> final level outcome.
- Assignment 2: fetch records -> user clicks Generate Certificate -> optional recurrent module selection -> backend fills template -> downloadable PDF returned.

How this addresses evaluation criteria:
- System design: modular, API-driven backend with clear separation of concerns.
- Automation logic: end-to-end record-to-certificate generation and downloadable output.
- User experience: clean dashboard, responsive table, and guided module modal for recurrent training.
- Scalability: coordinate dictionary and endpoint structure support adding new training types/templates without rewriting core logic.

## 3. Use of AI Tools (Required Deliverable)

I used AI tools (GitHub Copilot and LLM assistance) as intelligent autocomplete and boilerplate acceleration.

I explicitly drove the key engineering decisions:
- Monolithic FastAPI + SQLite architecture.
- Dictionary-driven coordinate mapping for each certificate type.
- Validation and business rules, including strict handling of recurrent module requirements (HTTP 400 when modules are missing).
- Endpoint contracts and local verification strategy.

## 4. Local Setup Instructions

Run these commands from the project root:

```bash
python -m venv .venv
```

Windows PowerShell:

```bash
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create env file:

```bash
copy .env.example .env
```

Start server:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 3000
```

Open in browser:
- Assignment 2 dashboard: http://localhost:3000/
- Assignment 1 quiz: http://localhost:3000/quiz

Optional data seed for Assignment 2:

```bash
curl -X POST http://localhost:3000/seed
```

## 5. Prioritizing Truth over Agreement

The prompt allows either a live link or local setup. I intentionally prioritized correctness and reproducibility over claiming a hosted deployment.

So this submission provides:
- A complete GitHub source submission.
- Clear local setup instructions for deterministic reviewer execution.
- Honest scope: no fabricated cloud deployment link, only validated local runtime flow.
