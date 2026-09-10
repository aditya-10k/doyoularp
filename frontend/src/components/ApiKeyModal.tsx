"use client";

import React, { useState, useEffect } from "react";
import { Key, X, ShieldCheck, Eye, EyeOff, Sparkles, AlertCircle } from "lucide-react";

interface ApiKeyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onKeySaved?: () => void;
}

export type ProviderType = "groq" | "gemini" | "openrouter" | "openai";

const PROVIDERS: { id: ProviderType; name: string; desc: string; freeTier: string }[] = [
  {
    id: "groq",
    name: "Groq",
    desc: "Ultra-low latency inference (openai/gpt-oss-20b, compound-mini).",
    freeTier: "Free tier available at console.groq.com",
  },
  {
    id: "gemini",
    name: "Google Gemini",
    desc: "1M token context window and high throughput (gemini-2.0-flash).",
    freeTier: "Free tier available at aistudio.google.com",
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    desc: "Access to free open-weights models (llama-3.3-70b-instruct:free).",
    freeTier: "Free tier available at openrouter.ai",
  },
  {
    id: "openai",
    name: "OpenAI",
    desc: "Direct execution via gpt-4o-mini with standard developer account.",
    freeTier: "Developer key at platform.openai.com",
  },
];

export default function ApiKeyModal({ isOpen, onClose, onKeySaved }: ApiKeyModalProps) {
  const [provider, setProvider] = useState<ProviderType>("groq");
  const [apiKey, setApiKey] = useState<string>("");
  const [showKey, setShowKey] = useState<boolean>(false);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);
  const [existingKey, setExistingKey] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const storedKey = localStorage.getItem("doyoularp_user_api_key");
      const storedProvider = localStorage.getItem("doyoularp_user_provider") as ProviderType | null;
      if (storedKey) {
        setApiKey(storedKey);
        setExistingKey(true);
      } else {
        setApiKey("");
        setExistingKey(false);
      }
      if (storedProvider && ["groq", "gemini", "openrouter", "openai"].includes(storedProvider)) {
        setProvider(storedProvider);
      }
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSave = () => {
    if (!apiKey.trim()) return;
    localStorage.setItem("doyoularp_user_api_key", apiKey.trim());
    localStorage.setItem("doyoularp_user_provider", provider);
    localStorage.setItem("doyoularp_api_prompt_seen", "true");
    setSavedSuccess(true);
    setExistingKey(true);
    if (onKeySaved) onKeySaved();
    setTimeout(() => {
      setSavedSuccess(false);
      onClose();
    }, 800);
  };

  const handleRemove = () => {
    localStorage.removeItem("doyoularp_user_api_key");
    localStorage.removeItem("doyoularp_user_provider");
    setApiKey("");
    setExistingKey(false);
    if (onKeySaved) onKeySaved();
  };

  const handleDismiss = () => {
    localStorage.setItem("doyoularp_api_prompt_seen", "true");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg border border-zinc-700 bg-[#0d0d0d] shadow-2xl p-6 font-mono text-zinc-200">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 pb-4 mb-5">
          <div className="flex items-center gap-3">
            <div className="p-2 border border-cyan-500/40 bg-cyan-950/30 text-cyan-400">
              <Key className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold tracking-wider uppercase text-zinc-100">
                Custom AI Provider Key
              </h2>
              <span className="text-[11px] text-zinc-500 uppercase tracking-widest block">
                OPTIONAL - CLIENT LOCAL STORAGE ONLY
              </span>
            </div>
          </div>
          <button
            onClick={handleDismiss}
            className="p-1 text-zinc-400 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Informational Banner */}
        <div className="border border-zinc-800 bg-zinc-900/40 p-3 mb-5 text-xs text-zinc-400 space-y-1.5">
          <div className="flex items-center gap-2 text-cyan-400 font-semibold">
            <ShieldCheck className="h-4 w-4 shrink-0" />
            <span>Privacy and Security Guarantee</span>
          </div>
          <p className="text-[11px] leading-relaxed text-zinc-400">
            Keys are stored strictly inside your browser&apos;s localStorage and sent only in the request header
            for your active session. They are never written to our PostgreSQL database or logged to disk.
          </p>
        </div>

        {/* Provider Selection */}
        <div className="space-y-2 mb-4">
          <label className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
            Select Provider
          </label>
          <div className="grid grid-cols-2 gap-2">
            {PROVIDERS.map((p) => {
              const isSelected = provider === p.id;
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setProvider(p.id)}
                  className={`p-2.5 text-left border text-xs transition-all ${
                    isSelected
                      ? "border-cyan-500 bg-cyan-950/40 text-cyan-200"
                      : "border-zinc-800 bg-zinc-900/40 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
                  }`}
                >
                  <div className="font-bold tracking-wide">{p.name}</div>
                  <div className="text-[10px] text-zinc-500 line-clamp-1 mt-0.5">{p.freeTier}</div>
                </button>
              );
            })}
          </div>
        </div>

        {/* API Key Input */}
        <div className="space-y-2 mb-5">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
              {provider.toUpperCase()} API Key
            </label>
            {existingKey && (
              <span className="text-[10px] text-emerald-400 font-mono tracking-wider">
                [ KEY CONFIGURED ]
              </span>
            )}
          </div>
          <div className="relative">
            <input
              type={showKey ? "text" : "password"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={`Enter your ${provider} API key (e.g. gsk_... or AIzaSy...)`}
              className="w-full border border-zinc-800 bg-black/60 px-3 py-2 pr-10 text-xs font-mono text-zinc-100 placeholder-zinc-600 focus:border-cyan-500 focus:outline-none"
            />
            <button
              type="button"
              onClick={() => setShowKey(!showKey)}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
            >
              {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          <p className="text-[10px] text-zinc-500">
            Leave blank if you prefer to use the free server tier. Server keys automatically fallback across Groq, OpenRouter, and Gemini.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center gap-3 pt-2 border-t border-zinc-800">
          <button
            type="button"
            onClick={handleSave}
            disabled={!apiKey.trim()}
            className="w-full sm:flex-1 py-2.5 border border-cyan-500 bg-cyan-600 text-black font-mono font-bold text-xs uppercase tracking-wider transition-colors hover:bg-cyan-400 disabled:opacity-50 disabled:pointer-events-none"
          >
            {savedSuccess ? "SAVED!" : "SAVE API KEY"}
          </button>

          {existingKey && (
            <button
              type="button"
              onClick={handleRemove}
              className="w-full sm:w-auto px-4 py-2.5 border border-red-800/80 bg-red-950/30 text-red-400 font-mono text-xs uppercase tracking-wider hover:bg-red-900/50 transition-colors"
            >
              REMOVE KEY
            </button>
          )}

          <button
            type="button"
            onClick={handleDismiss}
            className="w-full sm:w-auto px-4 py-2.5 border border-zinc-800 bg-zinc-900 text-zinc-400 font-mono text-xs uppercase tracking-wider hover:bg-zinc-800 hover:text-zinc-200 transition-colors"
          >
            CONTINUE WITH SERVER TIER
          </button>
        </div>
      </div>
    </div>
  );
}
