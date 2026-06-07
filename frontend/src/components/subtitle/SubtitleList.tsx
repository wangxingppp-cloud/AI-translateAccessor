/**
 * Auto-scrolling subtitle list.
 *
 * Behavior:
 *   - New entries auto-scroll to bottom
 *   - If user manually scrolls up, auto-scroll pauses
 *   - Auto-scroll resumes when user scrolls back to bottom
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import { ArrowDown } from 'lucide-react';
import { SubtitleLine } from './SubtitleLine';
import type { DiffSegment } from '../../types/ws-messages';

export interface SubtitleEntry {
  id: string;
  original: string;
  translated: string;
  isCorrected: boolean;
  diff?: DiffSegment[];
  timestamp?: number;
}

interface SubtitleListProps {
  entries: SubtitleEntry[];
  current?: SubtitleEntry | null;
  placeholder?: string;
}

export function SubtitleList({ entries, current, placeholder }: SubtitleListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [userScrolledUp, setUserScrolledUp] = useState(false);
  const prevLengthRef = useRef(entries.length);

  // Auto-scroll to bottom when new entries arrive or current updates
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    if (!userScrolledUp) {
      container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    }
    prevLengthRef.current = entries.length;
  }, [entries, current, userScrolledUp]);

  // Detect user scroll
  const handleScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setUserScrolledUp(!atBottom);
  }, []);

  const totalLen = entries.length + (current ? 1 : 0);

  if (totalLen === 0 && placeholder) {
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
          id={entry.id}
          original={entry.original}
          translated={entry.translated}
          isCorrected={entry.isCorrected}
          diff={entry.diff}
        />
      ))}
      {current && (
        <SubtitleLine
          key={`current-${current.id}`}
          id={current.id}
          original={current.original}
          translated={current.translated}
          isCorrected={current.isCorrected}
          isPending={true}
          diff={current.diff}
        />
      )}
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
          <ArrowDown size={12} strokeWidth={2} />
          滚动到最新
        </button>
      )}
    </div>
  );
}
