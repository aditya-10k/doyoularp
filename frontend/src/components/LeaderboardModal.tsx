"use client";

import React, { useEffect, useState } from "react";
import { X, Trophy, AlertCircle } from "lucide-react";
import { LeaderboardResponse } from "@/types";
import { getLeaderboard } from "@/lib/api";

interface LeaderboardModalProps {
  analysisId?: string | null;
  onClose: () => void;
}

export default function LeaderboardModal({ analysisId, onClose }: LeaderboardModalProps) {
  const [data, setData] = useState<LeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchLeaderboard() {
      try {
        setLoading(true);
        setError(null);
        // If analysisId is provided, fetch via that completed result
        const targetId = analysisId || "global";
        const result = await getLeaderboard(targetId);
        setData(result);
      } catch (err: any) {
        setError(err.message || "Failed to load leaderboard.");
      } finally {
        setLoading(false);
      }
    }
    fetchLeaderboard();
  }, [analysisId]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
      <div className="relative w-full max-w-2xl border border-zinc-800 bg-[#0c0c0e] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 p-5">
          <div className="flex items-center gap-2.5">
            <Trophy className="h-4 w-4 text-red-500" />
            <h3 className="font-mono text-sm font-bold uppercase tracking-wider text-zinc-100">
              LEADERBOARD // TOP RESUME HYPERS
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-200 transition-colors p-1"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="max-h-[60vh] overflow-y-auto p-5 font-mono text-xs">
          {loading ? (
            <div className="py-12 text-center text-zinc-500 uppercase tracking-widest">
              QUERYING LEADERBOARD ENTRIES...
            </div>
          ) : error ? (
            <div className="flex items-center gap-2 border border-red-900/40 bg-red-950/20 p-4 text-red-400">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          ) : !data || data.leaderboard.length === 0 ? (
            <div className="py-12 text-center text-zinc-500 uppercase tracking-widest">
              NO LEADERBOARD ENTRIES RECORDED YET.
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500 text-[10px] uppercase tracking-wider">
                  <th className="pb-2.5 w-12">RANK</th>
                  <th className="pb-2.5">CANDIDATE ALIAS</th>
                  <th className="pb-2.5 text-right w-24">LARP SCORE</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900">
                {data.leaderboard.map((entry) => {
                  const isCurrent = data.user_entry?.anonymous_alias === entry.anonymous_alias;
                  return (
                    <tr
                      key={entry.rank}
                      className={`transition-colors ${
                        isCurrent
                          ? "bg-red-950/30 font-bold text-red-300"
                          : "hover:bg-zinc-900/40 text-zinc-300"
                      }`}
                    >
                      <td className="py-3 text-zinc-500">#{entry.rank}</td>
                      <td className="py-3">
                        <div className="font-semibold">{entry.anonymous_alias}</div>
                        <div className="text-[11px] text-zinc-500 italic truncate max-w-sm">
                          &ldquo;{entry.roast}&rdquo;
                        </div>
                      </td>
                      <td className="py-3 text-right text-red-500 font-bold">
                        {entry.larp_score.toFixed(1)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer Note */}
        <div className="border-t border-zinc-800 p-4 text-center">
          <span className="font-mono text-[10px] text-zinc-600 uppercase tracking-widest">
            ANONYMIZED REPUTATION METRICS &bull; NO PII EXPOSED
          </span>
        </div>
      </div>
    </div>
  );
}
