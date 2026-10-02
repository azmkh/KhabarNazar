/**
 * Point this at your FastAPI server when Phase 3 is ready.
 * Set EXPO_PUBLIC_API_URL in a .env file or in your shell before `expo start`.
 */
export const API_BASE_URL =
  (typeof process !== 'undefined' && process.env?.EXPO_PUBLIC_API_URL) || '';

export const APP_TAGLINE =
  'Decision support for Urdu, Roman Urdu, and news images — not absolute truth.';
