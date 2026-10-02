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
  TextInput,
} from 'react-native';

import { Text, View } from '@/components/Themed';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { analyzeSubmission } from '@/lib/api';
import { APP_TAGLINE } from '@/lib/config';
import { useAuth } from '@/lib/AuthContext';
import { hrefDisputeList } from '@/lib/navigation';
import { useSubmissions } from '@/lib/SubmissionsContext';

export default function CheckScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const theme = Colors[colorScheme];
  const router = useRouter();
  const { user } = useAuth();
  const { addSubmission } = useSubmissions();

  const [text, setText] = useState('');
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function pickImage() {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      Alert.alert('Permission needed', 'Allow photo library access to attach screenshots.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: false,
      quality: 0.85,
    });
    if (!result.canceled && result.assets[0]) {
      setImageUri(result.assets[0].uri);
    }
  }

  async function onSubmit() {
    try {
      setBusy(true);
      const analysis = await analyzeSubmission({ text, imageUri });
      const trimmed = text.trim();
      const kind = trimmed && imageUri ? 'both' : trimmed ? 'text' : 'image';
      const id = addSubmission({
        kind,
        textPreview: trimmed.slice(0, 280) || undefined,
        imageUri,
        verdict: analysis.verdict,
        confidence: analysis.confidence,
        summary: analysis.summary,
        languageQuality: analysis.languageQuality,
        languageQualityLabel: analysis.languageQualityLabel,
        sourceCredibility: analysis.sourceCredibility,
        sourceCredibilityLabel: analysis.sourceCredibilityLabel,
        manipulationLikelihood: analysis.manipulationLikelihood,
        manipulationLabel: analysis.manipulationLabel,
      });
      setText('');
      setImageUri(null);
      router.push(`/result/${id}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Something went wrong.';
      Alert.alert('Could not analyze', msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 88 : 0}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
        style={{ backgroundColor: theme.background }}>
        <View
          style={[
            styles.welcome,
            { backgroundColor: theme.card, borderColor: theme.border },
          ]}>
          <View style={styles.welcomeTop}>
            {user?.avatarUri ? (
              <Image source={{ uri: user.avatarUri }} style={styles.welcomeAvatar} />
            ) : null}
            <Text style={[styles.welcomeHi, { color: theme.text, flex: 1 }]}>
              Hello,{' '}
              <Text style={{ fontWeight: '800' }}>
                {user?.displayName?.trim() || user?.email?.split('@')[0] || 'there'}
              </Text>
            </Text>
          </View>
          <Text style={[styles.welcomeSub, { color: theme.muted }]}>
            Submit text or a screenshot for a credibility check. If the verdict feels wrong, you
            can open a dispute.
          </Text>
          <Pressable
            onPress={() => router.push(hrefDisputeList())}
            style={({ pressed }) => [
              styles.disputeEntry,
              { borderColor: theme.tint, opacity: pressed ? 0.88 : 1 },
            ]}
            accessibilityRole="button">
            <FontAwesome name="gavel" size={16} color={theme.tint} />
            <Text style={[styles.disputeEntryText, { color: theme.tint }]}> Dispute an AI result</Text>
          </Pressable>
        </View>

        <View style={[styles.hero, { backgroundColor: theme.background }]}>
          <Text style={styles.heroTitle}>KhabarNazar</Text>
          <Text style={[styles.heroSub, { color: theme.muted }]}>{APP_TAGLINE}</Text>
        </View>

        <View
          style={[
            styles.card,
            { backgroundColor: theme.card, borderColor: theme.border },
          ]}>
          <Text style={[styles.label, { color: theme.muted }]}>Paste news (Urdu / Roman Urdu)</Text>
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder="e.g. headline or message you saw on WhatsApp…"
            placeholderTextColor={theme.muted}
            multiline
            textAlignVertical="top"
            style={[
              styles.input,
              { color: theme.text, borderColor: theme.border, backgroundColor: theme.background },
            ]}
          />

          <Text style={[styles.label, { color: theme.muted, marginTop: 14 }]}>Or attach a screenshot (max 10 MB on server)</Text>
          {imageUri ? (
            <View>
              <Image source={{ uri: imageUri }} style={styles.preview} resizeMode="contain" />
              <Pressable onPress={() => setImageUri(null)} style={styles.clearImage}>
                <Text style={{ color: theme.misleading, fontWeight: '600' }}>Remove image</Text>
              </Pressable>
            </View>
          ) : (
            <Pressable
              onPress={pickImage}
              style={[styles.attachBtn, { borderColor: theme.border }]}
              accessibilityRole="button">
              <FontAwesome name="image" size={18} color={theme.tint} />
              <Text style={[styles.attachLabel, { color: theme.tint }]}>Choose from gallery</Text>
            </Pressable>
          )}

          <Pressable
            onPress={onSubmit}
            disabled={busy}
            style={({ pressed }) => [
              styles.submit,
              { backgroundColor: theme.tint, opacity: busy ? 0.6 : pressed ? 0.9 : 1 },
            ]}
            accessibilityRole="button">
            {busy ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.submitText}>Analyze</Text>
            )}
          </Pressable>
        </View>

        <View style={[styles.notice, { borderColor: theme.border, backgroundColor: theme.card }]}>
          <Text style={[styles.noticeTitle, { color: theme.text }]}>Roman Urdu note</Text>
          <Text style={[styles.noticeBody, { color: theme.muted }]}>
            There is no large labeled Roman Urdu fake-news corpus yet. Accuracy may be lower than for
            Nastaliq Urdu; the live API should disclose confidence and limitations to users.
          </Text>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  scroll: {
    padding: 20,
    paddingBottom: 40,
  },
  welcome: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
  },
  welcomeTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  welcomeAvatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
  },
  welcomeHi: {
    fontSize: 20,
    lineHeight: 28,
  },
  welcomeSub: {
    marginTop: 8,
    fontSize: 14,
    lineHeight: 21,
  },
  disputeEntry: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 14,
    borderWidth: 1.5,
    borderRadius: 12,
    paddingVertical: 12,
    gap: 8,
  },
  disputeEntryText: {
    fontSize: 15,
    fontWeight: '700',
  },
  hero: {
    marginBottom: 16,
  },
  heroTitle: {
    fontSize: 28,
    fontWeight: '700',
    letterSpacing: -0.5,
  },
  heroSub: {
    marginTop: 6,
    fontSize: 15,
    lineHeight: 22,
  },
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 16,
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 8,
  },
  input: {
    minHeight: 120,
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    fontSize: 16,
    lineHeight: 22,
  },
  attachBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    borderWidth: 1,
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 12,
  },
  attachLabel: {
    fontSize: 16,
    fontWeight: '600',
  },
  preview: {
    width: '100%',
    height: 200,
    borderRadius: 12,
    backgroundColor: '#00000014',
  },
  clearImage: {
    marginTop: 8,
    alignSelf: 'flex-start',
  },
  submit: {
    marginTop: 20,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  submitText: {
    color: '#fff',
    fontSize: 17,
    fontWeight: '700',
  },
  notice: {
    marginTop: 20,
    padding: 14,
    borderRadius: 12,
    borderWidth: 1,
  },
  noticeTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 6,
  },
  noticeBody: {
    fontSize: 14,
    lineHeight: 20,
  },
});
