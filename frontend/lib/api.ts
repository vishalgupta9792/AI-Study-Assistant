import { NotesStyle, OutputLanguage, ProcessResponse } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function processVideo(
  youtubeUrl: string,
  language: OutputLanguage,
  style: NotesStyle
): Promise<ProcessResponse> {
  const res = await fetch(`${API_BASE}/api/v1/process`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ youtube_url: youtubeUrl, language, style }),
  });

  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail || "Failed to process video");
  }

  return res.json();
}

export function toAbsoluteExportUrl(path: string): string {
  if (path.startsWith("http")) {
    return path;
  }
  return `${API_BASE}${path}`;
}
