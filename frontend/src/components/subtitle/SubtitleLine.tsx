/**
 * Single subtitle entry — original + translated text.
 *
 * When a correction arrives (isCorrected=true), the translated text
 * briefly highlights to draw attention, then fades back to normal.
 */
import { useEffect, useState } from 'react';
import type { DiffSegment } from '../../types/ws-messages';

interface SubtitleLineProps {
  original: string;
  translated: string;
  isCorrected: boolean;
  diff?: DiffSegment[];
}

export function SubtitleLine({ original, translated, isCorrected, diff }: SubtitleLineProps) {
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    if (isCorrected) {
      setFlash(true);
      const timer = setTimeout(() => setFlash(false), 2000);
      return () => clearTimeout(timer);
    }
  }, [isCorrected, translated]);

  return (
    <div className={`subtitle-line ${isCorrected ? 'subtitle-line--corrected' : ''} ${flash ? 'subtitle-line--flash' : ''}`}>
      <div className="subtitle-line__original">{original}</div>
      <div className="subtitle-line__translated">
        {diff && diff.length > 0 ? (
          <DiffText segments={diff} />
        ) : (
          translated
        )}
      </div>
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
