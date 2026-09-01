"use client";

import React from "react";
import { ShieldAlert, Trophy } from "lucide-react";

interface NavbarProps {
  onOpenLeaderboard?: () => void;
  onReset?: () => void;
}

export default function Navbar({ onOpenLeaderboard, onReset }: NavbarProps) {
  return (
    <header className="w-full border-b border-zinc-800/80 bg-[#080808]/80 backdrop-blur-md px-6 py-4">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand / Logo */}
        <button
          onClick={onReset}
          className="flex items-center gap-3 text-left focus:outline-none group"
        >
          <div className="flex h-8 w-8 items-center justify-center border border-red-600 bg-red-950/40 text-red-500 font-mono font-bold text-sm transition-colors group-hover:bg-red-600 group-hover:text-white">
            DL
          </div>
          <div>
            <span className="font-mono text-sm font-bold tracking-wider text-zinc-100 group-hover:text-white transition-colors">
              doyoularp
            </span>
            <span className="block font-mono text-[10px] text-zinc-500 tracking-widest uppercase">
              EVIDENCE VERIFICATION ENGINE
            </span>
          </div>
        </button>

        {/* Status and Action Controls */}
        <div className="flex items-center gap-6">
          <div className="hidden sm:flex items-center gap-2 font-mono text-xs text-zinc-400">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="tracking-wider">API: ONLINE</span>
          </div>

          {onOpenLeaderboard && (
            <button
              onClick={onOpenLeaderboard}
              className="flex items-center gap-2 border border-zinc-700 bg-zinc-900/60 px-3.5 py-1.5 font-mono text-xs uppercase tracking-wider text-zinc-200 transition-all hover:border-red-600 hover:bg-zinc-800"
            >
              <Trophy className="h-3.5 w-3.5 text-zinc-400" />
              <span>LEADERBOARD</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
