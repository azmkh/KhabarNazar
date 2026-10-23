import { Redirect } from 'expo-router';

/**
 * The "Admin" tab (shown only to administrators) opens the moderation desk.
 * Pressing the tab navigates there directly (see (tabs)/_layout.tsx); this
 * redirect covers opening the route any other way.
 */
export default function ModerationTab() {
  return <Redirect href="/admin" />;
}
