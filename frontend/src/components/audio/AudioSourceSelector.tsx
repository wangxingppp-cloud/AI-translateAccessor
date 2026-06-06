/**
 * Audio source selector — microphone or system audio.
 */
import { Mic, Volume2 } from 'lucide-react';
import type { AudioSource } from '../../types/audio';

interface AudioSourceSelectorProps {
  value: AudioSource;
  onChange: (source: AudioSource) => void;
  disabled?: boolean;
}

export function AudioSourceSelector({
  value,
  onChange,
  disabled = false,
}: AudioSourceSelectorProps) {
  return (
    <div className="audio-source-selector">
      <label className="control-label">音频源</label>
      <div className="source-options">
        <button
          type="button"
          className={`source-option ${value === 'microphone' ? 'source-option--active' : ''}`}
          onClick={() => onChange('microphone')}
          disabled={disabled}
          title="使用麦克风采集现场语音"
        >
          <Mic size={14} strokeWidth={2} />
          <span>麦克风</span>
        </button>
        <button
          type="button"
          className={`source-option ${value === 'system' ? 'source-option--active' : ''}`}
          onClick={() => onChange('system')}
          disabled={disabled}
          title="捕获系统音频输出（播放中的视频/会议声音）"
        >
          <Volume2 size={14} strokeWidth={2} />
          <span>系统音频</span>
        </button>
      </div>
    </div>
  );
}
