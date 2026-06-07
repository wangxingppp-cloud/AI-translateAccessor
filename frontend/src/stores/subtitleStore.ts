/**
 * Subtitle state store — manages the real-time subtitle display list.
 *
 * Entries are added when ASR produces text, updated when LLM correction arrives,
 * and optionally persisted for translation history.
 */
import { create } from 'zustand';
import type { DiffSegment } from '../types/ws-messages';

export interface SubtitleEntry {
  id: string;
  original: string;
  translated: string;
  isCorrected: boolean;
  diff?: DiffSegment[];
  timestamp: number;
}

interface SubtitleStore {
  /** Completed sentences (history). */
  entries: SubtitleEntry[];
  /** Current in-progress sentence (real-time display). */
  current: SubtitleEntry | null;
  /** Add or update subtitle (handles final vs in-progress). */
  addEntry: (entry: SubtitleEntry & { isFinal?: boolean; isReplace?: boolean }) => void;
  /** Update an existing entry with corrected text + diff. */
  correctEntry: (id: string, text: string, diff: DiffSegment[]) => void;
  /** Clear all entries (session end). */
  clear: () => void;
  /** Get recent entries (for history/export). */
  getRecent: (n?: number) => SubtitleEntry[];
}

export const useSubtitleStore = create<SubtitleStore>((set, get) => ({
  entries: [],
  current: null,

  addEntry: (entry) =>
    set((s) => {
      if (entry.isFinal) {
        // Dedup: don't add if last entry has same id
        const lastEntry = s.entries[s.entries.length - 1];
        if (lastEntry && lastEntry.id === entry.id) {
          // Update translation if provided
          const updated = [...s.entries];
          updated[updated.length - 1] = { ...lastEntry, translated: entry.translated || lastEntry.translated };
          return { entries: updated, current: null };
        }
        const hist: SubtitleEntry = {
          id: entry.id, original: entry.original, translated: entry.translated || "",
          isCorrected: false, timestamp: entry.timestamp,
        };
        return { entries: [...s.entries, hist].slice(-100), current: null };
      }

      const cur: SubtitleEntry = {
        id: entry.id, original: entry.original, translated: entry.translated || "",
        isCorrected: false, timestamp: entry.timestamp,
      };
      return { current: cur };
    }),

  correctEntry: (id, text, diff) =>
    set((s) => ({
      entries: s.entries.map((e) =>
        e.id === id ? { ...e, translated: text, isCorrected: true, diff } : e
      ),
      current: s.current?.id === id ? { ...s.current, translated: text, isCorrected: true, diff } : s.current,
    })),

  clear: () => set({ entries: [], current: null }),

  getRecent: (n = 20) => {
    const { entries } = get();
    return entries.slice(-n);
  },
}));
