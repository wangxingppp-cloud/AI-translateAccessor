/**
 * Minimal audio visualizer — shows activity indicator when capturing.
 */
import { useEffect, useRef } from 'react';
import type { AudioCaptureState } from '../../types/audio';

interface AudioVisualizerProps {
  state: AudioCaptureState;
  /** Optional: latest chunk sample count for level meter. */
  level?: number;
}

export function AudioVisualizer({ state, level = 0 }: AudioVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const isActive = state === 'capturing';

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;

    const draw = () => {
      const w = canvas.width;
      const h = canvas.height;

      ctx.clearRect(0, 0, w, h);

      if (isActive && level > 0) {
        // Bar level meter with gradient
        const normalized = Math.min(level / 32768, 1) * 0.85;
        const barHeight = Math.max(h * normalized, 2);

        const gradient = ctx.createLinearGradient(0, h, 0, h - barHeight);
        gradient.addColorStop(0, 'rgba(0, 212, 255, 0.9)');
        gradient.addColorStop(1, 'rgba(0, 255, 136, 0.9)');
        ctx.fillStyle = gradient;

        // Rounded top corners
        const radius = 2;
        ctx.beginPath();
        ctx.moveTo(0, h);
        ctx.lineTo(0, h - barHeight + radius);
        ctx.quadraticCurveTo(0, h - barHeight, radius, h - barHeight);
        ctx.lineTo(w - radius, h - barHeight);
        ctx.quadraticCurveTo(w, h - barHeight, w, h - barHeight + radius);
        ctx.lineTo(w, h);
        ctx.closePath();
        ctx.fill();
      } else if (isActive) {
        // Pulsing dot
        ctx.fillStyle = '#00FF88';
        ctx.shadowColor = 'rgba(0, 255, 136, 0.6)';
        ctx.shadowBlur = 4;
        ctx.beginPath();
        ctx.arc(w / 2, h / 2, 3, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;
      } else {
        // Inactive
        ctx.fillStyle = '#5C6068';
        ctx.beginPath();
        ctx.arc(w / 2, h / 2, 2, 0, Math.PI * 2);
        ctx.fill();
      }

      animId = requestAnimationFrame(draw);
    };

    draw();
    return () => cancelAnimationFrame(animId);
  }, [isActive, level]);

  return (
    <canvas
      ref={canvasRef}
      className="audio-visualizer"
      width={44}
      height={20}
    />
  );
}
