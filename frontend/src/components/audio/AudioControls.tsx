/**
 * Audio capture controls — start / pause / resume / stop.
 *
 * When active, displays two buttons:
 *   - Pause/Resume toggle (syncs with backend)
 *   - Stop button (triggers save dialog)
 */
import { useState, useCallback } from 'react';
import { Play, Square, Loader2, Pause, Save, X } from 'lucide-react';
import type { AudioCaptureState } from '../../types/audio';

interface AudioControlsProps {
  state: AudioCaptureState;
  isPaused: boolean;
  onStart: () => void;
  onPause: () => void;
  onResume: () => void;
  onStopRequest: () => void;
}

export function AudioControls({ state, isPaused, onStart, onPause, onResume, onStopRequest }: AudioControlsProps) {
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
        <div className="audio-controls__active-group">
          <button
            type="button"
            className={`control-btn ${isPaused ? 'control-btn--resume' : 'control-btn--pause'}`}
            onClick={isPaused ? onResume : onPause}
          >
            {isPaused ? (
              <>
                <Play size={16} strokeWidth={2.5} />
                继续
              </>
            ) : (
              <>
                <Pause size={16} strokeWidth={2.5} />
                暂停
              </>
            )}
          </button>
          <button
            type="button"
            className="control-btn control-btn--stop"
            onClick={onStopRequest}
          >
            <Square size={16} strokeWidth={2.5} />
            结束
          </button>
        </div>
      )}
    </div>
  );
}

// ── Save Dialog ──────────────────────────────────────────────

interface SaveDialogProps {
  open: boolean;
  onSave: (name: string) => void;
  onDiscard: () => void;
  onCancel: () => void;
}

export function SaveDialog({ open, onSave, onDiscard, onCancel }: SaveDialogProps) {
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSave = useCallback(() => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setSaving(true);
    onSave(trimmed);
    setName('');
    setSaving(false);
  }, [name, onSave]);

  const handleDiscard = useCallback(() => {
    setName('');
    onDiscard();
  }, [onDiscard]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && name.trim()) {
      handleSave();
    } else if (e.key === 'Escape') {
      onCancel();
    }
  }, [name, handleSave, onCancel]);

  if (!open) return null;

  const now = new Date();
  const defaultName = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

  return (
    <div className="save-dialog-overlay" onClick={onCancel}>
      <div className="save-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="save-dialog__header">
          <h3 className="save-dialog__title">保存翻译记录</h3>
          <button type="button" className="save-dialog__close" onClick={onCancel} aria-label="关闭">
            <X size={16} />
          </button>
        </div>
        <div className="save-dialog__body">
          <p className="save-dialog__desc">是否将本次翻译记录保存到历史中？</p>
          <div className="save-dialog__input-row">
            <input
              type="text"
              className="settings-input save-dialog__input"
              placeholder={defaultName}
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={handleKeyDown}
              autoFocus
            />
          </div>
        </div>
        <div className="save-dialog__footer">
          <button
            type="button"
            className="save-dialog__btn save-dialog__btn--discard"
            onClick={handleDiscard}
          >
            不保存
          </button>
          <button
            type="button"
            className="save-dialog__btn save-dialog__btn--cancel"
            onClick={onCancel}
          >
            取消
          </button>
          <button
            type="button"
            className="save-dialog__btn save-dialog__btn--save"
            onClick={handleSave}
            disabled={!name.trim() || saving}
          >
            <Save size={14} />
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
