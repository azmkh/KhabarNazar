import { StyleSheet, View } from 'react-native';

import { AppText, AuthImage, Card, Icon, Tag, VerdictBadge, useAppTheme } from '@/components/ui';
import { radius, space } from '@/constants/theme';
import { relativeTime } from '@/lib/format';
import type { Submission } from '@/types/submission';

type Props = {
  item: Submission;
  onPress: () => void;
  /** Show dispute / admin review status tags. */
  showStatus?: boolean;
};

/** One submission in a list: verdict, preview, time and status. */
export function SubmissionRow({ item, onPress, showStatus = true }: Props) {
  const { colors } = useAppTheme();
  const isImage = item.kind !== 'text';
  const preview = item.textPreview || (isImage ? 'Image submission' : 'Submission');

  return (
    <Card onPress={onPress} style={styles.card}>
      <View style={styles.row}>
        <View style={[styles.thumb, { backgroundColor: colors.surfaceMuted }]}>
          {isImage && item.imageUri ? (
            <AuthImage uri={item.imageUri} style={styles.thumbImage} />
          ) : (
            <Icon name={isImage ? 'image' : 'file-text'} size={20} color="textMuted" />
          )}
        </View>
        <View style={styles.body}>
          <View style={styles.top}>
            <VerdictBadge verdict={item.verdict} size="sm" />
            <AppText variant="caption" color="textSubtle">{relativeTime(item.createdAt)}</AppText>
          </View>
          <AppText variant="bodyStrong" numberOfLines={2}>{preview}</AppText>
          {showStatus && (item.dispute || item.adminReview) ? (
            <View style={styles.tags}>
              {item.dispute ? (
                <Tag
                  icon="flag"
                  label={item.dispute.status === 'pending' ? 'Dispute pending' : `Dispute ${item.dispute.status}`}
                  tone={item.dispute.status === 'pending' ? 'uncertain' : 'neutral'}
                />
              ) : null}
              {item.adminReview ? (
                <Tag
                  icon="badge-check"
                  label={item.adminReview.resolution === 'uphold_ai' ? 'Admin upheld AI' : 'Admin override'}
                  tone="credible"
                />
              ) : null}
            </View>
          ) : null}
        </View>
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { padding: space.md },
  row: { flexDirection: 'row', gap: space.md },
  thumb: {
    width: 52,
    height: 52,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  thumbImage: { width: '100%', height: '100%' },
  body: { flex: 1, gap: 6 },
  top: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.sm },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 2 },
});
