/**
 * Auto-scrolling subtitle list.
 *
 * Behavior:
 *   - New entries auto-scroll to bottom
 *   - If user manually scrolls up, auto-scroll pauses
 *   - Auto-scroll resumes when user scrolls back to bottom
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import { SubtitleLine } from './SubtitleLine';
import type { DiffSegment } from '../../types/ws-messages';

export interface SubtitleEntry {
  id: string;
  original: string;
  translated: string;
  isCorrected: boolean;
  diff?: DiffSegment[];
}

interface SubtitleListProps {
  entries: SubtitleEntry[];
  placeholder?: string;
}

export function SubtitleList({ entries, placeholder }: SubtitleListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [userScrolledUp, setUserScrolledUp] = useState(false);
  const prevLengthRef = useRef(entries.length);

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Only auto-scroll if user hasn't scrolled up
    if (!userScrolledUp && entries.length > prevLengthRef.current) {
      container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    }
    prevLengthRef.current = entries.length;
  }, [entries, userScrolledUp]);

  // Detect user scroll
  const handleScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setUserScrolledUp(!atBottom);
  }, []);

  if (entries.length === 0 && placeholder) {
    return (
      <div className="subtitle-placeholder">
        <p className="subtitle-hint">{placeholder}</p>
      </div>
    );
  }

  return (
    <div className="subtitle-list" ref={containerRef} onScroll={handleScroll}>
      {entries.map((entry) => (
        <SubtitleLine
          key={entry.id}
          original={entry.original}
          translated={entry.translated}
          isCorrected={entry.isCorrected}
          diff={entry.diff}
        />
      ))}
      {userScrolledUp && (
        <button
          type="button"
          className="subtitle-scroll-btn"
          onClick={() => {
            const el = containerRef.current;
            if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
            setUserScrolledUp(false);
          }}
        >
          ↓ 滚动到最新
        </button>
      )}
    </div>
  );
}
