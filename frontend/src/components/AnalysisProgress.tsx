"use client";

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2 } from "lucide-react";
import { AnalysisStatus } from "@/types";

interface AnalysisProgressProps {
  status: AnalysisStatus;
}

const STAGE_DESCRIPTIONS: Record<string, { label: string; desc: string }> = {
  created: {
    label: "INITIALIZING SESSION",
    desc: "Allocating anonymous alias and analysis pipeline instance...",
  },
  parsing_resume: {
    label: "PARSING RESUME & HYPERLINKS",
    desc: "Scanning PDF text layer and embedded annotation link dictionaries...",
  },
  extracting_links: {
    label: "CATEGORIZING TARGETS",
    desc: "Filtering GitHub profiles, portfolios, and public project endpoints...",
  },
  extracting_claims: {
    label: "EXTRACTING ATOMIC CLAIMS",
    desc: "Decomposing resume statements into falsifiable propositions with sentence traceability...",
  },
  collecting_github: {
    label: "HARVESTING GITHUB RECEIPTS",
    desc: "Collecting repos, languages, commit logs, manifests, and contributor attribution...",
  },
  collecting_web: {
    label: "VERIFYING WEB EVIDENCE",
    desc: "SSRF-safe crawling of public portfolios, documentation, and project sites...",
  },
  normalizing_evidence: {
    label: "NORMALIZING EVIDENCE",
    desc: "Structuring and deduplicating cross-source evidence records...",
  },
  retrieving_evidence: {
    label: "HYBRID RAG RETRIEVAL",
    desc: "Running dense vector cosine search and exact technology keyword boosting...",
  },
  evaluating_claims: {
    label: "EVALUATING CLAIMS",
    desc: "Assessing verdicts (SUPPORTED, PARTIALLY SUPPORTED, UNVERIFIED, CONTRADICTED)...",
  },
  generating_roast: {
    label: "SYNTHESIZING ROAST",
    desc: "Calculating deterministic LARP score and formulating evidence-grounded roast...",
  },
  finalizing: {
    label: "FINALIZING REPORT",
    desc: "Generating anonymous leaderboard record and access token...",
  },
  completed: {
    label: "ANALYSIS COMPLETE",
    desc: "Rendering finalized verification report and roast...",
  },
  failed: {
    label: "PIPELINE HALTED",
    desc: "An unhandled error occurred during pipeline execution.",
  },
};

export default function AnalysisProgress({ status }: AnalysisProgressProps) {
  const currentStage = STAGE_DESCRIPTIONS[status.stage] || {
    label: status.stage.toUpperCase(),
    desc: "Processing evidence...",
  };

  return (
    <motion.div
      id="loading-container-box"
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className="relative w-full max-w-xl mx-auto border-2 border-red-500/90 bg-[#0c0c0e]/95 p-8 container-burning-glow backdrop-blur-md transition-all duration-300 overflow-hidden"
    >
      {/* Top Flame Tongues rising from container rim */}
      <div className="pointer-events-none absolute -top-4 left-4 right-4 h-5 bg-gradient-to-t from-amber-400 via-orange-500 to-transparent filter-flame-tongues opacity-80" />

      {/* Molten Strike Edge on Left where warrior fire streams scorch the container */}
      <div className="pointer-events-none absolute -left-1 top-0 bottom-0 w-2 bg-gradient-to-b from-amber-200 via-orange-400 to-red-600 filter-flame-tongues opacity-95" />
      <div className="pointer-events-none absolute -left-2 top-[22%] w-4 h-16 bg-amber-300/90 blur-[4px] rounded-full" />
      <div className="pointer-events-none absolute -left-2 top-[62%] w-4 h-16 bg-amber-300/90 blur-[4px] rounded-full" />

      {/* Laser Scanline Beam Traveling Down */}
      <div className="pointer-events-none animate-scanline bg-gradient-to-b from-transparent via-red-500/15 to-transparent blur-[1px]" />

      {/* Header Info */}
      <div className="relative z-10 flex items-center justify-between border-b border-zinc-800/80 pb-4 mb-6">
        <div>
          <span className="font-mono text-[10px] tracking-widest text-zinc-500 uppercase">
            TARGET IDENTIFIER
          </span>
          <p className="font-mono text-base font-bold text-zinc-100">
            {status.candidate_alias}
          </p>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs text-red-400">
          <Loader2 className="h-4 w-4 animate-spin text-red-500" />
          <span className="tracking-wider uppercase">ACTIVE SCAN</span>
        </div>
      </div>

      {/* Stage Tracker */}
      <div className="relative z-10 space-y-4">
        <div className="flex items-baseline justify-between">
          <AnimatePresence mode="wait">
            <motion.span
              key={currentStage.label}
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              transition={{ duration: 0.2 }}
              className="font-mono text-xs uppercase tracking-wider text-red-500 font-semibold"
            >
              {currentStage.label}
            </motion.span>
          </AnimatePresence>
          <span className="font-mono text-sm font-bold text-zinc-200">
            {status.progress}%
          </span>
        </div>

        {/* Progress Bar with glowing molten lead edge */}
        <div className="relative h-2 w-full bg-zinc-950 overflow-hidden border border-zinc-800">
          <motion.div
            className="h-full bg-gradient-to-r from-red-800 via-red-500 to-amber-400 relative"
            initial={{ width: 0 }}
            animate={{ width: `${status.progress}%` }}
            transition={{ duration: 0.5, ease: "easeOut" }}
          >
            <div className="absolute right-0 top-0 bottom-0 w-2 bg-amber-200 shadow-[0_0_12px_#ff9900]" />
          </motion.div>
        </div>

        <AnimatePresence mode="wait">
          <motion.p
            key={currentStage.desc}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 6 }}
            transition={{ duration: 0.25 }}
            className="font-mono text-xs text-zinc-400 leading-relaxed min-h-[36px]"
          >
            {currentStage.desc}
          </motion.p>
        </AnimatePresence>
      </div>

      {/* Terminal Details */}
      <div className="mt-8 border-t border-zinc-800/80 pt-4">
        <div className="flex items-center justify-between font-mono text-[10px] text-zinc-600 uppercase tracking-widest">
          <span>TASK ID: {status.analysis_id.slice(0, 8)}...</span>
          <span>ENGINE: RAG + QWEN-32B</span>
        </div>
      </div>
    </motion.div>
  );
}
