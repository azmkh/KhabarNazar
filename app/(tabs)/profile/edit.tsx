import * as ImagePicker from 'expo-image-picker';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { Avatar, Button, Icon, useAppTheme } from '@/components/ui';
import { space } from '@/constants/theme';
import { useAuth } from '@/lib/AuthContext';
import { showAlert } from '@/lib/alert';

export default function EditProfileScreen() {
  const { colors } = useAppTheme();
  const { user, updateProfile } = useAuth();
  const router = useRouter();

  const [avatarUri, setAvatarUri] = useState<string | null>(user?.avatarUri ?? null);
  const [busy, setBusy] = useState(false);
  const changed = avatarUri !== (user?.avatarUri ?? null);

  async function pickAvatar() {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      showAlert('Photos', 'Allow library access to set a profile picture.');
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
      await updateProfile({ avatarUri });
      router.back();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Could not save.';
      showAlert('Edit profile', msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView style={{ backgroundColor: colors.background }} contentContainerStyle={styles.scroll}>
      <View style={styles.avatarArea}>
        <Pressable onPress={() => void pickAvatar()} accessibilityRole="button" accessibilityLabel="Choose profile photo">
          <Avatar uri={avatarUri} name={user?.name || user?.email} size={120} />
          <View style={[styles.cameraBadge, { backgroundColor: colors.primary, borderColor: colors.background }]}>
            <Icon name="camera" size={16} color={colors.onPrimary} />
          </View>
        </Pressable>
        <View style={styles.avatarActions}>
          <Button label="Choose photo" icon="image" variant="secondary" size="sm" onPress={() => void pickAvatar()} />
          {avatarUri ? (
            <Button label="Remove" icon="trash-2" variant="ghost" size="sm" onPress={() => setAvatarUri(null)} />
          ) : null}
        </View>
      </View>

      <Button label="Save" icon="check" onPress={() => void onSave()} loading={busy} disabled={!changed} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { padding: space.lg, gap: space.xl, paddingBottom: space.xxxl },
  avatarArea: { alignItems: 'center', gap: space.lg, paddingTop: space.lg },
  cameraBadge: {
    position: 'absolute',
    right: 2,
    bottom: 2,
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 3,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarActions: { flexDirection: 'row', gap: space.sm },
});
