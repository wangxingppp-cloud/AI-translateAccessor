/**
 * Subtitle state store — committed (history) + pending (real-time).
 *
 * Design:
 *   - committed: finalized sentences with translations, immutable
 *   - pending: in-progress sentence, updates in real-time
 *   - Translation arrives async, matched by sequence_id
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
  /** Committed sentences (history, immutable once added). */
  entries: SubtitleEntry[];
  /** Pending sentence (real-time, replaces on each update). */
  pending: SubtitleEntry | null;
  /** Add pending update or commit a sentence. */
  addEntry: (entry: SubtitleEntry & { isFinal?: boolean }) => void;
  /** Update translation for an existing committed entry. */
  updateTranslation: (id: string, translated: string) => void;
  /** Update correction diff for an entry. */
  correctEntry: (id: string, text: string, diff: DiffSegment[]) => void;
  /** Clear all state (session end). */
  clear: () => void;
  /** Get recent entries. */
  getRecent: (n?: number) => SubtitleEntry[];
}

export const useSubtitleStore = create<SubtitleStore>((set, get) => ({
  entries: [],
  pending: null,

  addEntry: (entry) =>
    set((s) => {
      if (entry.isFinal) {
        // Commit: add to entries, clear pending
        // Dedup: skip if last entry has same id or same text
        const last = s.entries[s.entries.length - 1];
        if (last && last.id === entry.id) {
          // Already committed, update translation only
          const updated = [...s.entries];
          updated[updated.length - 1] = { ...last, translated: entry.translated || last.translated };
          return { entries: updated, pending: null };
        }
        if (last && last.original.trim() === entry.original.trim()) {
          // Same text, skip duplicate
          return { entries: s.entries, pending: null };
        }
        const hist: SubtitleEntry = {
          id: entry.id, original: entry.original, translated: entry.translated || "",
          isCorrected: false, timestamp: entry.timestamp,
        };
        return { entries: [...s.entries, hist].slice(-100), pending: null };
      }

      // Pending update: skip if same text as last committed (dedup)
      const last = s.entries[s.entries.length - 1];
      if (last && last.original.trim() === entry.original.trim()) {
        return { pending: null };
      }

      // Skip if pending has same text
      if (s.pending && s.pending.original.trim() === entry.original.trim()) {
        return s; // no change
      }

      const cur: SubtitleEntry = {
        id: entry.id, original: entry.original, translated: "",
        isCorrected: false, timestamp: entry.timestamp,
      };
      return { pending: cur };
    }),

  updateTranslation: (id, translated) =>
    set((s) => {
      // Search all entries for matching id
      const idx = s.entries.findIndex((e) => e.id === id);
      if (idx >= 0) {
        const entry = s.entries[idx];
        // If entry already has a translation (NMT), mark as corrected (LLM refined)
        const isRefined = entry.translated && entry.translated !== translated;
        const updated = [...s.entries];
        updated[idx] = { ...entry, translated, isCorrected: isRefined };
        return { entries: updated };
      }
      // Also check pending
      if (s.pending?.id === id) {
        return { pending: { ...s.pending, translated } };
      }
      return s;
    }),

  correctEntry: (id, text, diff) =>
    set((s) => ({
      entries: s.entries.map((e) =>
        e.id === id ? { ...e, translated: text, isCorrected: true, diff } : e
      ),
      pending: s.pending?.id === id ? { ...s.pending, translated: text, isCorrected: true, diff } : s.pending,
    })),

  clear: () => set({ entries: [], pending: null }),

  getRecent: (n = 20) => {
    const { entries } = get();
    return entries.slice(-n);
  },
}));
