import { useEffect, useState } from 'react';
import { useColorScheme as useSystemColorScheme } from 'react-native';

// The web build is pre-rendered to static HTML, where the user's colour scheme
// is unknown. Render 'light' first so the server HTML and the first client
// render match (avoiding a hydration mismatch), then follow the system setting.
export function useColorScheme() {
  const system = useSystemColorScheme();
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => setHydrated(true), []);
  return hydrated ? system : 'light';
}
