# AI Engineer Notes Assistant

AI-powered web app for engineering students that converts YouTube lectures into structured study notes.

## Stack
- Frontend: Next.js (TypeScript), Tailwind CSS, Framer Motion, shadcn-style components
- Backend: FastAPI (Python)
- Video pipeline: FFmpeg, Whisper, Tesseract OCR, LLM-ready hooks
- Export: PDF, DOCX, Markdown
- Voice mode: Browser speech synthesis (`Explain This Topic`)

## Monorepo Layout
- `frontend/` Next.js app
- `backend/` FastAPI API + AI pipeline skeleton
- `docs/` Architecture and roadmap

## Quick Start

### 1) Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2) Frontend
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Environment
Copy `.env.example` values into:
- `backend/.env`
- `frontend/.env.local`

## Current MVP Coverage
- YouTube URL input
- Processing indicator
- Topic-wise structured notes format
- Separate sections for spoken explanation, screen content, and code
- Syntax-highlighted code blocks in UI
- Export buttons for PDF/DOCX/Markdown
- Dark/Light mode
- Voice explanation per topic

## For Better Accuracy (Recommended)
- Install `ffmpeg`, `yt-dlp`, and `tesseract` on your system PATH.
- If `OPENAI_API_KEY` is provided in `backend/.env`, notes are rewritten in cleaner teacher-style language.
- Without these tools, app still works using transcript-first extraction.

## Notes About AI Pipeline
Current implementation is transcript-first and link-specific:
- Reads YouTube captions using `youtube-transcript-api`
- Builds topic windows from timestamped transcript
- Optionally extracts on-screen text/code via OCR (`yt-dlp + ffmpeg + tesseract`)
- Optionally rewrites explanations in teacher style using OpenAI (if key is set)

To make it fully AI-powered in production:
1. Add Whisper/ASR fallback when transcript is unavailable.
2. Improve OCR with frame quality filters and layout-aware parsing.
3. Use an LLM for stronger topic segmentation and better code reconstruction.
4. Add job queue and retries for long videos.
5. Persist jobs/notes in PostgreSQL.

## Future Enhancements
- Async job queue (Celery/RQ + Redis)
- Auth + user history
- Stripe billing
- Exam mode, quiz mode, concept map mode
- Docker + Kubernetes deployment
