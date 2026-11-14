/** "Just now", "5 min ago", "3 h ago", "Yesterday", then a short date. */
export function relativeTime(timestamp: number, now = Date.now()) {
  const seconds = Math.round((now - timestamp) / 1000);
  if (seconds < 60) return 'Just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return new Date(timestamp).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

export function fullDate(timestamp: number) {
  return new Date(timestamp).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function percent(value: number | null | undefined, digits = 1) {
  return value == null ? 'Unavailable' : `${(value * 100).toFixed(digits)}%`;
}

export function languageLabel(language: string | null | undefined) {
  switch (language) {
    case 'urdu': return 'Urdu script';
    case 'roman_urdu': return 'Roman Urdu';
    case 'english': return 'English';
    case 'mixed': return 'Mixed Urdu and Latin script';
    case 'unknown': return 'Not clearly identified';
    default: return language ?? 'Not detected';
  }
}

/**
 * Accept links the way people type them: "geo.tv/news" becomes "https://geo.tv/news".
 * Returns null when the text is not a usable web link.
 */
export function normalizeEvidenceLink(raw: string): string | null {
  const value = raw.trim();
  if (!value) return '';
  // Same rule as the backend: add https:// only when there is no scheme at all ("geo.tv/x"),
  // so "javascript:..." or "mailto:..." are rejected rather than rewritten.
  const hasScheme = /^[a-z][a-z0-9+-]*:/i.test(value);
  const withScheme = hasScheme ? value : `https://${value.replace(/^\/+/, '')}`;
  if (!/^https?:\/\//i.test(withScheme)) return null;
  // A host with a dot (example.com) and no spaces.
  return /^https?:\/\/[^\s/?#]+\.[^\s/?#]+\S*$/i.test(withScheme) ? withScheme : null;
}
