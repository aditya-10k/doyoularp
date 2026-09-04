"use client";

import React from "react";
import Image from "next/image";
import { motion } from "framer-motion";
import Canvas3D from "./Canvas3D";

interface BackgroundHeroProps {
  children?: React.ReactNode;
  noScroll?: boolean;
}

export default function BackgroundHero({ children, noScroll = false }: BackgroundHeroProps) {
  return (
    <div className={`relative ${noScroll ? "h-screen max-h-screen overflow-hidden" : "min-h-screen overflow-x-hidden"} w-full bg-black`}>
      {/* 3D Particle Canvas */}
      <Canvas3D />

      {/* Stone Warrior Image: Top to bottom edge-to-edge on the left */}
      <div className="pointer-events-none fixed inset-0 z-0 select-none">
        <motion.div
          id="warrior-hero-container"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1.0, ease: "easeOut" }}
          className="relative h-screen w-full sm:w-[70vw] md:w-[60vw] lg:w-[50vw] xl:w-[48vw]"
        >
          <Image
            id="warrior-hero-image"
            src="/background.png"
            alt="Terracotta Warrior"
            fill
            priority
            className="object-cover object-left-top opacity-100"
          />
        </motion.div>
      </div>

      {/* Foreground Content */}
      <div className={`relative z-10 ${noScroll ? "h-screen max-h-screen" : "min-h-screen"} flex flex-col justify-center`}>
        {children}
      </div>
    </div>
  );
}
