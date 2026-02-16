export type CodeLineExplanation = {
  line_number: number;
  explanation: string;
};

export type CodeBlock = {
  language: string;
  code: string;
  explanation: string;
  line_by_line: CodeLineExplanation[];
};

export type TopicNote = {
  topic_name: string;
  explanation: string[];
  screen_content: string[];
  formulas_or_diagrams: string[];
  diagram?: string | null;
  code_sections: CodeBlock[];
};

export type ProcessResponse = {
  note_id: string;
  source_url: string;
  notes: TopicNote[];
  exports: {
    pdf: string;
    docx: string;
    markdown: string;
  };
};

export type OutputLanguage = "english" | "hinglish";
export type NotesStyle = "simple" | "exam";
