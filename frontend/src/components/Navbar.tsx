"use client";

import React from "react";
import { ShieldAlert, Trophy, Key } from "lucide-react";

interface NavbarProps {
  onOpenLeaderboard?: () => void;
  onReset?: () => void;
  onOpenApiKeyModal?: () => void;
  hasCustomKey?: boolean;
}

export default function Navbar({ onOpenLeaderboard, onReset, onOpenApiKeyModal, hasCustomKey }: NavbarProps) {
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
        <div className="flex items-center gap-3 sm:gap-4">
          <div className="hidden sm:flex items-center gap-2 font-mono text-xs text-zinc-400 mr-2">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="tracking-wider">API: ONLINE</span>
          </div>

          {onOpenApiKeyModal && (
            <button
              onClick={onOpenApiKeyModal}
              className={`flex items-center gap-2 border px-3.5 py-1.5 font-mono text-xs uppercase tracking-wider transition-all ${
                hasCustomKey
                  ? "border-cyan-500/70 bg-cyan-950/30 text-cyan-300 hover:border-cyan-400 hover:bg-cyan-900/40"
                  : "border-zinc-700 bg-zinc-900/60 text-zinc-300 hover:border-zinc-500 hover:bg-zinc-800"
              }`}
            >
              <Key className={`h-3.5 w-3.5 ${hasCustomKey ? "text-cyan-400" : "text-zinc-400"}`} />
              <span>{hasCustomKey ? "API KEY: ACTIVE" : "API KEY"}</span>
            </button>
          )}

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
