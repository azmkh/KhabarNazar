import AsyncStorage from '@react-native-async-storage/async-storage';
import { router } from 'expo-router';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';

import { ApiError, getCurrentUser, login, register, setUnauthorizedHandler, type ApiUser } from './api';
import { showAlert } from './alert';
import { API_BASE_URL } from './config';
import { readToken, writeToken } from './tokenStorage';

// Non-secret profile only. The token itself lives in secure storage (lib/tokenStorage.ts).
const PROFILE_KEY = 'kn_session_v1';

export type AuthUser = ApiUser & { avatarUri?: string | null };

type Session = { accessToken: string; user: AuthUser };

type AuthContextValue = {
  user: AuthUser | null;
  accessToken: string | null;
  ready: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, displayName?: string) => Promise<void>;
  signOut: () => Promise<void>;
  updateProfile: (patch: { displayName?: string; email?: string; avatarUri?: string | null }) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function validateEmail(email: string) {
  const trimmed = email.trim();
  if (!trimmed.includes('@') || trimmed.length < 5) throw new Error('Enter a valid email address.');
  return trimmed.toLowerCase();
}

function validatePassword(password: string) {
  if (password.length < 6) throw new Error('Password must be at least 6 characters.');
}

async function clearStoredSession() {
  await writeToken(null);
  await AsyncStorage.removeItem(PROFILE_KEY);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const tokenRef = useRef<string | null>(null);

  const persist = useCallback(async (session: Session | null) => {
    if (session) {
      await writeToken(session.accessToken);
      await AsyncStorage.setItem(PROFILE_KEY, JSON.stringify({ user: session.user }));
    } else {
      await clearStoredSession();
    }
    tokenRef.current = session?.accessToken ?? null;
    setAccessToken(session?.accessToken ?? null);
    setUser(session?.user ?? null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(PROFILE_KEY);
        if (!raw) {
          await writeToken(null);
          return;
        }
        const saved = JSON.parse(raw) as { user?: AuthUser; accessToken?: string };
        // Sessions saved by older app versions kept the token in plain AsyncStorage: move it.
        if (saved.accessToken) {
          await writeToken(saved.accessToken);
          await AsyncStorage.setItem(PROFILE_KEY, JSON.stringify({ user: saved.user }));
        }
        const token = await readToken();
        if (!token || !saved.user?.email) {
          await clearStoredSession();
          return;
        }

        let currentUser = saved.user;
        if (API_BASE_URL) {
          try {
            currentUser = { ...await getCurrentUser(token), avatarUri: currentUser.avatarUri ?? null };
          } catch (error) {
            if (error instanceof ApiError && error.status === 401) {
              await clearStoredSession();
              return;
            }
            // Keep the cached profile for a temporary connection outage. Protected API calls still validate the token.
          }
        }
        if (!cancelled) {
          tokenRef.current = token;
          setAccessToken(token);
          setUser(currentUser);
          await AsyncStorage.setItem(PROFILE_KEY, JSON.stringify({ user: currentUser }));
        }
      } catch {
        await clearStoredSession().catch(() => undefined);
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // A protected request answered 401: the token expired or was revoked. Several requests can fail
  // at once, so only react to the token that is still current.
  useEffect(() => {
    setUnauthorizedHandler((failedToken) => {
      if (!tokenRef.current || failedToken !== tokenRef.current) return;
      tokenRef.current = null;
      void persist(null).then(() => {
        router.replace('/login');
        showAlert('Session expired', 'Please sign in again.');
      });
    });
    return () => setUnauthorizedHandler(null);
  }, [persist]);

  const signIn = useCallback(async (email: string, password: string) => {
    const normalizedEmail = validateEmail(email);
    validatePassword(password);
    const response = await login(normalizedEmail, password);
    await persist({ accessToken: response.access_token, user: response.user });
    router.replace('/(tabs)');
  }, [persist]);

  const signUp = useCallback(async (email: string, password: string, displayName?: string) => {
    const normalizedEmail = validateEmail(email);
    validatePassword(password);
    const emailName = normalizedEmail.split('@')[0];
    const name = displayName?.trim() || (emailName.length >= 2 ? emailName : 'KhabarNazar User');
    const response = await register(normalizedEmail, password, name);
    await persist({ accessToken: response.access_token, user: response.user });
    router.replace('/(tabs)');
  }, [persist]);

  const updateProfile = useCallback(async (patch: {
    displayName?: string; email?: string; avatarUri?: string | null;
  }) => {
    if (!user || !accessToken) throw new Error('Not signed in.');
    const requestedName = patch.displayName?.trim();
    if ((patch.email !== undefined && patch.email.trim().toLowerCase() !== user.email) ||
        (requestedName !== undefined && requestedName !== user.name)) {
      throw new Error('Name and email changes are not supported by the backend yet. Only the local profile photo can be changed.');
    }
    // `avatarUri: null` means "remove the photo", so only keep the old one when the key is absent.
    const avatarUri = 'avatarUri' in patch ? patch.avatarUri ?? null : user.avatarUri ?? null;
    await persist({ accessToken, user: { ...user, avatarUri } });
  }, [user, accessToken, persist]);

  const signOut = useCallback(async () => {
    await persist(null);
    router.replace('/login');
  }, [persist]);

  const value = useMemo(() => ({ user, accessToken, ready, signIn, signUp, signOut, updateProfile }),
    [user, accessToken, ready, signIn, signUp, signOut, updateProfile]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
