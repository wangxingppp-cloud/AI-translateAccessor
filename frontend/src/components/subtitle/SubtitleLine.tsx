/**
 * Single subtitle entry — original + translated text with TTS button.
 *
 * When a correction arrives (isCorrected=true), the translated text
 * briefly highlights to draw attention, then fades back to normal.
 */
import { useEffect, useState } from 'react';
import { Volume2, Loader2, VolumeX } from 'lucide-react';
import type { DiffSegment } from '../../types/ws-messages';
import { useTTSStore } from '../../stores/ttsStore';
import { useConnectionStore } from '../../stores/connectionStore';

interface SubtitleLineProps {
  id: string;
  original: string;
  translated: string;
  isCorrected: boolean;
  diff?: DiffSegment[];
}

export function SubtitleLine({ id, original, translated, isCorrected, diff }: SubtitleLineProps) {
  const [flash, setFlash] = useState(false);
  const { playingId, loadingId, play } = useTTSStore();
  const backendPort = useConnectionStore((s) => s.backendPort);

  const isPlaying = playingId === id;
  const isLoading = loadingId === id;

  useEffect(() => {
    if (isCorrected) {
      setFlash(true);
      const timer = setTimeout(() => setFlash(false), 2000);
      return () => clearTimeout(timer);
    }
  }, [isCorrected, translated]);

  const handleTTS = () => {
    if (!translated || !backendPort) return;
    play(id, translated, backendPort);
  };

  return (
    <div className={`subtitle-line ${isCorrected ? 'subtitle-line--corrected' : ''} ${flash ? 'subtitle-line--flash' : ''}`}>
      <div className="subtitle-line__original">{original}</div>
      {translated && (
        <div className="subtitle-line__translated-row">
          <span className="subtitle-line__translated">
            {diff && diff.length > 0 ? (
              <DiffText segments={diff} />
            ) : (
              translated
            )}
          </span>
          <button
            type="button"
            className={`tts-btn ${isPlaying ? 'tts-btn--playing' : ''}`}
            onClick={handleTTS}
            disabled={isLoading}
            title={isPlaying ? '停止朗读' : '朗读译文'}
            aria-label={isPlaying ? '停止朗读' : '朗读译文'}
          >
            {isLoading ? (
              <Loader2 size={14} className="animate-spin" />
            ) : isPlaying ? (
              <VolumeX size={14} />
            ) : (
              <Volume2 size={14} />
            )}
          </button>
        </div>
      )}
    </div>
  );
}

/** Render translated text with diff highlighting. */
function DiffText({ segments }: { segments: DiffSegment[] }) {
  // If unchanged, just show text
  if (segments.length === 1 && segments[0].type === 'unchanged') {
    return <>{segments[0].text}</>;
  }

  // Show deleted (strikethrough + red) and inserted (green)
  return (
    <span className="diff-text">
      {segments.map((seg, i) => {
        if (seg.type === 'unchanged') return <span key={i}>{seg.text}</span>;
        if (seg.type === 'deleted') return <span key={i} className="diff-text__del" title="修正前">{seg.text}</span>;
        if (seg.type === 'inserted') return <span key={i} className="diff-text__ins" title="LLM 修正">{seg.text}</span>;
        return null;
      })}
    </span>
  );
}
