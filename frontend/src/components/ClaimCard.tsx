"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronUp, ExternalLink, ShieldCheck, HelpCircle, AlertTriangle, XCircle } from "lucide-react";
import { Claim, VerdictType } from "@/types";

interface ClaimCardProps {
  claim: Claim;
}

const VERDICT_CONFIG: Record<
  VerdictType,
  {
    label: string;
    border: string;
    bg: string;
    text: string;
    description: string;
  }
> = {
  SUPPORTED: {
    label: "SUPPORTED",
    border: "border-emerald-600/70",
    bg: "bg-emerald-950/30",
    text: "text-emerald-400",
    description: "Strong public evidence confirms this claim.",
  },
  PARTIALLY_SUPPORTED: {
    label: "PARTIALLY SUPPORTED",
    border: "border-amber-600/70",
    bg: "bg-amber-950/30",
    text: "text-amber-400",
    description: "Related artifacts found, but key metrics or scale remain unverified.",
  },
  UNVERIFIED: {
    label: "UNVERIFIED",
    border: "border-zinc-700",
    bg: "bg-zinc-900/40",
    text: "text-zinc-400",
    description: "Insufficient public evidence found. Missing evidence does not imply fraud.",
  },
  CONTRADICTED: {
    label: "CONTRADICTED",
    border: "border-red-600/80",
    bg: "bg-red-950/40",
    text: "text-red-400",
    description: "Public records and commit logs directly conflict with this statement.",
  },
};

export default function ClaimCard({ claim }: ClaimCardProps) {
  const [expanded, setExpanded] = useState(false);
  const evaluation = claim.evaluation;
  const verdict: VerdictType = evaluation?.verdict || "UNVERIFIED";
  const config = VERDICT_CONFIG[verdict];

  return (
    <div className={`border transition-all ${config.border} bg-[#0d0d0f]/90`}>
      {/* Main Header Row */}
      <div
        onClick={() => setExpanded(!expanded)}
        className="cursor-pointer p-4 sm:p-5 flex items-start justify-between gap-4 select-none hover:bg-zinc-900/40"
      >
        <div className="space-y-2 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {/* Verdict Badge */}
            <span
              className={`inline-flex items-center px-2 py-0.5 border font-mono text-[11px] font-semibold tracking-wider ${config.border} ${config.bg} ${config.text}`}
            >
              {config.label}
            </span>

            {/* Category Tag */}
            <span className="font-mono text-[10px] uppercase tracking-widest text-zinc-500 border border-zinc-800 px-2 py-0.5">
              {claim.category}
            </span>

            {evaluation?.confidence && (
              <span className="font-mono text-[10px] text-zinc-500">
                CONFIDENCE: {(evaluation.confidence * 100).toFixed(0)}%
              </span>
            )}
          </div>

          {/* Atomic Claim Text */}
          <h4 className="font-mono text-sm font-semibold text-zinc-100 leading-snug">
            {claim.claim_text}
          </h4>

          {/* Resume Source Quote */}
          <div className="border-l-2 border-zinc-800 pl-3 py-0.5">
            <span className="font-mono text-[10px] uppercase tracking-widest text-zinc-600 block">
              ORIGINAL RESUME STATEMENT
            </span>
            <p className="font-mono text-xs italic text-zinc-400">
              &ldquo;{claim.source_text}&rdquo;
            </p>
          </div>
        </div>

        {/* Expand / Collapse Icon */}
        <button
          type="button"
          className="text-zinc-500 hover:text-zinc-300 p-1 shrink-0"
        >
          {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>

      {/* Expanded Reasoning & Evidence Details */}
      {expanded && (
        <div className="border-t border-zinc-800/80 bg-black/40 p-4 sm:p-5 space-y-3 font-mono text-xs">
          <div>
            <span className="text-[10px] uppercase tracking-widest text-zinc-500 block mb-1">
              EVALUATION REASONING
            </span>
            <p className="text-zinc-300 leading-relaxed">
              {evaluation?.reasoning || config.description}
            </p>
          </div>

          {evaluation?.evidence_ids && evaluation.evidence_ids.length > 0 && (
            <div className="pt-2">
              <span className="text-[10px] uppercase tracking-widest text-zinc-500 block mb-1">
                REFERENCED EVIDENCE ARTIFACTS
              </span>
              <div className="flex flex-wrap gap-1.5">
                {evaluation.evidence_ids.map((id) => (
                  <span
                    key={id}
                    className="inline-flex items-center gap-1 border border-zinc-800 bg-zinc-950 px-2 py-0.5 text-[10px] text-zinc-400 font-mono"
                  >
                    <span>ID: {id.slice(0, 8)}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
