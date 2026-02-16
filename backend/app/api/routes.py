from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config import get_settings
from app.schemas.notes import ExportLinks, ProcessRequest, ProcessResponse
from app.services.exporters import write_docx, write_markdown, write_pdf
from app.services.pipeline import NotesPipeline

router = APIRouter(prefix="/api/v1", tags=["notes"])

# In-memory index for MVP. Replace with DB in production.
EXPORT_INDEX: dict[str, dict[str, Path]] = {}


@router.post("/process", response_model=ProcessResponse)
def process_video(request: ProcessRequest) -> ProcessResponse:
    settings = get_settings()
    export_dir = Path(settings.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    try:
        notes = NotesPipeline().run(
            str(request.youtube_url),
            language=request.language,
            style=request.style,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    note_id = uuid4().hex

    md_path = write_markdown(export_dir, notes)
    docx_path = write_docx(export_dir, notes)
    pdf_path = write_pdf(export_dir, notes)

    EXPORT_INDEX[note_id] = {
        "markdown": md_path,
        "docx": docx_path,
        "pdf": pdf_path,
    }

    return ProcessResponse(
        note_id=note_id,
        source_url=request.youtube_url,
        notes=notes,
        exports=ExportLinks(
            pdf=f"/api/v1/export/pdf/{note_id}",
            docx=f"/api/v1/export/docx/{note_id}",
            markdown=f"/api/v1/export/markdown/{note_id}",
        ),
    )


@router.get("/export/{fmt}/{note_id}")
def download_export(fmt: str, note_id: str):
    file_map = EXPORT_INDEX.get(note_id)
    if not file_map:
        raise HTTPException(status_code=404, detail="Note export not found")

    fmt = fmt.lower()
    if fmt not in file_map:
        raise HTTPException(status_code=404, detail="Format not available")

    file_path = file_map[fmt]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File missing on server")

    media_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "markdown": "text/markdown",
    }

    names = {
        "pdf": "engineering-notes.pdf",
        "docx": "engineering-notes.docx",
        "markdown": "engineering-notes.md",
    }

    return FileResponse(path=file_path, media_type=media_types[fmt], filename=names[fmt])
