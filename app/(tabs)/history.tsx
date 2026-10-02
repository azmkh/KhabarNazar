import { useRouter } from 'expo-router';
import { FlatList, Pressable, StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { useSubmissions } from '@/lib/SubmissionsContext';
import type { Submission } from '@/types/submission';

function verdictLabel(v: Submission['verdict']) {
  if (v === 'credible') return 'Likely credible';
  if (v === 'misleading') return 'Likely misleading';
  return 'Uncertain';
}

export default function HistoryScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const theme = Colors[colorScheme];
  const { submissions } = useSubmissions();
  const router = useRouter();

  return (
    <View style={[styles.root, { backgroundColor: theme.background }]}>
      <FlatList
        data={submissions}
        keyExtractor={(item) => item.id}
        contentContainerStyle={submissions.length === 0 ? styles.emptyWrap : styles.list}
        ListEmptyComponent={
          <Text style={[styles.empty, { color: theme.muted }]}>
            No checks yet. Run an analysis from the Check tab — items are kept for this session on
            your device (wire up AsyncStorage or your API for persistence).
          </Text>
        }
        renderItem={({ item }) => (
          <Pressable
            onPress={() => router.push(`/result/${item.id}`)}
            style={({ pressed }) => [
              styles.row,
              { backgroundColor: theme.card, borderColor: theme.border, opacity: pressed ? 0.85 : 1 },
            ]}>
            <View style={styles.rowTop}>
              <Text style={[styles.badge, { color: theme[item.verdict] }]}>{verdictLabel(item.verdict)}</Text>
              <Text style={[styles.date, { color: theme.muted }]}>
                {new Date(item.createdAt).toLocaleString()}
              </Text>
            </View>
            <Text numberOfLines={2} style={{ color: theme.text, marginTop: 6 }}>
              {item.textPreview || (item.imageUri ? 'Image submission' : 'Submission')}
            </Text>
            {item.dispute ? (
              <Text style={{ color: theme.tint, marginTop: 8, fontSize: 12, fontWeight: '700' }}>
                Dispute filed · admin review pending
              </Text>
            ) : null}
            {item.adminReview ? (
              <Text style={{ color: theme.credible, marginTop: 6, fontSize: 12, fontWeight: '700' }}>
                Admin: {item.adminReview.resolution === 'uphold_ai' ? 'Uphold AI' : `Override → ${item.adminReview.overrideVerdict}`}
              </Text>
            ) : null}
          </Pressable>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  list: {
    padding: 16,
    gap: 12,
  },
  emptyWrap: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
  },
  empty: {
    textAlign: 'center',
    fontSize: 15,
    lineHeight: 22,
  },
  row: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
  },
  rowTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
  },
  badge: {
    fontWeight: '700',
    fontSize: 14,
  },
  date: {
    fontSize: 12,
  },
});
