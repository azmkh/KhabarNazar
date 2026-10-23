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
    case 'unknown': return 'Could not identify confidently';
    default: return language ?? 'Not detected';
  }
}
