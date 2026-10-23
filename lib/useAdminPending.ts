import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';

import { listDisputes } from './api';
import { useAuth } from './AuthContext';

const REFRESH_MS = 60_000;

/**
 * For administrators: how many disputes are waiting for review (counted by the
 * server). Refreshes when the screen gains focus and every minute. Always null
 * for normal users, who make no request.
 */
export function useAdminPending() {
  const { user, accessToken } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [pending, setPending] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    if (!isAdmin || !accessToken) {
      setPending(null);
      return;
    }
    try {
      // A one-row page is enough: the total comes back in X-Total-Count.
      setPending((await listDisputes(accessToken, { status: 'pending', limit: 1 })).total);
    } catch {
      // Keep the last known count; the admin screens show their own errors.
    }
  }, [isAdmin, accessToken]);

  useFocusEffect(useCallback(() => { void refresh(); }, [refresh]));

  useEffect(() => {
    if (!isAdmin) return;
    const timer = setInterval(() => void refresh(), REFRESH_MS);
    return () => clearInterval(timer);
  }, [isAdmin, refresh]);

  return { isAdmin, pending };
}
