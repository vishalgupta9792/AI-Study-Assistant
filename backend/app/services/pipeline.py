from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from app.core.config import get_settings
from app.schemas.notes import CodeBlock, CodeLineExplanation, TopicNote

try:
    import pytesseract
except Exception:  # pragma: no cover - optional dependency at runtime
    pytesseract = None  # type: ignore[assignment]

LanguageMode = Literal["english", "hinglish"]
StyleMode = Literal["simple", "exam"]

STOP_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "to",
    "of",
    "in",
    "for",
    "is",
    "are",
    "this",
    "that",
    "we",
    "you",
    "it",
    "with",
    "on",
    "as",
    "be",
    "by",
    "from",
    "at",
}


@dataclass
class TranscriptEntry:
    text: str
    start: float
    duration: float


@dataclass
class OcrEntry:
    text: str
    second: int


@dataclass
class RawPipelineOutput:
    transcript_entries: list[TranscriptEntry]
    ocr_entries: list[OcrEntry]
    code_snippets: list[str]


class NotesPipeline:
    def run(
        self,
        youtube_url: str,
        language: LanguageMode = "english",
        style: StyleMode = "simple",
    ) -> list[TopicNote]:
        raw = self._collect_raw_data(youtube_url)
        return self._structure_notes(raw, language=language, style=style)

    def _collect_raw_data(self, youtube_url: str) -> RawPipelineOutput:
        video_id = self._extract_video_id(youtube_url)
        transcript_error: str | None = None
        transcript_entries: list[TranscriptEntry] = []
        try:
            transcript_entries = self._fetch_transcript_entries(video_id)
        except ValueError as exc:
            transcript_error = str(exc)

        ocr_entries = self._extract_ocr_entries(youtube_url)
        if not transcript_entries and not ocr_entries:
            detail = transcript_error or "No useful transcript text found for this video."
            raise ValueError(
                f"{detail} Also no OCR text could be extracted. "
                "Try another video, or install ffmpeg + tesseract for better fallback extraction."
            )

        code_snippets = self._extract_code_candidates(transcript_entries, ocr_entries)
        return RawPipelineOutput(
            transcript_entries=transcript_entries,
            ocr_entries=ocr_entries,
            code_snippets=code_snippets,
        )

    def _extract_video_id(self, youtube_url: str) -> str:
        parsed = urlparse(youtube_url)
        host = parsed.netloc.lower()
        path = parsed.path.strip("/")

        if "youtu.be" in host and path:
            return path.split("/")[0]

        if "youtube.com" in host:
            if path == "watch":
                video_id = parse_qs(parsed.query).get("v", [""])[0]
                if video_id:
                    return video_id
            if path.startswith("shorts/"):
                return path.split("/")[1]
            if path.startswith("embed/"):
                return path.split("/")[1]

        raise ValueError("Could not parse a valid YouTube video ID from the provided URL.")

    def _fetch_transcript_entries(self, video_id: str) -> list[TranscriptEntry]:
        preferred_languages = ["en", "en-US", "hi", "en-GB"]
        entries: list[TranscriptEntry] = []

        try:
            snippets = YouTubeTranscriptApi().fetch(video_id, languages=preferred_languages)
            for item in snippets:
                text = self._clean_text(getattr(item, "text", ""))
                if len(text.split()) < 3:
                    continue
                entries.append(
                    TranscriptEntry(
                        text=text,
                        start=float(getattr(item, "start", 0.0)),
                        duration=float(getattr(item, "duration", 0.0)),
                    )
                )
        except AttributeError:
            # Backward compatibility for older versions.
            data = YouTubeTranscriptApi.get_transcript(video_id, languages=preferred_languages)  # type: ignore[attr-defined]
            for item in data:
                text = self._clean_text(item.get("text", ""))
                if len(text.split()) < 3:
                    continue
                entries.append(
                    TranscriptEntry(
                        text=text,
                        start=float(item.get("start", 0.0)),
                        duration=float(item.get("duration", 0.0)),
                    )
                )
        except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as exc:
            raise ValueError(
                "Transcript unavailable for this video. Try a video with captions enabled."
            ) from exc
        except Exception as exc:
            raise ValueError("Unable to read transcript from YouTube right now. Try again.") from exc

        return self._dedupe_transcript(entries)

    def _extract_ocr_entries(self, youtube_url: str) -> list[OcrEntry]:
        if not shutil.which("yt-dlp") or not shutil.which("ffmpeg"):
            return []
        if pytesseract is None:
            return []

        tesseract_cmd = shutil.which("tesseract")
        if not tesseract_cmd:
            return []

        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        ocr_entries: list[OcrEntry] = []

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            video_file = tmp_dir / "video.mp4"
            frames_dir = tmp_dir / "frames"
            frames_dir.mkdir(parents=True, exist_ok=True)

            download = subprocess.run(
                ["yt-dlp", "-f", "mp4", "-o", str(video_file), youtube_url],
                capture_output=True,
                text=True,
                check=False,
            )
            if download.returncode != 0 or not video_file.exists():
                return []

            frame_pattern = frames_dir / "frame_%03d.jpg"
            extract = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(video_file),
                    "-vf",
                    "fps=1/6",
                    "-frames:v",
                    "24",
                    str(frame_pattern),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if extract.returncode != 0:
                return []

            for idx, frame in enumerate(sorted(frames_dir.glob("frame_*.jpg")), start=0):
                try:
                    raw_text = pytesseract.image_to_string(str(frame), config="--oem 3 --psm 6")
                except Exception:
                    continue

                for line in self._normalize_ocr_lines(raw_text):
                    if len(line.split()) < 2:
                        continue
                    ocr_entries.append(OcrEntry(text=line, second=idx * 6))

        return self._dedupe_ocr(ocr_entries)

    def _extract_code_candidates(
        self,
        transcript_entries: list[TranscriptEntry],
        ocr_entries: list[OcrEntry],
    ) -> list[str]:
        code_like = re.compile(
            r"(^\s*#include|^\s*import |int\s+main|return\s+\d+;|for\s*\(|while\s*\(|if\s*\(|console\.log|def\s+|"
            r"\b(?:int|float|double|char|long|short|bool|string)\b\s+[a-zA-Z_]\w*\s*=.*;|^\s*[{}]\s*$)",
            re.IGNORECASE,
        )
        pool: list[str] = []

        for entry in transcript_entries:
            if code_like.search(entry.text):
                pool.append(entry.text)
        for entry in ocr_entries:
            if code_like.search(entry.text):
                pool.append(entry.text)

        cleaned = self._unique_lines(pool)[:20]
        if not cleaned:
            return []

        grouped: list[str] = []
        current: list[str] = []
        for line in cleaned:
            current.append(line)
            if len(current) >= 8:
                grouped.append("\n".join(current))
                current = []
        if current:
            grouped.append("\n".join(current))
        return grouped[:2]

    def _structure_notes(
        self,
        raw: RawPipelineOutput,
        language: LanguageMode,
        style: StyleMode,
    ) -> list[TopicNote]:
        base_entries = raw.transcript_entries
        if not base_entries and raw.ocr_entries:
            base_entries = [
                TranscriptEntry(text=item.text, start=float(item.second), duration=6.0)
                for item in raw.ocr_entries
            ]

        windows = self._topic_windows(base_entries, max_topics=5, window_seconds=90)
        topics: list[TopicNote] = []

        for index, (start, end, chunk) in enumerate(windows, start=1):
            chunk_lines = [x.text for x in chunk]
            ocr_lines = [x.text for x in raw.ocr_entries if start <= x.second <= end]

            explanation = self._to_points(chunk_lines, max_points=6, language=language, style=style)
            explanation = self._llm_rewrite_points(explanation, language=language, style=style)

            screen_content = self._unique_lines(ocr_lines)[:6]
            if not screen_content:
                screen_content = [self._format_text("No clear board/screen text was detected in this segment.", language, style)]

            formulas = self._extract_formula_like_lines(chunk_lines + ocr_lines)
            diagram = self._build_topic_diagram(chunk_lines, language)

            topic_code = []
            if index == 1 and raw.code_snippets:
                topic_code = raw.code_snippets
            if any(self._looks_code(line) for line in ocr_lines):
                topic_code = topic_code + ["\n".join([x for x in ocr_lines if self._looks_code(x)])]

            topics.append(
                TopicNote(
                    topic_name=self._topic_title(chunk_lines, index, language),
                    explanation=explanation,
                    screen_content=[self._format_text(x, language, style) for x in screen_content],
                    formulas_or_diagrams=[self._format_text(x, language, style) for x in formulas],
                    diagram=diagram,
                    code_sections=self._build_code_blocks(topic_code, language, style),
                )
            )

        return topics

    def _topic_windows(
        self,
        entries: list[TranscriptEntry],
        max_topics: int,
        window_seconds: int,
    ) -> list[tuple[int, int, list[TranscriptEntry]]]:
        if not entries:
            return []

        grouped: list[tuple[int, int, list[TranscriptEntry]]] = []
        cursor = int(entries[0].start)
        last = int(entries[-1].start + entries[-1].duration)
        while cursor <= last and len(grouped) < max_topics:
            start = cursor
            end = start + window_seconds
            chunk = [x for x in entries if start <= int(x.start) < end]
            if chunk:
                grouped.append((start, end, chunk))
            cursor = end

        if not grouped:
            grouped.append((0, window_seconds, entries[:40]))
        return grouped

    def _topic_title(self, lines: list[str], index: int, language: LanguageMode) -> str:
        words: list[str] = []
        for line in lines:
            words.extend(re.findall(r"[a-zA-Z]{4,}", line.lower()))
        freq: dict[str, int] = {}
        for w in words:
            if w in STOP_WORDS:
                continue
            freq[w] = freq.get(w, 0) + 1

        top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:2]
        labels = [x[0].capitalize() for x in top] or [f"Section {index}"]
        base = " & ".join(labels)
        if language == "hinglish":
            return f"Topic {index}: {base} Concept"
        return f"Topic {index}: {base}"

    def _to_points(
        self,
        lines: list[str],
        max_points: int,
        language: LanguageMode,
        style: StyleMode,
    ) -> list[str]:
        points: list[str] = []
        for line in lines:
            candidate = self._simplify_sentence(line)
            if len(candidate.split()) < 5:
                continue
            formatted = self._format_text(candidate, language, style)
            if formatted not in points:
                points.append(formatted)
            if len(points) >= max_points:
                break
        return points

    def _llm_rewrite_points(
        self,
        points: list[str],
        language: LanguageMode,
        style: StyleMode,
    ) -> list[str]:
        if not points:
            return points

        api_key = get_settings().openai_api_key
        if not api_key:
            return points

        try:
            from openai import OpenAI
        except Exception:
            return points

        guidance = "Explain in simple student-friendly English."
        if language == "hinglish":
            guidance = "Explain in natural Hinglish (easy Hindi + English mix), simple classroom style."
        if style == "exam":
            guidance += " Keep it exam-oriented and concise."

        client = OpenAI(api_key=api_key)
        prompt = (
            f"{guidance}\n"
            "Rewrite the following bullets without changing meaning. "
            "Return exactly one bullet per line, no numbering:\n"
            + "\n".join(points)
        )
        try:
            response = client.responses.create(
                model="gpt-4o-mini",
                input=prompt,
                temperature=0.3,
            )
            text = getattr(response, "output_text", "") or ""
            rewritten = [self._clean_text(x) for x in text.splitlines() if self._clean_text(x)]
            return rewritten[: len(points)] if rewritten else points
        except Exception:
            return points

    def _build_topic_diagram(self, lines: list[str], language: LanguageMode) -> str:
        steps = self._extract_process_steps(lines)
        if not steps:
            if language == "hinglish":
                return "Flow: Input -> Process -> Output"
            return "Flow: Input -> Process -> Output"
        chain = " -> ".join(step.capitalize() for step in steps[:5])
        return f"Flow: {chain}"

    def _extract_process_steps(self, lines: list[str]) -> list[str]:
        verbs = ["select", "define", "calculate", "solve", "check", "apply", "write", "run", "print"]
        found: list[str] = []
        text = " ".join(lines).lower()
        for v in verbs:
            if re.search(rf"\b{v}\b", text) and v not in found:
                found.append(v)
        return found

    def _extract_formula_like_lines(self, lines: Iterable[str]) -> list[str]:
        formulas: list[str] = []
        pattern = re.compile(
            r"(=|plus|minus|integral|derivative|matrix|voltage|current|force|energy|sum|sigma|kcl|kvl)",
            re.IGNORECASE,
        )
        for line in lines:
            if pattern.search(line):
                cleaned = self._clean_text(line)
                if cleaned and cleaned not in formulas:
                    formulas.append(cleaned)
        return formulas[:6]

    def _build_code_blocks(
        self,
        snippets: list[str],
        language: LanguageMode,
        style: StyleMode,
    ) -> list[CodeBlock]:
        blocks: list[CodeBlock] = []
        for snippet in snippets:
            cleaned = self._clean_code(snippet)
            if len(cleaned.splitlines()) < 1:
                continue
            lang = self._guess_language(cleaned)
            blocks.append(
                CodeBlock(
                    language=lang,
                    code=cleaned,
                    explanation=self._format_text(
                        "This code is extracted from the lecture screen/transcript and cleaned for readability.",
                        language,
                        style,
                    ),
                    line_by_line=self._line_explanations(cleaned, language, style),
                )
            )
        return blocks[:3]

    def _line_explanations(self, code: str, language: LanguageMode, style: StyleMode) -> list[CodeLineExplanation]:
        out: list[CodeLineExplanation] = []
        for i, line in enumerate(code.splitlines(), start=1):
            x = line.strip()
            if not x:
                continue

            if x.startswith("#include"):
                text = "Includes header file for input/output functions."
            elif re.search(r"\bint\s+main\s*\(", x):
                text = "Program execution starts here."
            elif x == "{":
                text = "Start of the main code block."
            elif x == "}":
                text = "End of the main code block."
            elif x.startswith("//"):
                text = "Comment line explaining the logic."
            elif "for" in x and "(" in x:
                text = "Loop runs a block multiple times."
            elif "return" in x:
                text = "Returns status and ends the function."
            elif "=" in x:
                text = "Assigns or computes a value."
            else:
                text = "Core statement in this code."

            out.append(
                CodeLineExplanation(
                    line_number=i,
                    explanation=self._format_text(text, language, style),
                )
            )
        return out

    def _looks_code(self, text: str) -> bool:
        return bool(
            re.search(
                r"(^\s*#include|;\s*$|int\s+main|for\s*\(|while\s*\(|if\s*\(|return\s+\d+;|def\s+|console\.log|"
                r"\b(?:int|float|double|char|long|short|bool|string)\b\s+[a-zA-Z_]\w*\s*=.*;|^\s*[{}]\s*$)",
                text,
                flags=re.IGNORECASE,
            )
        )

    def _guess_language(self, code: str) -> str:
        lower = code.lower()
        if "#include" in lower or "int main" in lower:
            return "c"
        if "import " in lower or "def " in lower:
            return "python"
        if "console.log" in lower or "function " in lower:
            return "javascript"
        if "public static void main" in lower:
            return "java"
        return "text"

    def _simplify_sentence(self, text: str) -> str:
        text = self._clean_text(text)
        replacements = {
            "therefore": "so",
            "hence": "so",
            "approximately": "about",
            "utilize": "use",
            "demonstrates": "shows",
            "fundamentally": "mainly",
        }
        out = text.lower()
        for old, new in replacements.items():
            out = out.replace(old, new)
        return out[:1].upper() + out[1:] if out else out

    def _format_text(self, text: str, language: LanguageMode, style: StyleMode) -> str:
        if style == "exam":
            text = f"Exam focus: {text}"
        if language == "hinglish":
            return self._to_hinglish(text)
        return text

    def _to_hinglish(self, text: str) -> str:
        replacements = {
            r"\bthis\b": "ye",
            r"\bis\b": "hai",
            r"\bare\b": "hain",
            r"\bshows\b": "show karta hai",
            r"\bbecause\b": "kyunki",
            r"\band\b": "aur",
            r"\bwith\b": "ke saath",
            r"\bfor\b": "ke liye",
            r"\buse\b": "use karo",
        }
        out = text
        for pattern, value in replacements.items():
            out = re.sub(pattern, value, out, flags=re.IGNORECASE)
        return out

    def _clean_code(self, code: str) -> str:
        lines = [self._clean_text(line) for line in code.splitlines()]
        lines = [line for line in lines if line]
        return "\n".join(lines)

    def _normalize_ocr_lines(self, text: str) -> list[str]:
        # Preserve line boundaries so code lines like `double x = 5.0;` are not merged away.
        lines = text.splitlines()
        out: list[str] = []
        for line in lines:
            cleaned = self._clean_text(line)
            if cleaned:
                out.append(cleaned)
        return self._unique_lines(out)

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\[.*?\]", " ", text)
        text = text.replace("\n", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _unique_lines(self, lines: Iterable[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for line in lines:
            cleaned = self._clean_text(line)
            key = cleaned.lower()
            if not cleaned or key in seen:
                continue
            seen.add(key)
            out.append(cleaned)
        return out

    def _dedupe_transcript(self, entries: list[TranscriptEntry]) -> list[TranscriptEntry]:
        out: list[TranscriptEntry] = []
        seen: set[str] = set()
        for entry in entries:
            key = entry.text.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(entry)
        return out

    def _dedupe_ocr(self, entries: list[OcrEntry]) -> list[OcrEntry]:
        out: list[OcrEntry] = []
        seen: set[str] = set()
        for entry in entries:
            key = entry.text.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(entry)
        return out
