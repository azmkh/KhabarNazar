/**
 * Set this to the backend origin, for example http://192.168.1.20:8000.
 * On Android emulator, use http://10.0.2.2:8000. The API client adds /api/v1.
 */
export const API_BASE_URL =
  ((typeof process !== 'undefined' && process.env?.EXPO_PUBLIC_API_URL) || '').replace(/\/$/, '');

export const APP_TAGLINE =
  'Decision support for Urdu, Roman Urdu, and news images — not absolute truth.';
