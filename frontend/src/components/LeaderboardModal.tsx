"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { X, Trophy, AlertCircle, Loader2 } from "lucide-react";
import { LeaderboardEntryItem, LeaderboardResponse } from "@/types";
import { getLeaderboard } from "@/lib/api";

interface LeaderboardModalProps {
  analysisId?: string | null;
  onClose: () => void;
}

const PAGE_SIZE = 50;

export default function LeaderboardModal({ analysisId, onClose }: LeaderboardModalProps) {
  const [entries, setEntries] = useState<LeaderboardEntryItem[]>([]);
  const [userEntry, setUserEntry] = useState<LeaderboardEntryItem | null>(null);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [offset, setOffset] = useState<number>(0);
  const [hasMore, setHasMore] = useState<boolean>(true);
  const [loadingInitial, setLoadingInitial] = useState<boolean>(true);
  const [loadingMore, setLoadingMore] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const fetchPage = useCallback(
    async (pageOffset: number, isInitial = false) => {
      if (isInitial) {
        setLoadingInitial(true);
        setError(null);
      } else {
        setLoadingMore(true);
      }

      try {
        const targetId = analysisId || "global";
        const res: LeaderboardResponse = await getLeaderboard(targetId, PAGE_SIZE, pageOffset);

        if (isInitial) {
          setEntries(res.leaderboard);
          setUserEntry(res.user_entry || null);
        } else {
          setEntries((prev) => {
            const existingRanks = new Set(prev.map((e) => e.rank));
            const freshItems = res.leaderboard.filter((e) => !existingRanks.has(e.rank));
            return [...prev, ...freshItems];
          });
        }

        setTotalCount(res.total);
        const newOffset = pageOffset + res.leaderboard.length;
        setOffset(newOffset);
        const moreAvailable =
          res.has_more !== undefined ? res.has_more : newOffset < res.total;
        setHasMore(moreAvailable && res.leaderboard.length > 0);
      } catch (err: any) {
        setError(err.message || "Failed to load leaderboard.");
      } finally {
        if (isInitial) setLoadingInitial(false);
        setLoadingMore(false);
      }
    },
    [analysisId]
  );

  // Initial load
  useEffect(() => {
    setEntries([]);
    setOffset(0);
    setHasMore(true);
    fetchPage(0, true);
  }, [fetchPage]);

  // Scroll listener for infinite scroll
  const handleScroll = () => {
    const container = scrollContainerRef.current;
    if (!container || loadingInitial || loadingMore || !hasMore) return;

    const { scrollTop, scrollHeight, clientHeight } = container;
    if (scrollTop + clientHeight >= scrollHeight - 100) {
      fetchPage(offset, false);
    }
  };

  // IntersectionObserver on sentinel element at bottom of table
  useEffect(() => {
    if (!sentinelRef.current) return;

    const observer = new IntersectionObserver(
      (observerEntries) => {
        if (observerEntries[0].isIntersecting && hasMore && !loadingMore && !loadingInitial) {
          fetchPage(offset, false);
        }
      },
      { threshold: 0.1 }
    );

    const target = sentinelRef.current;
    observer.observe(target);
    return () => observer.unobserve(target);
  }, [offset, hasMore, loadingMore, loadingInitial, fetchPage]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm">
      <div className="relative w-full max-w-2xl border border-zinc-800 bg-[#0a0a0c] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 p-5">
          <div className="flex items-center gap-2.5">
            <Trophy className="h-4 w-4 text-red-500" />
            <div>
              <h3 className="font-mono text-sm font-bold uppercase tracking-wider text-zinc-100">
                LEADERBOARD // TOP RESUME HYPERS
              </h3>
              <span className="font-mono text-[10px] text-zinc-500 uppercase tracking-widest block">
                {totalCount > 0
                  ? `SHOWING ${entries.length} OF ${totalCount} VERIFIED CANDIDATES`
                  : "LIVE ANONYMIZED REPUTATION METRICS"}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-200 transition-colors p-1"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content Body with Infinite Scroll */}
        <div
          ref={scrollContainerRef}
          onScroll={handleScroll}
          className="max-h-[60vh] overflow-y-auto p-5 font-mono text-xs"
        >
          {loadingInitial ? (
            <div className="py-12 text-center text-zinc-500 uppercase tracking-widest flex flex-col items-center gap-3">
              <Loader2 className="h-5 w-5 animate-spin text-red-500" />
              <span>QUERYING LEADERBOARD ENTRIES...</span>
            </div>
          ) : error && entries.length === 0 ? (
            <div className="flex items-center gap-2 border border-red-900/40 bg-red-950/20 p-4 text-red-400">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          ) : entries.length === 0 ? (
            <div className="py-12 text-center text-zinc-500 uppercase tracking-widest">
              NO LEADERBOARD ENTRIES RECORDED YET.
            </div>
          ) : (
            <div className="space-y-4">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-zinc-800 text-zinc-500 text-[10px] uppercase tracking-wider">
                    <th className="pb-2.5 w-12">RANK</th>
                    <th className="pb-2.5">CANDIDATE ALIAS</th>
                    <th className="pb-2.5 text-right w-24">LARP SCORE</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900">
                  {entries.map((entry) => {
                    const isCurrent = userEntry?.anonymous_alias === entry.anonymous_alias;
                    return (
                      <tr
                        key={entry.rank}
                        className={`transition-colors ${
                          isCurrent
                            ? "bg-red-950/40 font-bold text-red-200 border-l-2 border-red-500"
                            : "hover:bg-zinc-900/40 text-zinc-300"
                        }`}
                      >
                        <td className="py-3 text-zinc-500">#{entry.rank}</td>
                        <td className="py-3">
                          <div className="font-semibold flex items-center gap-2">
                            <span>{entry.anonymous_alias}</span>
                            {isCurrent && (
                              <span className="font-mono text-[9px] px-1.5 py-0.5 border border-red-600 bg-red-950/80 text-red-400 uppercase">
                                YOUR SCAN
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-zinc-500 italic truncate max-w-sm mt-0.5">
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

              {/* Bottom Sentinel for IntersectionObserver */}
              <div ref={sentinelRef} className="h-2 w-full" />

              {/* Loading More Indicator */}
              {loadingMore && (
                <div className="py-3 text-center border-t border-zinc-800/80 flex items-center justify-center gap-2 text-zinc-400 text-[11px]">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-red-500" />
                  <span className="uppercase tracking-wider">
                    LOADING MORE CANDIDATES (RANK #{offset + 1}+)...
                  </span>
                </div>
              )}

              {/* End of List indicator */}
              {!hasMore && entries.length > 0 && (
                <div className="py-3 text-center border-t border-zinc-800/80 text-zinc-600 text-[10px] uppercase tracking-widest">
                  [ ALL {totalCount} CANDIDATES LOADED // END OF LEADERBOARD ]
                </div>
              )}

              {/* Error loading more */}
              {error && entries.length > 0 && (
                <div className="py-3 text-center border-t border-red-900/50 flex items-center justify-center gap-3 text-red-400 text-[11px]">
                  <span>{error}</span>
                  <button
                    onClick={() => fetchPage(offset, false)}
                    className="border border-red-800 bg-red-950/50 px-2 py-1 uppercase hover:bg-red-900 text-white"
                  >
                    RETRY
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Note */}
        <div className="border-t border-zinc-800 p-4 text-center flex items-center justify-between">
          <span className="font-mono text-[10px] text-zinc-600 uppercase tracking-widest">
            ANONYMIZED REPUTATION METRICS &bull; NO PII EXPOSED
          </span>
          <span className="font-mono text-[10px] text-zinc-500 uppercase">
            PAGE SIZE: {PAGE_SIZE}
          </span>
        </div>
      </div>
    </div>
  );
}
