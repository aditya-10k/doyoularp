"use client";

import React, { useState, useEffect } from "react";
import { Key, X, ShieldCheck, Eye, EyeOff, Plus, Trash2, Check } from "lucide-react";

interface ApiKeyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onKeySaved?: () => void;
}

export type ProviderType = "groq" | "gemini" | "openrouter" | "openai";

export interface StoredApiKey {
  id: string;
  provider: ProviderType;
  key: string;
  createdAt: number;
}

const PROVIDERS: { id: ProviderType; name: string; desc: string; freeTier: string; placeholder: string }[] = [
  {
    id: "groq",
    name: "Groq",
    desc: "Ultra-low latency inference (openai/gpt-oss-20b, compound-mini).",
    freeTier: "Free tier at console.groq.com",
    placeholder: "gsk_...",
  },
  {
    id: "gemini",
    name: "Google Gemini",
    desc: "1M token context window and high throughput (gemini-2.0-flash).",
    freeTier: "Free tier at aistudio.google.com",
    placeholder: "AIzaSy...",
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    desc: "Access to free open-weights models (llama-3.3-70b-instruct:free).",
    freeTier: "Free tier at openrouter.ai",
    placeholder: "sk-or-...",
  },
  {
    id: "openai",
    name: "OpenAI",
    desc: "Direct execution via gpt-4o-mini with standard developer account.",
    freeTier: "Developer key at platform.openai.com",
    placeholder: "sk-proj-...",
  },
];

