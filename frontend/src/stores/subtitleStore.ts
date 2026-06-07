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
  entries: SubtitleEntry[];
  /** Add or update a subtitle entry (upsert by id). */
  addEntry: (entry: SubtitleEntry) => void;
  /** Update an existing entry with corrected text + diff. */
  correctEntry: (id: string, text: string, diff: DiffSegment[]) => void;
  /** Clear all entries (session end). */
  clear: () => void;
  /** Get recent entries (for history/export). */
  getRecent: (n?: number) => SubtitleEntry[];
}

export const useSubtitleStore = create<SubtitleStore>((set, get) => ({
  entries: [],

  addEntry: (entry) =>
    set((s) => {
      const idx = s.entries.findIndex((e) => e.id === entry.id);
      if (idx >= 0) {
        // Update existing entry (merge translated if new one has it)
        const updated = [...s.entries];
        const prev = updated[idx];
        updated[idx] = {
          ...prev,
          translated: entry.translated || prev.translated,
          timestamp: entry.timestamp,
        };
        return { entries: updated };
      }
      // New entry
      return { entries: [...s.entries, entry].slice(-50) };
    }),

  correctEntry: (id, text, diff) =>
    set((s) => ({
      entries: s.entries.map((e) =>
        e.id === id ? { ...e, translated: text, isCorrected: true, diff } : e
      ),
    })),

  clear: () => set({ entries: [] }),

  getRecent: (n = 20) => {
    const { entries } = get();
    return entries.slice(-n);
  },
}));
