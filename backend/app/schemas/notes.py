from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ProcessRequest(BaseModel):
    youtube_url: HttpUrl
    language: Literal["english", "hinglish"] = "english"
    style: Literal["simple", "exam"] = "simple"


class CodeLineExplanation(BaseModel):
    line_number: int
    explanation: str


class CodeBlock(BaseModel):
    language: str
    code: str
    explanation: str
    line_by_line: list[CodeLineExplanation] = Field(default_factory=list)


class TopicNote(BaseModel):
    topic_name: str
    explanation: list[str]
    screen_content: list[str]
    formulas_or_diagrams: list[str]
    diagram: str | None = None
    code_sections: list[CodeBlock] = Field(default_factory=list)


class ExportLinks(BaseModel):
    pdf: str
    docx: str
    markdown: str


class ProcessResponse(BaseModel):
    note_id: str
    source_url: HttpUrl
    notes: list[TopicNote]
    exports: ExportLinks


class ErrorResponse(BaseModel):
    detail: str
