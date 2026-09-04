"use client";

import React, { useEffect, useRef, useState } from "react";

export default function EyeLasers() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [coords, setCoords] = useState<{
    eye1: { x: number; y: number };
    eye2: { x: number; y: number };
    target1: { x: number; y: number };
    target2: { x: number; y: number };
    box: {
      left: number;
      top: number;
      width: number;
      height: number;
      right: number;
      bottom: number;
    };
  } | null>(null);

  // Track coordinates of warrior eyes and target container
  useEffect(() => {
    const updateCoordinates = () => {
      const targetEl = document.getElementById("loading-container-box");
      if (!targetEl) return;

      const bRect = targetEl.getBoundingClientRect();

      // Precise warrior pupil coordinates from 1535 x 1025 background image:
      // Left eye pupil (viewer's left / warrior's right): x=448, y=356
      // Right eye pupil (viewer's right / warrior's left): x=593, y=373
      const warriorContainer = document.getElementById("warrior-hero-container");
      let eye1X = 0;
      let eye1Y = 0;
      let eye2X = 0;
      let eye2Y = 0;

      if (warriorContainer) {
        const wRect = warriorContainer.getBoundingClientRect();
        const scale = Math.max(wRect.width / 1535, wRect.height / 1025);
        eye1X = wRect.left + 448 * scale;
        eye1Y = wRect.top + 356 * scale;
        eye2X = wRect.left + 593 * scale;
        eye2Y = wRect.top + 373 * scale;
      } else {
        const H = window.innerHeight;
        const W = window.innerWidth;
        let cWidth = W;
        if (W >= 1280) cWidth = W * 0.48;
        else if (W >= 1024) cWidth = W * 0.50;
        else if (W >= 768) cWidth = W * 0.60;
        else if (W >= 640) cWidth = W * 0.70;

        const scale = Math.max(cWidth / 1535, H / 1025);
        eye1X = 448 * scale;
        eye1Y = 356 * scale;
        eye2X = 593 * scale;
        eye2Y = 373 * scale;
      }

      // Target impact points on container's left wall (independent trajectories)
      const target1 = {
        x: bRect.left + 1,
        y: bRect.top + bRect.height * 0.18,
      };
      const target2 = {
        x: bRect.left + 1,
        y: bRect.top + bRect.height * 0.72,
      };

      setCoords({
        eye1: { x: eye1X, y: eye1Y },
        eye2: { x: eye2X, y: eye2Y },
        target1,
        target2,
        box: {
          left: bRect.left,
          top: bRect.top,
          width: bRect.width,
          height: bRect.height,
          right: bRect.right,
          bottom: bRect.bottom,
        },
      });
    };

    updateCoordinates();
    window.addEventListener("resize", updateCoordinates);
    const interval = setInterval(updateCoordinates, 50);

    return () => {
      window.removeEventListener("resize", updateCoordinates);
      clearInterval(interval);
    };
  }, []);

  // Streaming Fire Particles along beams and rising off container borders
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);

    interface FireParticle {
      type: "beam" | "impact" | "border";
      x: number;
      y: number;
      vx: number;
      vy: number;
      size: number;
      color: string;
      alpha: number;
      decay: number;
      life: number;
      maxLife: number;
    }

    const particles: FireParticle[] = [];
    const flamePalette = ["#ffffff", "#fef08a", "#fde047", "#f97316", "#ef4444", "#dc2626", "#991b1b"];

    const spawnBeamParticle = (start: { x: number; y: number }, end: { x: number; y: number }): FireParticle => {
      const dx = end.x - start.x;
      const dy = end.y - start.y;
      const dist = Math.hypot(dx, dy) || 1;
      const speed = 16 + Math.random() * 14;
      const progress = Math.random() * 0.2; // spawn near eye
      const px = -dy / dist;
      const py = dx / dist;
      const spread = (Math.random() - 0.5) * 8;

      return {
        type: "beam",
        x: start.x + dx * progress + px * spread,
        y: start.y + dy * progress + py * spread,
        vx: (dx / dist) * speed + (Math.random() - 0.5) * 3,
        vy: (dy / dist) * speed + (Math.random() - 0.5) * 3,
        size: 1.5 + Math.random() * 3,
        color: flamePalette[Math.floor(Math.random() * (flamePalette.length - 2))],
        alpha: 0.85 + Math.random() * 0.15,
        decay: 0.02 + Math.random() * 0.02,
        life: 0,
        maxLife: Math.floor(dist / speed) + 5,
      };
    };

    const spawnImpactParticle = (target: { x: number; y: number }): FireParticle => {
      const angle = Math.PI * 0.6 + Math.random() * Math.PI * 0.8; // spray back-left and up/down
      const speed = 3 + Math.random() * 7;
      return {
        type: "impact",
        x: target.x + (Math.random() - 0.5) * 4,
        y: target.y + (Math.random() - 0.5) * 16,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        size: 1.2 + Math.random() * 2.5,
        color: flamePalette[Math.floor(Math.random() * flamePalette.length)],
        alpha: 0.9,
        decay: 0.025 + Math.random() * 0.03,
        life: 0,
        maxLife: 35 + Math.random() * 25,
      };
    };

    const spawnBorderEmber = (box: { left: number; top: number; width: number; height: number }): FireParticle => {
      // Spawn along the top edge or sides of the box
      const side = Math.random();
      let sx = box.left + Math.random() * box.width;
      let sy = box.top;
      if (side < 0.25) {
        // left edge
        sx = box.left;
        sy = box.top + Math.random() * box.height;
      } else if (side < 0.5) {
        // right edge
        sx = box.left + box.width;
        sy = box.top + Math.random() * box.height;
      }

      return {
        type: "border",
        x: sx,
        y: sy,
        vx: (Math.random() - 0.5) * 1.5,
        vy: -(1.5 + Math.random() * 3), // rise upwards like fire smoke
        size: 1 + Math.random() * 2.6,
        color: flamePalette[Math.floor(Math.random() * flamePalette.length)],
        alpha: 0.8,
        decay: 0.015 + Math.random() * 0.02,
        life: 0,
        maxLife: 40 + Math.random() * 40,
      };
    };

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // We need coordinates to spawn
      if (coords) {
        // Spawn beam particles
        for (let i = 0; i < 3; i++) {
          particles.push(spawnBeamParticle(coords.eye1, coords.target1));
          particles.push(spawnBeamParticle(coords.eye2, coords.target2));
        }
        // Spawn impact splash sparks
        for (let i = 0; i < 2; i++) {
          particles.push(spawnImpactParticle(coords.target1));
          particles.push(spawnImpactParticle(coords.target2));
        }
        // Spawn border fire embers
        if (particles.length < 180 && Math.random() > 0.3) {
          particles.push(spawnBorderEmber(coords.box));
        }
      }

      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;

        if (p.type === "border") {
          p.x += Math.sin(p.y * 0.05) * 0.6; // flame waver
        }

        p.alpha -= p.decay;
        p.life++;

        if (p.alpha <= 0 || p.life >= p.maxLife || p.x < -20 || p.x > width + 20 || p.y < -20) {
          particles.splice(i, 1);
          continue;
        }

        ctx.save();
        ctx.globalAlpha = Math.max(0, p.alpha);
        ctx.fillStyle = p.color;
        ctx.shadowColor = "#f97316";
        ctx.shadowBlur = p.type === "beam" ? 10 : 6;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", handleResize);
    };
  }, [coords]);

  if (!coords) return null;

  const { eye1, eye2, target1, target2, box } = coords;

  return (
    <div className="pointer-events-none fixed inset-0 z-30 overflow-hidden select-none">
      {/* Real-time Streaming Fire Canvas */}
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none z-40" />

      <svg className="w-full h-full">
        <defs>
          {/* Dynamic Beam Turbulence Filter (Physically wavers like roaring jet flame) */}
          <filter id="flameBeamNoise" x="-40%" y="-40%" width="180%" height="180%">
            <feTurbulence type="fractalNoise" baseFrequency="0.03 0.16" numOctaves="3" result="noise">
              <animate
                attributeName="baseFrequency"
                values="0.02 0.12; 0.04 0.24; 0.025 0.16; 0.02 0.12"
                dur="0.7s"
                repeatCount="indefinite"
              />
            </feTurbulence>
            <feDisplacementMap in="SourceGraphic" in2="noise" scale="18" xChannelSelector="R" yChannelSelector="G" />
          </filter>

          {/* Container Border Burning Flame Filter */}
          <filter id="flameBorderNoise" x="-20%" y="-20%" width="140%" height="140%">
            <feTurbulence type="fractalNoise" baseFrequency="0.025 0.08" numOctaves="3" result="borderNoise">
              <animate
                attributeName="baseFrequency"
                values="0.02 0.06; 0.035 0.12; 0.02 0.06"
                dur="1.2s"
                repeatCount="indefinite"
              />
            </feTurbulence>
            <feDisplacementMap in="SourceGraphic" in2="borderNoise" scale="14" xChannelSelector="R" yChannelSelector="G" />
          </filter>

          {/* Linear Gradients for the Flame Beams */}
          <linearGradient id="beamGrad1" x1={eye1.x} y1={eye1.y} x2={target1.x} y2={target1.y} gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="1" />
            <stop offset="15%" stopColor="#fef08a" stopOpacity="0.95" />
            <stop offset="45%" stopColor="#f97316" stopOpacity="0.9" />
            <stop offset="80%" stopColor="#ea580c" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#dc2626" stopOpacity="0.8" />
          </linearGradient>

          <linearGradient id="beamGrad2" x1={eye2.x} y1={eye2.y} x2={target2.x} y2={target2.y} gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="1" />
            <stop offset="15%" stopColor="#fef08a" stopOpacity="0.95" />
            <stop offset="45%" stopColor="#f97316" stopOpacity="0.9" />
            <stop offset="80%" stopColor="#ea580c" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#dc2626" stopOpacity="0.8" />
          </linearGradient>

          {/* Organic Eye Flame Aura (NO robotic white circle) */}
          <radialGradient id="eyeFireAura" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.95" />
            <stop offset="25%" stopColor="#fef08a" stopOpacity="0.8" />
            <stop offset="55%" stopColor="#f97316" stopOpacity="0.5" />
            <stop offset="80%" stopColor="#dc2626" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#7f1d1d" stopOpacity="0" />
          </radialGradient>

          {/* Molten Impact Burst (NO robotic white circle) */}
          <radialGradient id="impactFireBurst" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.9" />
            <stop offset="30%" stopColor="#fbbf24" stopOpacity="0.75" />
            <stop offset="65%" stopColor="#ea580c" stopOpacity="0.45" />
            <stop offset="90%" stopColor="#dc2626" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#000000" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* CONTAINER BURNING FIRE BORDERS (Torn, turbulent, organic flame silhouette) */}
        {/* Layer 1: Outward Licking Flame Aura */}
        <rect
          x={box.left - 6}
          y={box.top - 12}
          width={box.width + 12}
          height={box.height + 16}
          fill="none"
          stroke="#ea580c"
          strokeWidth="12"
          filter="url(#flameBorderNoise)"
          opacity="0.75"
        />

        {/* Layer 2: Intense Raging Fire Border */}
        <rect
          x={box.left - 2}
          y={box.top - 6}
          width={box.width + 4}
          height={box.height + 8}
          fill="none"
          stroke="#f97316"
          strokeWidth="6"
          filter="url(#flameBorderNoise)"
          opacity="0.9"
        />

        {/* Layer 3: White-Hot Molten Core Rim */}
        <rect
          x={box.left}
          y={box.top}
          width={box.width}
          height={box.height}
          fill="none"
          stroke="#fef08a"
          strokeWidth="2"
          opacity="0.95"
        />

        {/* Top Flame Tongues (Flames licking upward from container top) */}
        <line
          x1={box.left}
          y1={box.top - 2}
          x2={box.right}
          y2={box.top - 2}
          stroke="#fef08a"
          strokeWidth="8"
          filter="url(#flameBorderNoise)"
          opacity="0.85"
        />

        {/* Left Edge: Blazing Molten Impact Surface */}
        <line
          x1={box.left}
          y1={box.top}
          x2={box.left}
          y2={box.bottom}
          stroke="#ffffff"
          strokeWidth="4"
          filter="url(#flameBorderNoise)"
          opacity="0.95"
        />

        {/* STREAMING FIRE BEAM 1 (eye1 -> target1) */}
        {/* Outer turbulent flame mantle */}
        <line
          x1={eye1.x}
          y1={eye1.y}
          x2={target1.x}
          y2={target1.y}
          stroke="#dc2626"
          strokeWidth="26"
          strokeLinecap="round"
          filter="url(#flameBeamNoise)"
          opacity="0.7"
        />
        {/* Roaring orange fire jet */}
        <line
          x1={eye1.x}
          y1={eye1.y}
          x2={target1.x}
          y2={target1.y}
          stroke="url(#beamGrad1)"
          strokeWidth="12"
          strokeLinecap="round"
          filter="url(#flameBeamNoise)"
          opacity="0.9"
        />
        {/* Blazing yellow plasma filament */}
        <line
          x1={eye1.x}
          y1={eye1.y}
          x2={target1.x}
          y2={target1.y}
          stroke="#fef08a"
          strokeWidth="4"
          strokeLinecap="round"
          opacity="0.95"
        />
        {/* Incandescent white core stream */}
        <line
          x1={eye1.x}
          y1={eye1.y}
          x2={target1.x}
          y2={target1.y}
          stroke="#ffffff"
          strokeWidth="1.8"
          strokeLinecap="round"
        />

        {/* STREAMING FIRE BEAM 2 (eye2 -> target2) */}
        {/* Outer turbulent flame mantle */}
        <line
          x1={eye2.x}
          y1={eye2.y}
          x2={target2.x}
          y2={target2.y}
          stroke="#dc2626"
          strokeWidth="26"
          strokeLinecap="round"
          filter="url(#flameBeamNoise)"
          opacity="0.7"
        />
        {/* Roaring orange fire jet */}
        <line
          x1={eye2.x}
          y1={eye2.y}
          x2={target2.x}
          y2={target2.y}
          stroke="url(#beamGrad2)"
          strokeWidth="12"
          strokeLinecap="round"
          filter="url(#flameBeamNoise)"
          opacity="0.9"
        />
        {/* Blazing yellow plasma filament */}
        <line
          x1={eye2.x}
          y1={eye2.y}
          x2={target2.x}
          y2={target2.y}
          stroke="#fef08a"
          strokeWidth="4"
          strokeLinecap="round"
          opacity="0.95"
        />
        {/* Incandescent white core stream */}
        <line
          x1={eye2.x}
          y1={eye2.y}
          x2={target2.x}
          y2={target2.y}
          stroke="#ffffff"
          strokeWidth="1.8"
          strokeLinecap="round"
        />

        {/* EYE FIRE AURAS (Soft blazing flame glow - NO rigid circular dots) */}
        <circle cx={eye1.x} cy={eye1.y} r="26" fill="url(#eyeFireAura)" filter="url(#flameBeamNoise)" />
        <circle cx={eye1.x} cy={eye1.y} r="14" fill="url(#eyeFireAura)" />

        <circle cx={eye2.x} cy={eye2.y} r="26" fill="url(#eyeFireAura)" filter="url(#flameBeamNoise)" />
        <circle cx={eye2.x} cy={eye2.y} r="14" fill="url(#eyeFireAura)" />

        {/* MOLTEN IMPACT SPLASHES (Turbulent flame bursts - NO rigid circular dots) */}
        <ellipse cx={target1.x + 4} cy={target1.y} rx="34" ry="24" fill="url(#impactFireBurst)" filter="url(#flameBeamNoise)" />
        <ellipse cx={target1.x + 2} cy={target1.y} rx="18" ry="12" fill="url(#impactFireBurst)" />

        <ellipse cx={target2.x + 4} cy={target2.y} rx="34" ry="24" fill="url(#impactFireBurst)" filter="url(#flameBeamNoise)" />
        <ellipse cx={target2.x + 2} cy={target2.y} rx="18" ry="12" fill="url(#impactFireBurst)" />
      </svg>
    </div>
  );
}
