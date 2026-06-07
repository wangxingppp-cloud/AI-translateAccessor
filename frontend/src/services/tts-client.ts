/**
 * TTS client — fetches synthesized speech from the backend.
 *
 * Simple stateless service with in-memory cache to avoid
 * re-synthesizing the same text on repeated clicks.
 */

const cache = new Map<string, ArrayBuffer>();
const CACHE_MAX = 50;

export async function fetchTTS(text: string, backendPort: number): Promise<ArrayBuffer> {
  const key = text.trim();
  const cached = cache.get(key);
  if (cached) return cached;

  const resp = await fetch(`http://127.0.0.1:${backendPort}/api/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: key }),
  });

  if (!resp.ok) {
    const err = await resp.text().catch(() => '');
    throw new Error(`TTS failed (${resp.status}): ${err}`);
  }

  const buf = await resp.arrayBuffer();

  // LRU-ish cache eviction
  if (cache.size >= CACHE_MAX) {
    const first = cache.keys().next().value;
    if (first !== undefined) cache.delete(first);
  }
  cache.set(key, buf);

  return buf;
}
