"use client";

import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Trophy } from "lucide-react";
import BackgroundHero from "@/components/BackgroundHero";
import ResumeUploader from "@/components/ResumeUploader";
import AnalysisProgress from "@/components/AnalysisProgress";
import ResultDashboard from "@/components/ResultDashboard";
import LeaderboardModal from "@/components/LeaderboardModal";
import EyeLasers from "@/components/EyeLasers";
import BurningQuote from "@/components/BurningQuote";
import {
  createAnalysis,
  uploadResume,
  getAnalysisResult,
  subscribeToAnalysisEvents,
} from "@/lib/api";
import { AnalysisStatus, ResultResponse } from "@/types";

type ViewState = "IDLE" | "PROCESSING" | "RESULT" | "ERROR";

export default function Home() {
  const [viewState, setViewState] = useState<ViewState>("IDLE");
  const [currentAnalysisId, setCurrentAnalysisId] = useState<string | null>(null);
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatus | null>(null);
  const [analysisResult, setAnalysisResult] = useState<ResultResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [showLeaderboard, setShowLeaderboard] = useState(false);

  // Stream analysis status via SSE when in PROCESSING state
  useEffect(() => {
    if (viewState !== "PROCESSING" || !currentAnalysisId) return;

    let isMounted = true;
    const unsubscribe = subscribeToAnalysisEvents(
      currentAnalysisId,
      (status) => {
        if (!isMounted) return;
        setAnalysisStatus(status);
      },
      async () => {
        if (!isMounted) return;
        try {
          const result = await getAnalysisResult(currentAnalysisId);
          if (isMounted) {
            setAnalysisResult(result);
            setViewState("RESULT");
          }
        } catch (err: any) {
          if (isMounted) {
            setErrorMessage(err.message || "Failed to retrieve analysis results.");
            setViewState("ERROR");
          }
        }
      },
      (errorMsg) => {
        if (!isMounted) return;
        setErrorMessage(errorMsg || "Analysis pipeline failed unexpectedly.");
        setViewState("ERROR");
      }
    );

    return () => {
      isMounted = false;
      unsubscribe();
    };
  }, [viewState, currentAnalysisId]);

  const handleUpload = async (file: File, customAlias?: string) => {
    try {
      setErrorMessage(null);
      const created = await createAnalysis(customAlias);
      setCurrentAnalysisId(created.analysis_id);
      setAnalysisStatus(created);
      setViewState("PROCESSING");

      await uploadResume(created.analysis_id, file);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to initiate analysis pipeline.");
      setViewState("ERROR");
    }
  };

  const handleReset = () => {
    setViewState("IDLE");
    setCurrentAnalysisId(null);
    setAnalysisStatus(null);
    setAnalysisResult(null);
    setErrorMessage(null);
  };

  return (
    <BackgroundHero noScroll={viewState === "IDLE"}>
      {/* Minimal Top-Right Leaderboard Trigger */}
      <div className="absolute top-4 right-4 sm:top-6 sm:right-6 z-20">
        <button
          onClick={() => setShowLeaderboard(true)}
          className="flex items-center gap-2 border border-zinc-800 bg-black/70 px-3.5 py-1.5 sm:px-4 sm:py-2 font-mono text-xs uppercase tracking-wider text-zinc-400 backdrop-blur-md transition-all hover:border-red-600 hover:text-white"
        >
          <Trophy className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-zinc-400" />
          <span>LEADERBOARD</span>
        </button>
      </div>

      {/* Main Content Layout */}
      <main className={`flex-1 flex flex-col justify-center px-4 sm:px-6 lg:px-12 ${viewState === "IDLE" ? "py-4 sm:py-6 h-full max-h-screen" : "py-12"} max-w-7xl mx-auto w-full`}>
        <AnimatePresence mode="wait">
          {/* 1. IDLE STATE: Warrior visible on left from top to bottom, Quote & Uploader on the right */}
          {viewState === "IDLE" && (
            <motion.div
              key="idle"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.6 }}
              className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-center w-full my-auto"
            >
              {/* Left spacer - Allows the stone warrior to stand unobstructed from top to bottom */}
              <div className="hidden lg:block lg:col-span-5 pointer-events-none" />

              {/* Right Column: Sparkled Large Sun Tzu Quote & Resume Uploader */}
              <div className="lg:col-span-7 space-y-4 sm:space-y-5 flex flex-col items-center lg:items-end">
                {/* Sun Tzu Quote: Scaled with Animated Shimmer & Sparkle */}
                <motion.div
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.8, delay: 0.15 }}
                  className="text-center lg:text-right space-y-2 max-w-2xl"
                >
                  <div className="hidden lg:block h-0.5 w-20 bg-gradient-to-r from-transparent to-red-600 ml-auto mb-3" />
                  <BurningQuote />
                </motion.div>

                {/* Clean Resume Uploader Box */}
                <div className="w-full max-w-lg">
                  <ResumeUploader onUpload={handleUpload} />
                </div>
              </div>
            </motion.div>
          )}

          {/* 2. PROCESSING STATE: Live radar & stage timeline with Eye Lasers */}
          {viewState === "PROCESSING" && analysisStatus && (
            <>
              {/* Red Laser Rays Shooting From Warrior Eyes to Loading Container */}
              <EyeLasers />

              <motion.div
                key="processing"
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.96 }}
                transition={{ duration: 0.5 }}
                className="w-full flex justify-center lg:justify-end my-auto relative z-20"
              >
                <div className="w-full max-w-xl">
                  <AnalysisProgress status={analysisStatus} />
                </div>
              </motion.div>
            </>
          )}

          {/* 3. RESULT STATE: Full breakdown dashboard */}
          {viewState === "RESULT" && analysisResult && (
            <motion.div
              key="result"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.7 }}
              className="py-6"
            >
              <ResultDashboard
                result={analysisResult}
                onOpenLeaderboard={() => setShowLeaderboard(true)}
                onReset={handleReset}
              />
            </motion.div>
          )}

          {/* 4. ERROR STATE */}
          {viewState === "ERROR" && (
            <motion.div
              key="error"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="max-w-lg mx-auto border border-red-900 bg-black/90 p-8 text-center space-y-4 my-auto backdrop-blur-md"
            >
              <div className="font-mono text-xs uppercase tracking-widest text-red-500 font-bold">
                [ PIPELINE ERROR ]
              </div>
              <p className="font-mono text-xs text-zinc-300">
                {errorMessage || "An unexpected error interrupted the analysis."}
              </p>
              <button
                onClick={handleReset}
                className="border border-zinc-700 bg-zinc-900 px-6 py-2.5 font-mono text-xs text-zinc-100 hover:border-zinc-500 uppercase tracking-wider"
              >
                RETURN TO UPLOAD
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Leaderboard Modal */}
      {showLeaderboard && (
        <LeaderboardModal
          analysisId={currentAnalysisId}
          onClose={() => setShowLeaderboard(false)}
        />
      )}
    </BackgroundHero>
  );
}
