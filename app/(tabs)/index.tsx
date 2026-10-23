import * as ImagePicker from 'expo-image-picker';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Image, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { SubmissionRow } from '@/components/SubmissionRow';
import { AppText, Avatar, Button, Card, Icon, Masthead, Segmented, TextField, useAppTheme } from '@/components/ui';
import { radius, space } from '@/constants/theme';
import { submitImage, submitText } from '@/lib/api';
import { useAuth } from '@/lib/AuthContext';
import { hrefAdminRoot, hrefDisputeList, hrefProfileMe } from '@/lib/navigation';
import { useSubmissions } from '@/lib/SubmissionsContext';
import { showAlert } from '@/lib/alert';
import { useAdminPending } from '@/lib/useAdminPending';

type Mode = 'text' | 'image';
const MAX_TEXT = 10_000;
const MIN_TEXT = 3;
/** The backend rejects uploads over MAX_UPLOAD_SIZE_MB (10 MB). */
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;

export default function CheckScreen() {
  const { colors } = useAppTheme();
  const router = useRouter();
  const { user, accessToken } = useAuth();
  const { isAdmin, pending } = useAdminPending();
  const { submissions, total, disputeTotal, addServerSubmission } = useSubmissions();

  const [mode, setMode] = useState<Mode>('text');
  const [text, setText] = useState('');
  const [imageAsset, setImageAsset] = useState<ImagePicker.ImagePickerAsset | null>(null);
  const [busy, setBusy] = useState(false);

  const firstName = user?.name?.trim().split(/\s+/)[0] || user?.email?.split('@')[0] || 'there';
  const recent = submissions.slice(0, 3);
  const trimmed = text.trim();
  const canSubmit = mode === 'text' ? trimmed.length >= MIN_TEXT : Boolean(imageAsset);

  async function pickImage(source: 'library' | 'camera') {
    try {
      const perm = source === 'camera'
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!perm.granted) {
        showAlert('Permission needed', source === 'camera'
          ? 'Allow camera access to photograph a news item.'
          : 'Allow photo library access to attach screenshots.');
        return;
      }
      const options: ImagePicker.ImagePickerOptions = { mediaTypes: ['images'], allowsEditing: false, quality: 0.85 };
      const result = source === 'camera'
        ? await ImagePicker.launchCameraAsync(options)
        : await ImagePicker.launchImageLibraryAsync(options);
      if (!result.canceled && result.assets[0]) setImageAsset(result.assets[0]);
    } catch (e) {
      showAlert('Image', e instanceof Error ? e.message : 'Could not open the image picker.');
    }
  }

  async function onSubmit() {
    try {
      if (!accessToken) throw new Error('Your session is missing. Please sign in again.');
      setBusy(true);
      let response;
      if (mode === 'text') {
        response = await submitText(accessToken, trimmed);
      } else {
        const asset = imageAsset!;
        const mimeType = asset.mimeType?.toLowerCase();
        const extension = asset.fileName?.split('.').pop()?.toLowerCase() || asset.uri.split('.').pop()?.toLowerCase();
        const inferredType = mimeType || (extension === 'png' ? 'image/png' : extension === 'webp' ? 'image/webp' : 'image/jpeg');
        if (!['image/jpeg', 'image/png', 'image/webp'].includes(inferredType)) {
          throw new Error('Choose a JPG, PNG, or WEBP image.');
        }
        if (asset.fileSize && asset.fileSize > MAX_IMAGE_BYTES) {
          throw new Error('This image is larger than 10 MB. Choose a smaller one or a screenshot.');
        }
        const suffix = inferredType === 'image/png' ? 'png' : inferredType === 'image/webp' ? 'webp' : 'jpg';
        response = await submitImage(accessToken, {
          uri: asset.uri,
          name: asset.fileName || `upload.${suffix}`,
          type: inferredType,
        });
      }
      const id = addServerSubmission(response, mode === 'image' ? imageAsset?.uri : null);
      setText('');
      setImageAsset(null);
      router.push(`/result/${id}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Something went wrong.';
      showAlert('Could not analyze', msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView
        style={{ backgroundColor: colors.background }}
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled">
        <Masthead
          kicker={`Hello, ${firstName}`}
          title="What would you like to check?"
          accessory={
            <Pressable onPress={() => router.push(hrefProfileMe())} accessibilityRole="button" accessibilityLabel="My profile">
              <Avatar uri={user?.avatarUri} name={user?.name || user?.email} size={44} onInk />
            </Pressable>
          }>
          <View style={styles.stats}>
            <Stat value={total} label={total === 1 ? 'check' : 'checks'} />
            <View style={[styles.statDivider, { backgroundColor: colors.inkSoft }]} />
            <Stat value={disputeTotal} label={disputeTotal === 1 ? 'dispute' : 'disputes'} />
          </View>
        </Masthead>

        <View style={styles.body}>
          {isAdmin ? (
            // Administrators get a clear way into the moderation desk from the first screen.
            <Card onPress={() => router.push(hrefAdminRoot())} style={[styles.adminCard, { borderColor: colors.primary }]}>
              <View style={styles.adminRow}>
                <View style={[styles.adminIcon, { backgroundColor: colors.primarySoft }]}>
                  <Icon name="shield-check" size={22} color="primary" />
                </View>
                <View style={styles.flex}>
                  <AppText variant="overline" color="primary">Signed in as administrator</AppText>
                  <AppText variant="bodyStrong">Open the moderation desk</AppText>
                  <AppText variant="caption" color={pending ? 'uncertain' : 'textMuted'}>
                    {pending == null ? 'Review disputes and every submission' : pending
                      ? `${pending} ${pending === 1 ? 'dispute is' : 'disputes are'} waiting for review`
                      : 'No disputes waiting right now'}
                  </AppText>
                </View>
                <Icon name="chevron-right" size={20} color="primary" />
              </View>
            </Card>
          ) : null}
          <Card style={styles.composer}>
            <Segmented<Mode>
              value={mode}
              onChange={setMode}
              options={[
                { value: 'text', label: 'Text', icon: 'type' },
                { value: 'image', label: 'Image', icon: 'image' },
              ]}
            />

            {mode === 'text' ? (
              <View style={styles.gap}>
                <TextField
                  value={text}
                  onChangeText={setText}
                  multiline
                  maxLength={MAX_TEXT}
                  placeholder="Paste a headline or WhatsApp forward in Urdu, Roman Urdu, or English…"
                  accessibilityLabel="News text to check"
                />
                <View style={styles.meta}>
                  <AppText variant="caption" color="textSubtle">Urdu · Roman Urdu · English</AppText>
                  <AppText variant="caption" color="textSubtle">{text.length.toLocaleString()} / {MAX_TEXT.toLocaleString()}</AppText>
                </View>
              </View>
            ) : imageAsset ? (
              <View style={styles.gap}>
                <View style={[styles.preview, { backgroundColor: colors.surfaceMuted }]}>
                  <Image source={{ uri: imageAsset.uri }} style={styles.previewImage} resizeMode="contain" />
                  <Pressable
                    onPress={() => setImageAsset(null)}
                    style={[styles.removeImage, { backgroundColor: colors.ink }]}
                    accessibilityRole="button"
                    accessibilityLabel="Remove image">
                    <Icon name="x" size={16} color="onInk" />
                  </Pressable>
                </View>
                <AppText variant="caption" color="textSubtle" numberOfLines={1}>
                  {imageAsset.fileName ?? 'Selected image'}
                </AppText>
              </View>
            ) : (
              <View style={[styles.dropzone, { borderColor: colors.borderStrong, backgroundColor: colors.surfaceMuted }]}>
                <View style={[styles.dropIcon, { backgroundColor: colors.primarySoft }]}>
                  <Icon name="image-plus" size={26} color="primary" />
                </View>
                <AppText variant="bodyStrong" align="center">Add a news screenshot or poster</AppText>
                <AppText variant="caption" color="textMuted" align="center">
                  JPG, PNG or WEBP up to 10 MB. Text in the image is read with OCR.
                </AppText>
                <View style={styles.pickRow}>
                  <Button label="Gallery" icon="image" variant="secondary" size="sm" onPress={() => void pickImage('library')} />
                  {Platform.OS !== 'web' ? (
                    <Button label="Camera" icon="camera" variant="secondary" size="sm" onPress={() => void pickImage('camera')} />
                  ) : null}
                </View>
              </View>
            )}

            <Button
              label="Analyze"
              icon="sparkles"
              onPress={() => void onSubmit()}
              loading={busy}
              disabled={!canSubmit}
            />
          </Card>

          <Card tone="muted">
            <View style={styles.noteRow}>
              <Icon name="info" size={18} color="info" />
              <View style={styles.flex}>
                <AppText variant="bodyStrong">Decision support, not a final verdict</AppText>
                <AppText variant="caption" color="textMuted" style={styles.noteBody}>
                  The connected text model currently supports Urdu script. Roman Urdu and English may
                  return Uncertain until compatible models are connected. Any model result can be wrong;
                  check the explanation and dispute results you disagree with.
                </AppText>
              </View>
            </View>
          </Card>

          <View style={styles.sectionHeader}>
            <AppText variant="heading">Recent checks</AppText>
            {submissions.length > 0 ? (
              <Pressable onPress={() => router.push('/history')} hitSlop={8} accessibilityRole="link">
                <AppText variant="caption" color="primary">See all</AppText>
              </Pressable>
            ) : null}
          </View>
          {recent.length ? (
            <View style={styles.gap}>
              {recent.map((item) => (
                <SubmissionRow key={item.id} item={item} onPress={() => router.push(`/result/${item.id}`)} />
              ))}
            </View>
          ) : (
            <AppText variant="body" color="textMuted">Your checks will appear here.</AppText>
          )}

          <Button
            label="Dispute an AI result"
            icon="scale"
            variant="ghost"
            onPress={() => router.push(hrefDisputeList())}
          />
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  return (
    <View style={styles.stat}>
      <AppText variant="heading" color="onInk">{value}</AppText>
      <AppText variant="caption" color="onInkMuted">{label}</AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  scroll: { paddingBottom: space.xxxl },
  stats: { flexDirection: 'row', alignItems: 'center', gap: space.lg, marginTop: space.lg },
  stat: { flexDirection: 'row', alignItems: 'baseline', gap: 6 },
  statDivider: { width: 1, height: 18 },
  body: { paddingHorizontal: space.lg, gap: space.lg, marginTop: -space.lg },
  composer: { gap: space.lg },
  adminCard: { borderWidth: 1.5 },
  adminRow: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  adminIcon: { width: 44, height: 44, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center' },
  gap: { gap: space.sm },
  meta: { flexDirection: 'row', justifyContent: 'space-between' },
  preview: { borderRadius: radius.md, overflow: 'hidden', height: 220 },
  previewImage: { width: '100%', height: '100%' },
  removeImage: {
    position: 'absolute',
    top: space.sm,
    right: space.sm,
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dropzone: {
    borderWidth: 1.5,
    borderStyle: 'dashed',
    borderRadius: radius.lg,
    paddingVertical: space.xxl,
    paddingHorizontal: space.lg,
    alignItems: 'center',
    gap: space.sm,
  },
  dropIcon: { width: 56, height: 56, borderRadius: radius.lg, alignItems: 'center', justifyContent: 'center', marginBottom: space.xs },
  pickRow: { flexDirection: 'row', gap: space.sm, marginTop: space.sm },
  noteRow: { flexDirection: 'row', gap: space.md },
  noteBody: { marginTop: 2 },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: space.sm },
});
