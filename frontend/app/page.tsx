"use client";

import { FormEvent, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Download, Mic } from "lucide-react";

import { ProcessingCard } from "@/components/processing-card";
import { ThemeToggle } from "@/components/theme-toggle";
import { processVideo, toAbsoluteExportUrl } from "@/lib/api";
import { NotesStyle, OutputLanguage, ProcessResponse, TopicNote } from "@/lib/types";

function TopicCard({ topic }: { topic: TopicNote }) {
  const speak = () => {
    const utterance = new SpeechSynthesisUtterance(
      `${topic.topic_name}. ${topic.explanation.join(". ")}. ${topic.screen_content.join(". ")}`
    );
    utterance.rate = 1;
    utterance.pitch = 1;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  };

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-border bg-card p-6 shadow-card"
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <h2 className="text-xl font-bold">{topic.topic_name}</h2>
        <button
          onClick={speak}
          className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm hover:bg-muted"
        >
          <Mic className="h-4 w-4" /> Explain This Topic
        </button>
      </div>

      <div className="space-y-5 text-sm">
        <div>
          <h3 className="mb-2 text-base font-semibold">1. Explanation (What YouTuber Said)</h3>
          <ul className="space-y-1">
            {topic.explanation.map((point) => (
              <li key={point}>- {point}</li>
            ))}
          </ul>
        </div>

        <div>
          <h3 className="mb-2 text-base font-semibold">2. Screen Content</h3>
          <ul className="space-y-1">
            {topic.screen_content.map((point) => (
              <li key={point}>- {point}</li>
            ))}
          </ul>
          {topic.formulas_or_diagrams.length > 0 && (
            <ul className="mt-2 space-y-1 rounded-md border border-border/70 bg-muted p-3">
              {topic.formulas_or_diagrams.map((item) => (
                <li key={item}>- {item}</li>
              ))}
            </ul>
          )}
          {topic.diagram && (
            <div className="mt-3 rounded-md border border-border bg-background p-3">
              <p className="mb-1 text-xs uppercase tracking-wide text-foreground/70">Topic Diagram</p>
              <pre className="overflow-x-auto text-xs text-foreground/90">{topic.diagram}</pre>
            </div>
          )}
        </div>

        <div>
          <h3 className="mb-2 text-base font-semibold">3. Code Section</h3>
          {topic.code_sections.length === 0 && <p>- No code in this topic.</p>}
          <div className="space-y-4">
            {topic.code_sections.map((block, idx) => (
              <div key={`${block.language}-${idx}`} className="rounded-lg border border-border bg-muted p-4">
                <p className="mb-2 text-xs uppercase tracking-wide text-foreground/70">{block.language}</p>
                <pre className="overflow-x-auto rounded-md bg-black/90 p-3 text-xs text-cyan-200">
                  <code>{block.code}</code>
                </pre>
                <p className="mt-2">- {block.explanation}</p>
                <ul className="mt-2 space-y-1">
                  {block.line_by_line.map((line) => (
                    <li key={line.line_number}>- Line {line.line_number}: {line.explanation}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </div>
    </motion.section>
  );
}

export default function HomePage() {
  const [url, setUrl] = useState("");
  const [language, setLanguage] = useState<OutputLanguage>("english");
  const [style, setStyle] = useState<NotesStyle>("simple");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ProcessResponse | null>(null);

  const isValid = useMemo(() => {
    return /^https?:\/\//i.test(url.trim());
  }, [url]);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    setResult(null);

    try {
      const data = await processVideo(url.trim(), language, style);
      setResult(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Processing failed";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-4 py-10 md:px-8">
      <header className="mb-10 flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-foreground/60">AI Study Assistant</p>
          <h1 className="text-3xl font-bold md:text-4xl">Engineering Notes from YouTube</h1>
          <p className="mt-2 max-w-2xl text-sm text-foreground/70">
            Lecture link do, structured exam-ready notes pao: explanation, screen content, code extraction, and voice mode.
          </p>
        </div>
        <ThemeToggle />
      </header>

      <section className="rounded-xl border border-border bg-card p-5 shadow-card">
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="Paste YouTube lecture URL"
            className="h-12 flex-1 rounded-lg border border-border bg-background px-4 outline-none focus:ring-2 focus:ring-accent"
            required
          />
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as OutputLanguage)}
              className="h-12 rounded-lg border border-border bg-background px-4"
            >
              <option value="english">English</option>
              <option value="hinglish">Hinglish</option>
            </select>
            <select
              value={style}
              onChange={(e) => setStyle(e.target.value as NotesStyle)}
              className="h-12 rounded-lg border border-border bg-background px-4"
            >
              <option value="simple">Simple Humanized</option>
              <option value="exam">Exam Focused</option>
            </select>
            <button
              type="submit"
              disabled={!isValid || loading}
              className="h-12 rounded-lg bg-accent px-6 font-semibold text-accent-foreground disabled:opacity-50"
            >
              Generate Notes
            </button>
          </div>
        </form>
      </section>

      <div className="mt-6 space-y-4">
        {loading && <ProcessingCard />}
        {error && <p className="rounded-lg border border-red-400/40 bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}
      </div>

      {result && (
        <section className="mt-8 space-y-5">
          <div className="rounded-lg border border-border bg-card p-3 text-sm">
            Source Video:{" "}
            <a href={result.source_url} target="_blank" rel="noreferrer" className="underline">
              {result.source_url}
            </a>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <a
              href={toAbsoluteExportUrl(result.exports.pdf)}
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm hover:bg-muted"
            >
              <Download className="h-4 w-4" /> Download PDF
            </a>
            <a
              href={toAbsoluteExportUrl(result.exports.docx)}
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm hover:bg-muted"
            >
              <Download className="h-4 w-4" /> Download DOCX
            </a>
            <a
              href={toAbsoluteExportUrl(result.exports.markdown)}
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-2 text-sm hover:bg-muted"
            >
              <Download className="h-4 w-4" /> Download Markdown
            </a>
          </div>

          {result.notes.map((topic, idx) => (
            <TopicCard key={`${topic.topic_name}-${idx}`} topic={topic} />
          ))}
        </section>
      )}
    </main>
  );
}
