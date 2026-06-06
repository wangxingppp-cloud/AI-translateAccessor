/**
 * Audio capture controls — start / pause / stop.
 */
import { Play, Square, Loader2 } from 'lucide-react';
import type { AudioCaptureState } from '../../types/audio';

interface AudioControlsProps {
  state: AudioCaptureState;
  onStart: () => void;
  onStop: () => void;
}

export function AudioControls({ state, onStart, onStop }: AudioControlsProps) {
  const isActive = state === 'capturing';
  const isLoading = state === 'requesting';

  return (
    <div className="audio-controls">
      {!isActive ? (
        <button
          type="button"
          className={`control-btn control-btn--start ${isLoading ? 'control-btn--loading' : ''}`}
          onClick={onStart}
          disabled={isLoading}
        >
          {isLoading ? (
            <>
              <Loader2 size={16} strokeWidth={2.5} className="animate-spin" />
              请求权限...
            </>
          ) : (
            <>
              <Play size={16} strokeWidth={2.5} />
              开始翻译
            </>
          )}
        </button>
      ) : (
        <button
          type="button"
          className="control-btn control-btn--stop"
          onClick={onStop}
        >
          <Square size={16} strokeWidth={2.5} />
          停止
        </button>
      )}
    </div>
  );
}
