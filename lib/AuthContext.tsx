import AsyncStorage from '@react-native-async-storage/async-storage';
import { router } from 'expo-router';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { ApiError, getCurrentUser, login, register, type ApiUser } from './api';
import { API_BASE_URL } from './config';

const STORAGE_KEY = 'kn_session_v1';

export type AuthUser = ApiUser & { avatarUri?: string | null };

type StoredSession = { accessToken: string; user: AuthUser };

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

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  const persist = useCallback(async (session: StoredSession | null) => {
    if (session) await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    else await AsyncStorage.removeItem(STORAGE_KEY);
    setAccessToken(session?.accessToken ?? null);
    setUser(session?.user ?? null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(STORAGE_KEY);
        if (!raw) return;
        const saved = JSON.parse(raw) as Partial<StoredSession>;
        if (!saved.accessToken || !saved.user?.email) {
          await AsyncStorage.removeItem(STORAGE_KEY);
          return;
        }

        let currentUser = saved.user as AuthUser;
        if (API_BASE_URL) {
          try {
            currentUser = { ...await getCurrentUser(saved.accessToken), avatarUri: currentUser.avatarUri ?? null };
          } catch (error) {
            if (error instanceof ApiError && error.status === 401) {
              await AsyncStorage.removeItem(STORAGE_KEY);
              return;
            }
            // Keep the cached profile for a temporary connection outage. Protected API calls still validate the token.
          }
        }
        if (!cancelled) {
          const session = { accessToken: saved.accessToken, user: currentUser };
          setAccessToken(session.accessToken);
          setUser(session.user);
          await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(session));
        }
      } catch {
        await AsyncStorage.removeItem(STORAGE_KEY);
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => { cancelled = true; };
  }, []);

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
    await persist({ accessToken, user: { ...user, avatarUri: patch.avatarUri ?? user.avatarUri ?? null } });
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
