import { useEffect, useState } from 'react';
import { Image, Platform, type ImageProps } from 'react-native';

import { useAuth } from '@/lib/AuthContext';

type Props = Omit<ImageProps, 'source'> & { uri: string };

/**
 * Image from a protected backend endpoint.
 *
 * Native platforms send `source.headers`, but React Native Web renders a plain
 * <img> and ignores headers, so the backend answered 401. On web we fetch the
 * image with the Bearer token and show it through a temporary blob URL.
 * Local URIs (file:, blob:, data:) are shown directly.
 */
export function AuthImage({ uri, ...rest }: Props) {
  const { accessToken } = useAuth();
  const needsAuth = /^https?:/i.test(uri);
  const [webUri, setWebUri] = useState<string | null>(null);

  useEffect(() => {
    if (Platform.OS !== 'web' || !needsAuth) return;
    let objectUrl: string | null = null;
    let cancelled = false;
    fetch(uri, { headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined })
      .then((response) => (response.ok ? response.blob() : Promise.reject(new Error(String(response.status)))))
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setWebUri(objectUrl);
      })
      .catch(() => { if (!cancelled) setWebUri(null); });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [uri, accessToken, needsAuth]);

  if (Platform.OS === 'web' && needsAuth) {
    return webUri ? <Image source={{ uri: webUri }} {...rest} /> : null;
  }
  return (
    <Image
      source={{ uri, headers: needsAuth && accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined }}
      {...rest}
    />
  );
}
