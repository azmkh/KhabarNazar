import type { Href } from 'expo-router';

/** Typed routes may lag new paths; keep navigation calls here. */
export function hrefDisputeList(): Href {
  return '/dispute' as Href;
}

export function hrefDisputeDetail(id: string): Href {
  return `/dispute/${id}` as Href;
}

export function hrefProfileMe(): Href {
  return '/profile/me' as Href;
}

export function hrefProfileEdit(): Href {
  return '/profile/edit' as Href;
}

export function hrefProfileLogout(): Href {
  return '/profile/logout' as Href;
}

/**
 * Where a signed-in user lands (SRS Login: the role field decides the redirect target).
 * Pass the role from the backend's user response only, never a value the client chose.
 */
export function hrefHomeForRole(role: string | null | undefined): Href {
  return role === 'admin' ? hrefAdminRoot() : '/(tabs)';
}

export function hrefAdminRoot(): Href {
  return '/admin' as Href;
}

export function hrefAdminDisputes(): Href {
  return '/admin/disputes' as Href;
}

export function hrefAdminSubmissions(): Href {
  return '/admin/submissions' as Href;
}

export function hrefAdminReview(id: string): Href {
  return `/admin/review/${id}` as Href;
}
