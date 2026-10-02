import AsyncStorage from '@react-native-async-storage/async-storage';
import { router } from 'expo-router';
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

const STORAGE_KEY = 'kn_session_v1';

export type AuthUser = {
  email: string;
  displayName?: string | null;
  /** Local URI from image picker (demo); upload to server in production. */
  avatarUri?: string | null;
};

type AuthContextValue = {
  user: AuthUser | null;
  ready: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, displayName?: string) => Promise<void>;
  signOut: () => Promise<void>;
  updateProfile: (patch: {
    displayName?: string;
    email?: string;
    avatarUri?: string | null;
  }) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function validateEmail(email: string) {
  const trimmed = email.trim();
  if (!trimmed.includes('@') || trimmed.length < 5) {
    throw new Error('Enter a valid email address.');
  }
  return trimmed.toLowerCase();
}

function validatePassword(password: string) {
  if (password.length < 6) {
    throw new Error('Password must be at least 6 characters.');
  }
  return password;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const raw = await AsyncStorage.getItem(STORAGE_KEY);
        if (cancelled) return;
        if (raw) {
          const parsed = JSON.parse(raw) as AuthUser;
          if (parsed?.email) {
            setUser({
              email: parsed.email,
              displayName: parsed.displayName ?? null,
              avatarUri: parsed.avatarUri ?? null,
            });
          }
        }
      } catch {
        await AsyncStorage.removeItem(STORAGE_KEY);
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const persist = useCallback(async (next: AuthUser | null) => {
    if (next) {
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } else {
      await AsyncStorage.removeItem(STORAGE_KEY);
    }
    setUser(next);
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const e = validateEmail(email);
    validatePassword(password);
    await persist({ email: e });
    router.replace('/(tabs)');
  }, [persist]);

  const signUp = useCallback(
    async (email: string, password: string, displayName?: string) => {
      const e = validateEmail(email);
      validatePassword(password);
      const name = displayName?.trim() || undefined;
      await persist({ email: e, displayName: name });
      router.replace('/(tabs)');
    },
    [persist],
  );

  const updateProfile = useCallback(
    async (patch: {
      displayName?: string;
      email?: string;
      avatarUri?: string | null;
    }) => {
      if (!user) throw new Error('Not signed in.');
      const nextEmail = patch.email !== undefined ? validateEmail(patch.email) : user.email;
      const nextName =
        patch.displayName !== undefined ? patch.displayName.trim() || null : user.displayName;
      const nextAvatar =
        patch.avatarUri !== undefined ? patch.avatarUri : user.avatarUri ?? null;
      await persist({
        email: nextEmail,
        displayName: nextName,
        avatarUri: nextAvatar,
      });
    },
    [user, persist],
  );

  const signOut = useCallback(async () => {
    await persist(null);
    router.replace('/register');
  }, [persist]);

  const value = useMemo(
    () => ({
      user,
      ready,
      signIn,
      signUp,
      signOut,
      updateProfile,
    }),
    [user, ready, signIn, signUp, signOut, updateProfile],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
