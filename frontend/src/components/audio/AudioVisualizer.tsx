/**
 * Minimal audio visualizer — shows activity indicator when capturing.
 *
 * Can be expanded later with waveform / FFT rendering.
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
        // Simple bar level meter
        const normalized = Math.min(level / 32768, 1) * 0.8;
        const barHeight = h * normalized;

        ctx.fillStyle = '#6366f1';
        ctx.fillRect(0, h - barHeight, w, barHeight);
      } else if (isActive) {
        // Idle pulsing dot
        ctx.fillStyle = '#22c55e';
        ctx.beginPath();
        ctx.arc(w / 2, h / 2, 3, 0, Math.PI * 2);
        ctx.fill();
      } else {
        // Inactive
        ctx.fillStyle = '#8b8d97';
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
      width={40}
      height={20}
    />
  );
}
