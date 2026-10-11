import { Alert, Platform, type AlertButton } from 'react-native';

/**
 * Alert.alert is a no-op in React Native Web, so errors were silently
 * swallowed in the browser build. On web this falls back to window.alert and
 * then runs the first button's handler (the "OK" action).
 */
export function showAlert(title: string, message?: string, buttons?: AlertButton[]) {
  if (Platform.OS === 'web') {
    if (typeof window !== 'undefined') window.alert(message ? `${title}\n\n${message}` : title);
    buttons?.find((button) => button.style !== 'cancel')?.onPress?.();
    return;
  }
  Alert.alert(title, message, buttons);
}
