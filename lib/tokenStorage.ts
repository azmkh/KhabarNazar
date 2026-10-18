import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

/**
 * Where the login token (JWT) is kept.
 *
 * On a phone it goes into the iOS Keychain / Android Keystore via
 * expo-secure-store, which is encrypted by the operating system. Only the
 * non-secret profile (name, email, role, local photo) stays in AsyncStorage.
 * expo-secure-store has no web implementation, so the browser build falls back
 * to AsyncStorage (localStorage).
 */
const TOKEN_KEY = 'kn_access_token';

const useSecureStore = Platform.OS !== 'web';

export async function readToken(): Promise<string | null> {
  if (useSecureStore) return SecureStore.getItemAsync(TOKEN_KEY);
  return AsyncStorage.getItem(TOKEN_KEY);
}

export async function writeToken(token: string | null): Promise<void> {
  if (useSecureStore) {
    if (token) await SecureStore.setItemAsync(TOKEN_KEY, token);
    else await SecureStore.deleteItemAsync(TOKEN_KEY);
    return;
  }
  if (token) await AsyncStorage.setItem(TOKEN_KEY, token);
  else await AsyncStorage.removeItem(TOKEN_KEY);
}
