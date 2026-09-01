"use client";

import React, { useEffect, useRef } from "react";

export default function BurningQuote() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Floating Ember Particles rising off the burning letters
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = canvas.offsetWidth);
    let height = (canvas.height = canvas.offsetHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = canvas.offsetWidth;
      height = canvas.height = canvas.offsetHeight;
    };
    window.addEventListener("resize", handleResize);

    interface Ember {
      x: number;
      y: number;
      size: number;
      speedY: number;
      speedX: number;
      opacity: number;
      fadeSpeed: number;
      color: string;
      life: number;
      maxLife: number;
    }

    const embers: Ember[] = [];
    const colors = ["#ffffff", "#fef08a", "#f59e0b", "#f97316", "#ef4444", "#dc2626"];

    const createEmber = (initialY?: number): Ember => {
      const maxLife = 50 + Math.random() * 80;
      return {
        x: width * 0.05 + Math.random() * (width * 0.9),
        y: initialY ?? (height * 0.45 + Math.random() * (height * 0.5)),
        size: 1 + Math.random() * 2.8,
        speedY: 1.2 + Math.random() * 2.4,
        speedX: (Math.random() - 0.5) * 1.4,
        opacity: 0.7 + Math.random() * 0.3,
        fadeSpeed: 0.008 + Math.random() * 0.015,
        color: colors[Math.floor(Math.random() * colors.length)],
        life: 0,
        maxLife,
      };
    };

    // Initialize initial pool
    for (let i = 0; i < 45; i++) {
      embers.push(createEmber(Math.random() * height));
    }

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // Add new embers
      if (embers.length < 65 && Math.random() > 0.3) {
        embers.push(createEmber());
      }

      for (let i = embers.length - 1; i >= 0; i--) {
        const e = embers[i];
        e.y -= e.speedY;
        e.x += e.speedX + Math.sin(e.y * 0.04) * 0.6;
        e.life++;
        e.opacity -= e.fadeSpeed;

        if (e.opacity <= 0 || e.y < -10 || e.life >= e.maxLife) {
          embers.splice(i, 1);
          continue;
        }

        ctx.save();
        ctx.globalAlpha = Math.max(0, e.opacity);
        ctx.fillStyle = e.color;
        ctx.shadowColor = "#f97316";
        ctx.shadowBlur = 8;
        ctx.beginPath();
        ctx.arc(e.x, e.y, e.size, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  return (
    <div className="relative inline-block w-full select-none">
      {/* SVG Filters for Organic Flame Tongues and Heat Haze Distortion */}
      <svg className="absolute w-0 h-0 pointer-events-none opacity-0" aria-hidden="true">
        <defs>
          {/* Flame tongues displacement filter */}
          <filter id="flame-tongues" x="-20%" y="-60%" width="140%" height="220%">
            <feTurbulence type="fractalNoise" baseFrequency="0.025 0.12" numOctaves="3" result="flameNoise">
              <animate
                attributeName="baseFrequency"
                values="0.02 0.08; 0.035 0.16; 0.025 0.11; 0.02 0.08"
                dur="1.4s"
                repeatCount="indefinite"
              />
            </feTurbulence>
            <feDisplacementMap in="SourceGraphic" in2="flameNoise" scale="22" xChannelSelector="R" yChannelSelector="G" />
          </filter>

          {/* Molten fire flicker filter */}
          <filter id="fire-glow" x="-30%" y="-50%" width="160%" height="200%">
            <feTurbulence type="turbulence" baseFrequency="0.04 0.09" numOctaves="2" result="heatNoise">
              <animate
                attributeName="baseFrequency"
                values="0.04 0.09; 0.02 0.14; 0.04 0.09"
                dur="1.8s"
                repeatCount="indefinite"
              />
            </feTurbulence>
            <feDisplacementMap in="SourceGraphic" in2="heatNoise" scale="14" />
          </filter>
        </defs>
      </svg>

      {/* Floating Ember Particles Canvas Overlay */}
      <canvas
        ref={canvasRef}
        className="pointer-events-none absolute -inset-x-6 -top-10 -bottom-4 w-[calc(100%+3rem)] h-[calc(100%+3.5rem)] z-30"
      />

      {/* Burning Quote Container with 4 composited fire layers */}
      <div className="relative text-center lg:text-right">
        {/* Layer 1: Background Flame Inferno (Displaced upward licking flames) */}
        <span
          aria-hidden="true"
          className="absolute inset-0 font-serif text-3xl sm:text-4xl md:text-5xl lg:text-5xl xl:text-6xl font-black italic tracking-tight leading-[1.08] pointer-events-none z-0 filter-flame-tongues text-flame-inferno opacity-90 blur-[3px] -translate-y-1.5"
        >
          &ldquo;There is no limit to the larp&rdquo;
        </span>

        {/* Layer 2: Middle Wild Fire Licks (Secondary flickering flame silhouette) */}
        <span
          aria-hidden="true"
          className="absolute inset-0 font-serif text-3xl sm:text-4xl md:text-5xl lg:text-5xl xl:text-6xl font-black italic tracking-tight leading-[1.08] pointer-events-none z-10 filter-fire-glow text-flame-licks opacity-80 blur-[1px] -translate-y-1"
        >
          &ldquo;There is no limit to the larp&rdquo;
        </span>

        {/* Layer 3: White-Hot Incandescent Core (Sharp, readable, molten base) */}
        <blockquote className="relative z-20 font-serif text-3xl sm:text-4xl md:text-5xl lg:text-5xl xl:text-6xl font-black italic tracking-tight leading-[1.08] text-molten-core drop-shadow-[0_-3px_12px_rgba(255,100,0,0.8)]">
          &ldquo;There is no limit to the larp&rdquo;
        </blockquote>

        {/* Citation: Charred Ember Gold */}
        <cite className="relative z-20 font-mono text-xs sm:text-sm uppercase tracking-widest text-amber-400 drop-shadow-[0_0_8px_rgba(251,191,36,0.6)] not-italic block mt-2 sm:mt-2.5">
          &mdash; Sun Tzu, Art of War
        </cite>
      </div>
    </div>
  );
}