export default function ApiKeyModal({ isOpen, onClose, onKeySaved }: ApiKeyModalProps) {
  const [keysList, setKeysList] = useState<StoredApiKey[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<ProviderType>("groq");
  const [inputKey, setInputKey] = useState<string>("");
  const [showKey, setShowKey] = useState<boolean>(false);
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const storedKeysRaw = localStorage.getItem("doyoularp_user_keys");
      if (storedKeysRaw) {
        try {
          const parsed = JSON.parse(storedKeysRaw);
          if (Array.isArray(parsed)) {
            setKeysList(parsed);
          }
        } catch {
          setKeysList([]);
        }
      } else {
        // Check for legacy single-key format
        const legacyKey = localStorage.getItem("doyoularp_user_api_key");
        const legacyProvider = localStorage.getItem("doyoularp_user_provider") as ProviderType | null;
        if (legacyKey && legacyKey.trim()) {
          const migrated: StoredApiKey = {
            id: `legacy-${Date.now()}`,
            provider: legacyProvider || "groq",
            key: legacyKey.trim(),
            createdAt: Date.now(),
          };
          setKeysList([migrated]);
        } else {
          setKeysList([]);
        }
      }
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleAddKey = () => {
    const trimmed = inputKey.trim();
    if (!trimmed) return;

    const rawKeys = trimmed.split(/[\n,]+/).map((k) => k.trim()).filter(Boolean);
    const newItems: StoredApiKey[] = rawKeys.map((k) => ({
      id: `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
      provider: selectedProvider,
      key: k,
      createdAt: Date.now(),
    }));

    const updated = [...keysList, ...newItems];
    setKeysList(updated);
    setInputKey("");
  };

  const handleRemoveKey = (id: string) => {
    const updated = keysList.filter((k) => k.id !== id);
    setKeysList(updated);
    if (typeof window !== "undefined") {
      if (updated.length > 0) {
        localStorage.setItem("doyoularp_user_keys", JSON.stringify(updated));
        localStorage.setItem("doyoularp_user_api_key", updated[0].key);
        localStorage.setItem("doyoularp_user_provider", updated[0].provider);
      } else {
        localStorage.removeItem("doyoularp_user_keys");
        localStorage.removeItem("doyoularp_user_api_key");
        localStorage.removeItem("doyoularp_user_provider");
      }
    }
    if (onKeySaved) onKeySaved();
  };

  const handleClearAll = () => {
    setKeysList([]);
    setInputKey("");
    if (typeof window !== "undefined") {
      localStorage.removeItem("doyoularp_user_keys");
      localStorage.removeItem("doyoularp_user_api_key");
      localStorage.removeItem("doyoularp_user_provider");
    }
    if (onKeySaved) onKeySaved();
  };

  const handleSave = () => {
    let finalKeys = [...keysList];
    const trimmed = inputKey.trim();
    if (trimmed) {
      const rawKeys = trimmed.split(/[\n,]+/).map((k) => k.trim()).filter(Boolean);
      const newItems: StoredApiKey[] = rawKeys.map((k) => ({
        id: `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
        provider: selectedProvider,
        key: k,
        createdAt: Date.now(),
      }));
      finalKeys = [...finalKeys, ...newItems];
      setKeysList(finalKeys);
      setInputKey("");
    }

    if (typeof window !== "undefined") {
      if (finalKeys.length > 0) {
        localStorage.setItem("doyoularp_user_keys", JSON.stringify(finalKeys));
        localStorage.setItem("doyoularp_user_api_key", finalKeys[0].key);
        localStorage.setItem("doyoularp_user_provider", finalKeys[0].provider);
      } else {
        localStorage.removeItem("doyoularp_user_keys");
        localStorage.removeItem("doyoularp_user_api_key");
        localStorage.removeItem("doyoularp_user_provider");
      }
      localStorage.setItem("doyoularp_api_prompt_seen", "true");
    }

    setSavedSuccess(true);
    if (onKeySaved) onKeySaved();
    setTimeout(() => {
      setSavedSuccess(false);
      onClose();
    }, 800);
  };

  const handleDismiss = () => {
    if (typeof window !== "undefined") {
      localStorage.setItem("doyoularp_api_prompt_seen", "true");
    }
    onClose();
  };

  const maskKey = (key: string) => {
    if (key.length <= 8) return "••••••••";
    return `${key.slice(0, 4)}••••••••${key.slice(-4)}`;
  };

  const getProviderKeyCount = (provId: ProviderType) => {
    return keysList.filter((k) => k.provider === provId).length;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg border border-zinc-800 bg-[#0a0a0c] shadow-2xl p-6 font-mono text-zinc-200">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 pb-4 mb-5">
          <div className="flex items-center gap-3">
            <div className="p-2 border border-red-600/40 bg-red-950/30 text-red-500">
              <Key className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold tracking-wider uppercase text-zinc-100">
                Custom AI Provider Keys
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
        <div className="border border-zinc-800/90 bg-zinc-900/40 p-3 mb-4 text-xs text-zinc-400 space-y-1.5">
          <div className="flex items-center gap-2 text-red-400 font-semibold">
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
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
              Select Provider
            </label>
            <span className="text-[10px] text-zinc-500 font-mono">
              CASCADES ACROSS ALL KEYS
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {PROVIDERS.map((p) => {
              const isSelected = selectedProvider === p.id;
              const count = getProviderKeyCount(p.id);
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setSelectedProvider(p.id)}
                  className={`p-2.5 text-left border text-xs transition-all ${
                    isSelected
                      ? "border-red-600 bg-red-950/40 text-red-200"
                      : "border-zinc-800 bg-zinc-900/40 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="font-bold tracking-wide">{p.name}</div>
                    {count > 0 && (
                      <span className="font-mono text-[9px] px-1.5 py-0.5 border border-red-700 bg-red-950/80 text-red-300 uppercase">
                        {count} {count === 1 ? "KEY" : "KEYS"}
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] text-zinc-500 line-clamp-1 mt-0.5">{p.freeTier}</div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Add Provider Key Input */}
        <div className="space-y-2 mb-4">
          <label className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
            Add {selectedProvider.toUpperCase()} API Key
          </label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <input
                type={showKey ? "text" : "password"}
                value={inputKey}
                onChange={(e) => setInputKey(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddKey();
                  }
                }}
                placeholder={`Enter ${selectedProvider} key (${PROVIDERS.find((p) => p.id === selectedProvider)?.placeholder || "..."})`}
                className="w-full border border-zinc-800 bg-black/60 px-3 py-2 pr-10 text-xs font-mono text-zinc-100 placeholder-zinc-600 focus:border-red-600 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
              >
                {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <button
              type="button"
              onClick={handleAddKey}
              disabled={!inputKey.trim()}
              className="px-3.5 py-2 border border-red-600/80 bg-red-950/40 hover:bg-red-900/60 text-red-200 font-mono text-xs uppercase tracking-wider disabled:opacity-40 disabled:pointer-events-none transition-colors flex items-center gap-1.5"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>ADD</span>
            </button>
          </div>
          <p className="text-[10px] text-zinc-500">
            You can add multiple keys. The analysis pipeline cascades across all configured keys before using server fallbacks.
          </p>
        </div>

        {/* Configured Keys List */}
        {keysList.length > 0 && (
          <div className="space-y-2 mb-4 border-t border-zinc-800/80 pt-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
                Configured Keys ({keysList.length} Active)
              </label>
              <button
                type="button"
                onClick={handleClearAll}
                className="font-mono text-[10px] uppercase text-zinc-500 hover:text-red-400 transition-colors"
              >
                CLEAR ALL
              </button>
            </div>
            <div className="max-h-28 overflow-y-auto space-y-1.5 pr-1">
              {keysList.map((k) => (
                <div
                  key={k.id}
                  className="flex items-center justify-between border border-zinc-800 bg-black/50 px-3 py-1.5 text-xs font-mono"
                >
                  <div className="flex items-center gap-2">
                    <span className="border border-red-900/80 bg-red-950/60 px-1.5 py-0.5 text-[10px] font-bold text-red-400 uppercase">
                      {k.provider}
                    </span>
                    <span className="text-zinc-400 text-[11px]">{maskKey(k.key)}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveKey(k.id)}
                    className="text-zinc-500 hover:text-red-400 transition-colors p-1"
                    title="Remove key"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center gap-3 pt-3 border-t border-zinc-800">
          <button
            type="button"
            onClick={handleSave}
            disabled={keysList.length === 0 && !inputKey.trim()}
            className="w-full sm:flex-1 py-2.5 border border-red-600 bg-red-600 text-white font-mono font-bold text-xs uppercase tracking-wider transition-colors hover:bg-red-700 disabled:opacity-50 disabled:pointer-events-none flex items-center justify-center gap-2 shadow-md"
          >
            {savedSuccess ? (
              <>
                <Check className="h-4 w-4 text-white" />
                <span>SAVED &amp; APPLIED!</span>
              </>
            ) : (
              <span>
                {keysList.length > 0 || inputKey.trim()
                  ? `SAVE & APPLY ${keysList.length + (inputKey.trim() ? 1 : 0)} KEY${keysList.length + (inputKey.trim() ? 1 : 0) === 1 ? "" : "S"}`
                  : "SAVE API KEYS"}
              </span>
            )}
          </button>

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
