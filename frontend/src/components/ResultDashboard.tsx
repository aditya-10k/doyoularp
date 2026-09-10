"use client";

import React, { useState } from "react";
import { motion } from "framer-motion";
import { Copy, Check, Trophy, RotateCcw, ExternalLink, Shield } from "lucide-react";
import { ResultResponse, VerdictType } from "@/types";
import ClaimCard from "./ClaimCard";

interface ResultDashboardProps {
  result: ResultResponse;
  onOpenLeaderboard: () => void;
  onReset: () => void;
}

export default function ResultDashboard({
  result,
  onOpenLeaderboard,
  onReset,
}: ResultDashboardProps) {
  const [copied, setCopied] = useState(false);
  const [activeFilter, setActiveFilter] = useState<string>("ALL");

  const handleCopyRoast = () => {
    navigator.clipboard.writeText(result.roast);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getScoreClassification = (score: number) => {
    if (score >= 80) return { label: "CRITICAL DELUSION // OLYMPIC BUZZWORD GYMNAST", color: "text-red-500", border: "border-red-600" };
    if (score >= 50) return { label: "MODERATE FICTION // MISSING EVIDENCE", color: "text-amber-500", border: "border-amber-600" };
    if (score >= 25) return { label: "PARTIALLY SUBSTANTIATED // MODEST EXAGGERATION", color: "text-zinc-400", border: "border-zinc-700" };
    return { label: "LEGITIMATE // RECEIPTS CHECK OUT", color: "text-emerald-500", border: "border-emerald-600" };
  };

  const scoreClass = getScoreClassification(result.larp_score);

  const filteredClaims = result.claims_breakdown.filter((c) => {
    if (activeFilter === "ALL") return true;
    return c.evaluation?.verdict === activeFilter;
  });

  const defaultDerogatory = [
    "Go and make TikToks, pray you get diversity hired, or just hope your interviewer is as dumb as you.",
    "Submitting a software resume without GitHub is like applying to be an airline pilot by showing a picture of a bird.",
    "You spent more time selecting fonts on this PDF than writing actual code. Cancel the interviews and go become an influencer.",
    "If your code is operating in stealth mode, your job search should be operating in stealth mode as well.",
    "What was the master strategy? Hope the interviewer doesn't know what a version control system is?",
  ];

  const derogatoryList = result.derogatory_versions?.length ? result.derogatory_versions : defaultDerogatory;
  const [activeQuoteIdx, setActiveQuoteIdx] = useState<number>(0);

  const hasGithub = result.sources?.some((s) => s.type === "github");

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8 }}
      className="w-full max-w-4xl mx-auto space-y-8 pb-16"
    >
      {/* Target Identity & Score Overview */}
      <div className="border border-zinc-800 bg-[#0a0a0c]/90 p-6 sm:p-8 backdrop-blur-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-zinc-800/80">
          <div>
            <span className="font-mono text-[10px] tracking-widest text-zinc-500 uppercase block">
              EVALUATED CANDIDATE ALIAS
            </span>
            <h2 className="font-mono text-xl sm:text-2xl font-bold text-zinc-100 uppercase tracking-wide mt-1">
              {result.anonymous_alias}
            </h2>
            <span className={`inline-block mt-2 font-mono text-xs font-semibold uppercase tracking-wider ${scoreClass.color}`}>
              {scoreClass.label}
            </span>
          </div>

          {/* LARP Score Metric */}
          <div className="flex items-center gap-4 border border-zinc-800 bg-black/60 px-6 py-4">
            <div>
              <span className="font-mono text-[10px] uppercase tracking-widest text-zinc-500 block">
                LARP SCORE
              </span>
              <div className="flex items-baseline gap-1">
                <span className="font-mono text-4xl sm:text-5xl font-black text-red-500">
                  {result.larp_score.toFixed(1)}
                </span>
                <span className="font-mono text-xs text-zinc-600">/100</span>
              </div>
            </div>
          </div>
        </div>

        {/* Missing GitHub Savage Reality Check Banner */}
        {!hasGithub && (
          <div className="border-2 border-red-600 bg-red-950/40 p-5 space-y-4 mt-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-red-900/50 pb-3">
              <span className="font-mono text-xs font-black uppercase tracking-widest text-red-500">
                [ CRITICAL OFFENSE // ZERO GITHUB PROVENANCE ]
              </span>
              <button
                type="button"
                onClick={() => setActiveQuoteIdx((prev) => (prev + 1) % derogatoryList.length)}
                className="font-mono text-[10px] uppercase tracking-wider text-red-400 border border-red-800/80 px-2.5 py-1 bg-black/60 hover:border-red-500 hover:text-white transition-all w-fit"
              >
                REROLL VERDICT ({activeQuoteIdx + 1}/{derogatoryList.length})
              </button>
            </div>
            <p className="font-mono text-base sm:text-lg font-bold text-red-200 leading-relaxed italic">
              &ldquo;{derogatoryList[activeQuoteIdx]}&rdquo;
            </p>
            <div className="border-t border-red-900/40 pt-3 space-y-2">
              <span className="font-mono text-[10px] text-zinc-400 uppercase tracking-widest block">
                DEROGATORY REALITY CHECKS (SELECT TO VIEW):
              </span>
              <ul className="space-y-1.5">
                {derogatoryList.map((quote, idx) => (
                  <li
                    key={idx}
                    onClick={() => setActiveQuoteIdx(idx)}
                    className={`cursor-pointer font-mono text-xs transition-colors p-1.5 rounded border ${
                      idx === activeQuoteIdx
                        ? "border-red-700 bg-red-950/60 text-red-200 font-bold"
                        : "border-transparent text-zinc-500 hover:text-zinc-300 hover:bg-black/30"
                    }`}
                  >
                    &bull; {quote}
                  </li>
                ))}
              </ul>
            </div>
            <p className="font-mono text-xs text-zinc-400 pt-1">
              Candidate submitted an engineering resume without linking a GitHub profile or repository receipts. Pipeline aborted immediately with maximum LARP verdict.
            </p>
          </div>
        )}

        {/* The Brutal Roast Block */}
        <div className="pt-6 space-y-6">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs uppercase tracking-widest text-red-500 font-bold">
              [ OFFICIAL VERDICT ROAST ]
            </span>
            <button
              onClick={handleCopyRoast}
              className="flex items-center gap-1.5 font-mono text-xs text-zinc-400 hover:text-zinc-100 transition-colors"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
              <span>{copied ? "COPIED" : "COPY ROAST"}</span>
            </button>
          </div>

          {/* Multi-paragraph savage roast */}
          <div className="border-l-4 border-red-600 bg-red-950/20 p-6 font-serif text-base sm:text-lg italic text-zinc-100 leading-relaxed whitespace-pre-line shadow-[inset_0_0_20px_rgba(220,38,38,0.1)]">
            {result.roast}
          </div>

          {/* Forensic Verdict Summary */}
          <div className="border border-zinc-800/90 bg-black/50 p-5 space-y-2">
            <span className="font-mono text-[10px] uppercase tracking-widest text-zinc-500 font-bold block">
              FORENSIC VERDICT SUMMARY & REALITY AUTOPSY
            </span>
            <p className="font-mono text-xs text-zinc-300 leading-relaxed whitespace-pre-line">
              {result.verdict_summary}
            </p>
          </div>

          {/* Fatal Reality Mismatch & Egregious Fiction Callouts */}
          {(result.funny_mismatch || result.weakest_claim) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {result.funny_mismatch && (
                <div className="border border-red-900/60 bg-red-950/30 p-4">
                  <span className="font-mono text-[10px] uppercase tracking-widest text-red-400 font-bold block mb-1.5">
                    FATAL REALITY MISMATCH
                  </span>
                  <p className="font-mono text-xs text-zinc-300 leading-relaxed italic">
                    &ldquo;{result.funny_mismatch}&rdquo;
                  </p>
                </div>
              )}
              {result.weakest_claim && (
                <div className="border border-zinc-800 bg-zinc-950/60 p-4">
                  <span className="font-mono text-[10px] uppercase tracking-widest text-amber-500 font-bold block mb-1.5">
                    MOST FICTIONAL CLAIM
                  </span>
                  <p className="font-mono text-xs text-zinc-400 leading-relaxed">
                    {result.weakest_claim}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Discovered Sources */}
      {result.sources.length > 0 && (
        <div className="border border-zinc-800 bg-[#0a0a0c]/80 p-5">
          <span className="font-mono text-xs uppercase tracking-widest text-zinc-500 block mb-3">
            VERIFIED EVIDENCE SOURCES ({result.sources.length})
          </span>
          <div className="flex flex-wrap gap-2">
            {result.sources.map((s, idx) => (
              <a
                key={idx}
                href={s.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 border border-zinc-800 bg-zinc-950 px-3 py-1.5 font-mono text-xs text-zinc-300 hover:border-zinc-600 hover:text-white transition-colors"
              >
                <span className="uppercase text-[10px] text-red-400 font-semibold">{s.type}:</span>
                <span className="truncate max-w-[200px]">{s.url.replace(/^https?:\/\//, "")}</span>
                <ExternalLink className="h-3 w-3 text-zinc-500 shrink-0" />
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Claim Breakdown Header & Filters */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="font-mono text-base font-bold uppercase tracking-wider text-zinc-100">
              CLAIM BREAKDOWN ({result.claims_count})
            </h3>
            <span className="font-mono text-xs text-zinc-500">
              EVIDENCE-GROUNDED VERDICT ANALYSIS
            </span>
          </div>

          {/* Filter Tabs */}
          <div className="flex flex-wrap items-center gap-1.5 font-mono text-xs">
            {["ALL", "SUPPORTED", "PARTIALLY_SUPPORTED", "UNVERIFIED", "CONTRADICTED"].map((f) => (
              <button
                key={f}
                onClick={() => setActiveFilter(f)}
                className={`px-2.5 py-1 border transition-colors ${
                  activeFilter === f
                    ? "border-red-600 bg-red-950/40 text-red-400 font-semibold"
                    : "border-zinc-800 bg-zinc-950/60 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
                }`}
              >
                {f.replace("_", " ")}
              </button>
            ))}
          </div>
        </div>

        {/* Claim Cards List */}
        <div className="space-y-3">
          {filteredClaims.length > 0 ? (
            filteredClaims.map((claim) => (
              <ClaimCard key={claim.id} claim={claim} />
            ))
          ) : (
            <div className="border border-zinc-800 p-8 text-center font-mono text-xs text-zinc-500">
              No claims match filter &apos;{activeFilter}&apos;.
            </div>
          )}
        </div>
      </div>

      {/* Bottom Action Controls */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-6 border-t border-zinc-800">
        <button
          onClick={onReset}
          className="w-full sm:w-auto flex items-center justify-center gap-2 border border-zinc-800 bg-zinc-950/60 px-6 py-3 font-mono text-xs uppercase tracking-wider text-zinc-300 hover:border-zinc-600 hover:text-white transition-colors"
        >
          <RotateCcw className="h-4 w-4" />
          <span>SCAN ANOTHER RESUME</span>
        </button>

        <button
          onClick={onOpenLeaderboard}
          className="w-full sm:w-auto flex items-center justify-center gap-2 border border-red-600 bg-red-600 px-6 py-3 font-mono text-xs uppercase tracking-wider text-white hover:bg-red-700 transition-colors"
        >
          <Trophy className="h-4 w-4" />
          <span>VIEW ANONYMOUS LEADERBOARD</span>
        </button>
      </div>
    </motion.div>
  );
}
