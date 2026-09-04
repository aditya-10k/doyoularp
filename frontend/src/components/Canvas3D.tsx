"use client";

import React, { useEffect, useRef } from "react";

interface Particle3D {
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  size: number;
  color: string;
}

export default function Canvas3D() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId: number;
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };

    window.addEventListener("resize", handleResize);

    // Mouse parallax tracking
    let mouseX = 0;
    let mouseY = 0;
    const handleMouseMove = (e: MouseEvent) => {
      mouseX = (e.clientX - width / 2) * 0.05;
      mouseY = (e.clientY - height / 2) * 0.05;
    };
    window.addEventListener("mousemove", handleMouseMove);

    // Generate 3D dust particles and crimson embers
    const particleCount = 120;
    const particles: Particle3D[] = [];

    for (let i = 0; i < particleCount; i++) {
      const isRed = Math.random() < 0.2; // 20% subtle crimson embers
      particles.push({
        x: (Math.random() - 0.5) * width * 1.5,
        y: (Math.random() - 0.5) * height * 1.5,
        z: Math.random() * 800 + 100,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.4 - 0.2, // gentle drift upwards
        vz: (Math.random() - 0.5) * 0.5,
        size: Math.random() * 2 + 0.8,
        color: isRed ? "rgba(220, 38, 38, " : "rgba(180, 180, 180, ",
      });
    }

    const fov = 400; // Field of view depth

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      // Subtle 3D perspective projection
      for (let i = 0; i < particleCount; i++) {
        const p = particles[i];

        // Update positions
        p.x += p.vx;
        p.y += p.vy;
        p.z += p.vz;

        // Wrap around boundaries
        if (p.z <= 50) p.z = 900;
        if (p.z > 900) p.z = 50;
        if (p.y < -height) p.y = height;
        if (p.y > height) p.y = -height;
        if (p.x < -width) p.x = width;
        if (p.x > width) p.x = -width;

        // Perspective projection calculation
        const perspective = fov / (fov + p.z);
        const screenX = (p.x + mouseX * 2) * perspective + width / 2;
        const screenY = (p.y + mouseY * 2) * perspective + height / 2;
        const radius = Math.max(0.5, p.size * perspective * 1.5);
        const alpha = Math.min(0.8, (1 - p.z / 900) * 0.7);

        // Draw particle
        ctx.beginPath();
        ctx.arc(screenX, screenY, radius, 0, Math.PI * 2);
        ctx.fillStyle = `${p.color}${alpha})`;
        ctx.fill();
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("mousemove", handleMouseMove);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="pointer-events-none fixed inset-0 z-0 h-full w-full opacity-60"
    />
  );
}
