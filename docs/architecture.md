# System Architecture

## Flow
1. Student submits a YouTube URL.
2. Backend pipeline creates transcript + OCR payload + detected code blocks.
3. Structuring layer converts raw data into exam-ready topic notes.
4. Export layer generates PDF/DOCX/Markdown files.
5. Frontend renders notes and supports voice explanation mode.

## Core Backend Modules
- `pipeline.py`: orchestrates transcript + OCR + code extraction.
- `notes_engine.py` (integrated in pipeline): topic segmentation and compact summarization.
- `exporters.py`: PDF/DOCX/Markdown generation.
- `routes.py`: API endpoints for process and exports.

## APIs
- `POST /api/v1/process`
- `GET /api/v1/export/{format}/{note_id}`

## Production Upgrade Path
- Replace in-memory storage with PostgreSQL.
- Add task queue for long videos.
- Add real Whisper + OCR + LLM integrations.
- Add monitoring + retry policies.
