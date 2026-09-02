"use client";

import React, { useState, useRef } from "react";
import { motion } from "framer-motion";
import { FileUp, FileText, X, ArrowRight, AlertCircle } from "lucide-react";

interface ResumeUploaderProps {
  onUpload: (file: File, customAlias?: string) => void;
  isLoading?: boolean;
}

export default function ResumeUploader({ onUpload, isLoading }: ResumeUploaderProps) {
  const [dragOver, setDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [customAlias, setCustomAlias] = useState("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const validateAndSetFile = (file: File) => {
    setErrorMessage(null);
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setErrorMessage("REJECTED: File must be a valid PDF document.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setErrorMessage("REJECTED: File exceeds maximum allowed size (10 MB).");
      return;
    }
    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setErrorMessage("Please select or drop a PDF resume first.");
      return;
    }
    onUpload(selectedFile, customAlias.trim() || undefined);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.8 }}
      className="w-full max-w-lg mx-auto"
    >
      <form onSubmit={handleSubmit} className="space-y-2.5 sm:space-y-3">
        {/* Drag & Drop Area */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`relative cursor-pointer border transition-all duration-200 p-4 sm:p-5 text-center ${
            dragOver
              ? "border-red-500 bg-red-950/20"
              : selectedFile
              ? "border-zinc-500 bg-zinc-900/60"
              : "border-zinc-800 bg-black/60 hover:border-zinc-600 hover:bg-zinc-950/50"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            onChange={(e) => {
              if (e.target.files && e.target.files.length > 0) {
                validateAndSetFile(e.target.files[0]);
              }
            }}
            className="hidden"
          />

          {selectedFile ? (
            <div className="flex flex-col items-center justify-center space-y-2">
              <div className="flex h-9 w-9 items-center justify-center border border-zinc-700 bg-zinc-800 text-zinc-300">
                <FileText className="h-5 w-5 text-red-500" />
              </div>
              <div className="space-y-0.5">
                <p className="font-mono text-xs sm:text-sm font-semibold text-zinc-100 truncate max-w-xs sm:max-w-sm">
                  {selectedFile.name}
                </p>
                <p className="font-mono text-[10px] text-zinc-400">
                  {(selectedFile.size / 1024).toFixed(1)} KB &bull; PDF DOCUMENT
                </p>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedFile(null);
                }}
                className="inline-flex items-center gap-1 font-mono text-[10px] text-red-400 hover:text-red-300 pt-1"
              >
                <X className="h-3 w-3" />
                <span>REMOVE FILE</span>
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center space-y-2">
              <div className="flex h-9 w-9 items-center justify-center border border-zinc-800 bg-zinc-900/50 text-zinc-400">
                <FileUp className="h-5 w-5" />
              </div>
              <div className="space-y-0.5">
                <p className="font-mono text-xs sm:text-sm uppercase tracking-wider text-zinc-200">
                  DROP RESUME PDF HERE
                </p>
                <p className="font-mono text-[10px] sm:text-[11px] text-zinc-500">
                  OR CLICK TO BROWSE LOCAL FILES (MAX 10MB)
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Optional Custom Alias Input */}
        <div className="space-y-1">
          <label className="block font-mono text-[10px] uppercase tracking-widest text-zinc-400">
            ANONYMOUS HANDLE / ALIAS (OPTIONAL)
          </label>
          <input
            type="text"
            value={customAlias}
            onChange={(e) => setCustomAlias(e.target.value)}
            placeholder="e.g. Microservice Messiah, K8s Alchemist"
            maxLength={40}
            className="w-full border border-zinc-800 bg-zinc-950/80 px-3 py-2 font-mono text-xs text-zinc-100 placeholder:text-zinc-600 focus:border-red-600 focus:outline-none"
          />
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div className="flex items-center gap-2 border border-red-900/50 bg-red-950/30 p-2.5 text-red-400 font-mono text-xs">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Submit CTA */}
        <motion.button
          type="submit"
          whileHover={!selectedFile || isLoading ? {} : { scale: 1.01, boxShadow: "0 0 20px rgba(220, 38, 38, 0.4)" }}
          whileTap={!selectedFile || isLoading ? {} : { scale: 0.99 }}
          disabled={!selectedFile || isLoading}
          className={`w-full flex items-center justify-center gap-2 border py-2.5 sm:py-3 px-6 font-mono text-xs sm:text-sm uppercase tracking-widest transition-all ${
            !selectedFile || isLoading
              ? "border-zinc-800 bg-zinc-900/50 text-zinc-600 cursor-not-allowed"
              : "border-red-600 bg-red-600 text-white hover:bg-red-700"
          }`}
        >
          <span>{isLoading ? "ANALYZING EVIDENCE..." : "ANALYZE THIS FRAUD"}</span>
          <ArrowRight className="h-4 w-4" />
        </motion.button>
      </form>
    </motion.div>
  );
}
