"use client";

import { LoaderCircle } from "lucide-react";
import { motion } from "framer-motion";

export function ProcessingCard() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-border bg-card p-4 shadow-card"
    >
      <div className="flex items-center gap-3">
        <LoaderCircle className="h-5 w-5 animate-spin text-accent" />
        <div>
          <p className="font-semibold">Processing lecture...</p>
          <p className="text-sm text-foreground/70">
            Extracting speech, screen text, code, and building exam-ready notes.
          </p>
        </div>
      </div>
    </motion.div>
  );
}
