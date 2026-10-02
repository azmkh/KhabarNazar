import FontAwesome from '@expo/vector-icons/FontAwesome';
import * as ImagePicker from 'expo-image-picker';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Image,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { useAuth } from '@/lib/AuthContext';

export default function EditProfileScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const theme = Colors[colorScheme];
  const { user, updateProfile } = useAuth();
  const router = useRouter();

  const [name, setName] = useState(user?.displayName ?? '');
  const [email, setEmail] = useState(user?.email ?? '');
  const [avatarUri, setAvatarUri] = useState<string | null>(user?.avatarUri ?? null);
  const [busy, setBusy] = useState(false);

  async function pickAvatar() {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      Alert.alert('Photos', 'Allow library access to set a profile picture.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.85,
    });
    if (!result.canceled && result.assets[0]) {
      setAvatarUri(result.assets[0].uri);
    }
  }

  async function onSave() {
    try {
      setBusy(true);
      await updateProfile({ displayName: name, email, avatarUri });
      Alert.alert('Saved', 'Your profile has been updated.', [
        { text: 'OK', onPress: () => router.back() },
      ]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Could not save.';
      Alert.alert('Edit profile', msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: theme.background }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <Text style={[styles.sectionLabel, { color: theme.muted }]}>Profile photo</Text>
        <View style={styles.avatarRow}>
          <Pressable onPress={pickAvatar} style={styles.avatarWrap}>
            {avatarUri ? (
              <Image source={{ uri: avatarUri }} style={styles.avatarImg} />
            ) : (
              <View style={[styles.avatarPlaceholder, { borderColor: theme.border }]}>
                <FontAwesome name="user" size={40} color={theme.muted} />
              </View>
            )}
            <View style={[styles.cameraBadge, { backgroundColor: theme.tint }]}>
              <FontAwesome name="camera" size={14} color="#fff" />
            </View>
          </Pressable>
          <View style={styles.avatarActions}>
            <Pressable
              onPress={pickAvatar}
              style={[styles.smallBtn, { borderColor: theme.tint }]}>
              <FontAwesome name="picture-o" size={14} color={theme.tint} />
              <Text style={[styles.smallBtnText, { color: theme.tint }]}> Choose photo</Text>
            </Pressable>
            {avatarUri ? (
              <Pressable onPress={() => setAvatarUri(null)} style={styles.removeBtn}>
                <Text style={{ color: theme.misleading, fontWeight: '700', fontSize: 14 }}>Remove photo</Text>
              </Pressable>
            ) : null}
          </View>
        </View>

        <Text style={[styles.label, { color: theme.muted }]}>Display name</Text>
        <TextInput
          value={name}
          onChangeText={setName}
          placeholder="Your name"
          placeholderTextColor={theme.muted}
          style={[
            styles.input,
            { color: theme.text, borderColor: theme.border, backgroundColor: theme.card },
          ]}
        />

        <Text style={[styles.label, { color: theme.muted, marginTop: 16 }]}>Email</Text>
        <TextInput
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          keyboardType="email-address"
          placeholder="you@example.com"
          placeholderTextColor={theme.muted}
          style={[
            styles.input,
            { color: theme.text, borderColor: theme.border, backgroundColor: theme.card },
          ]}
        />

        <Pressable
          onPress={() => void onSave()}
          disabled={busy}
          style={({ pressed }) => [
            styles.save,
            { backgroundColor: theme.tint, opacity: busy ? 0.65 : pressed ? 0.9 : 1 },
          ]}>
          {busy ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text style={styles.saveText}>Save changes</Text>
          )}
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  scroll: {
    padding: 20,
    paddingBottom: 40,
  },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '800',
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginBottom: 10,
  },
  avatarRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 18,
    marginBottom: 24,
  },
  avatarWrap: {
    position: 'relative',
  },
  avatarImg: {
    width: 100,
    height: 100,
    borderRadius: 50,
  },
  avatarPlaceholder: {
    width: 100,
    height: 100,
    borderRadius: 50,
    borderWidth: 2,
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#00000008',
  },
  cameraBadge: {
    position: 'absolute',
    bottom: 2,
    right: 2,
    width: 30,
    height: 30,
    borderRadius: 15,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: '#fff',
  },
  avatarActions: {
    flex: 1,
    gap: 10,
  },
  smallBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    alignSelf: 'flex-start',
    borderWidth: 1.5,
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  smallBtnText: {
    fontSize: 14,
    fontWeight: '700',
  },
  removeBtn: {
    alignSelf: 'flex-start',
    paddingVertical: 4,
  },
  label: {
    fontSize: 13,
    fontWeight: '700',
    marginBottom: 8,
  },
  input: {
    borderWidth: 1,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: Platform.OS === 'ios' ? 14 : 10,
    fontSize: 16,
  },
  save: {
    marginTop: 28,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  saveText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },
});
