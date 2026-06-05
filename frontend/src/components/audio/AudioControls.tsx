/**
 * Audio capture controls — start / pause / stop.
 */
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
          {isLoading ? '⏳ 请求权限...' : '▶ 开始翻译'}
        </button>
      ) : (
        <button
          type="button"
          className="control-btn control-btn--stop"
          onClick={onStop}
        >
          ⏹ 停止
        </button>
      )}
    </div>
  );
}
