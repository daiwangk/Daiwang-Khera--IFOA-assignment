   # Daiwang-Khera--IFOA-assignment

   This repository contains both required tasks from the Technical Assignment - AI / Automation / Data Systems.

   - Assignment 1: AI-Driven Adaptive Quiz System (EASA Flight Dispatcher)
   - Assignment 2: Automated Certificate Generation System

   Live demo URLs:
   - Not deployed to cloud (local setup provided below, as allowed by the prompt)

   Repository:
   - https://github.com/daiwangk/Daiwang-Khera--IFOA-assignment

   ## 1. Project Overview

   ### Assignment 1 - AI Adaptive Quiz
   An AI-powered quiz platform focused on EASA Flight Dispatcher concepts in:
   - Aviation Navigation
   - Aviation Meteorology

   Key behaviors:
   - 10-question session
   - Adaptive levels (1 to 10)
   - Immediate answer evaluation
   - Correct/incorrect feedback with explanation
   - Final level based on performance

   ### Assignment 2 - Automated Certificate Generator
   A certificate generation dashboard backed by SQLite records.

   Key behaviors:
   - Record table view with required fields
   - Generate Certificate action per record
   - Training-type-based template selection
   - Dynamic PDF field stamping (participant, company, department, dates)
   - Recurrent training modal for module selection and module printing

   ## 2. System Design & Workflow (Required Deliverable)

   ### Architecture
   I implemented a monolithic FastAPI backend with SQLite to minimize external dependencies and make local reviewer setup frictionless.

   Why this design:
   - Single-process service is simple to run and verify
   - SQLite avoids external database setup
   - API-first structure keeps frontend and backend responsibilities separated

   ### Assignment 1 Workflow
   1. `POST /api/start` initializes quiz state and generates question 1.
   2. `POST /api/submit` evaluates answer immediately and updates level progression.
   3. `POST /api/generate` generates the next question with updated difficulty context.
   4. After question 10, final level and result summary are returned.

   ### Assignment 2 Workflow
   1. `GET /records` returns all participant records.
   2. Dashboard renders table and action buttons.
   3. Clicking Generate Certificate calls `POST /generate/{record_id}`.
   4. For `Recurrent` training, modules are required and validated.
   5. Backend generates a PDF and streams it as a downloadable file.

   ### The PDF Engine Strategy
   Instead of generating certificate layouts from scratch (brittle and hard to keep aligned), I mapped exact `(x, y)` coordinates for the provided certificate templates and used PyMuPDF to overlay dynamic values.

   Benefits:
   - Preserves official template appearance
   - Reduces layout drift risk
   - Scales by adding new template mappings rather than rewriting rendering logic

   ## 3. Use of AI Tools (Required Deliverable)

   I used AI tools (GitHub Copilot / LLM assistance) as coding support for:
   - boilerplate generation
   - faster refactoring
   - validation of edge-case handling

   I made and enforced the core technical decisions:
   - monolithic FastAPI + SQLite architecture
   - dictionary-driven certificate coordinate mapping
   - strict validation rules (for example, HTTP 400 when recurrent modules are missing)
   - endpoint contracts and local verification workflow

   ## 4. Local Setup Instructions

   ### Prerequisites
   - Python 3.10+
   - Windows PowerShell (or any shell with equivalent commands)

   ### Install and run
   ```bash
   python -m venv .venv
   ```

   ```bash
   .\.venv\Scripts\Activate.ps1
   ```

   ```bash
   pip install -r requirements.txt
   ```

   ```bash
   copy .env.example .env
   ```

   Edit `.env` and provide your Gemini key if testing live AI generation.

   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 3000
   ```

   ### Open in browser
   - Assignment 2 dashboard: `http://localhost:3000/`
   - Assignment 1 quiz: `http://localhost:3000/quiz`

   ### Optional seed command (Assignment 2)
   ```bash
   curl -X POST http://localhost:3000/seed
   ```

   ## 5. Deliverables Checklist

   - Working application (local demo): Yes
   - Source code: Yes
   - Sample certificate templates: Yes (`templates/`)
   - Generated PDF examples: Yes (`generated_certs/`)
   - System design and workflow explanation: Yes

