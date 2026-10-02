import FontAwesome from '@expo/vector-icons/FontAwesome';
import { useRouter } from 'expo-router';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { hrefAdminReview } from '@/lib/navigation';
import { useSubmissions } from '@/lib/SubmissionsContext';

export default function AdminDisputesScreen() {
  const router = useRouter();
  const { submissions } = useSubmissions();
  const list = submissions.filter((s) => s.dispute);

  return (
    <View style={styles.root}>
      <FlatList
        data={list}
        keyExtractor={(item) => item.id}
        contentContainerStyle={list.length === 0 ? styles.emptyWrap : styles.list}
        ListEmptyComponent={
          <View style={styles.emptyCard}>
            <FontAwesome name="inbox" size={40} color="#94a3b8" />
            <Text style={styles.emptyTitle}>No disputes in queue</Text>
            <Text style={styles.emptyBody}>
              When users file disputes from the app, they appear here for mandatory admin review.
            </Text>
          </View>
        }
        renderItem={({ item }) => {
          const pending = !item.adminReview;
          return (
            <Pressable
              onPress={() => router.push(hrefAdminReview(item.id))}
              style={({ pressed }) => [
                styles.row,
                { opacity: pressed ? 0.9 : 1 },
              ]}>
              <View style={styles.rowTop}>
                <View style={[styles.badge, pending ? styles.badgeOpen : styles.badgeDone]}>
                  <Text style={[styles.badgeText, pending ? styles.badgeTextOpen : styles.badgeTextDone]}>
                    {pending ? 'Open' : 'Reviewed'}
                  </Text>
                </View>
                <Text style={styles.date}>{new Date(item.dispute!.createdAt).toLocaleString()}</Text>
              </View>
              <Text style={styles.preview} numberOfLines={2}>
                {item.textPreview || (item.imageUri ? 'Image submission' : 'Submission')}
              </Text>
              {item.submitterEmail ? (
                <Text style={styles.meta}>From: {item.submitterEmail}</Text>
              ) : null}
              <Text style={styles.meta}>
                AI: {item.verdict} · {(item.confidence * 100).toFixed(1)}%
              </Text>
            </Pressable>
          );
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#ecfdf5',
  },
  list: {
    padding: 16,
    gap: 10,
  },
  emptyWrap: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
  },
  emptyCard: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 28,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#d1fae5',
  },
  emptyTitle: {
    marginTop: 14,
    fontSize: 18,
    fontWeight: '800',
    color: '#042f2e',
  },
  emptyBody: {
    marginTop: 8,
    textAlign: 'center',
    fontSize: 14,
    lineHeight: 21,
    color: '#64748b',
  },
  row: {
    backgroundColor: '#fff',
    borderRadius: 14,
    padding: 16,
    borderWidth: 1,
    borderColor: '#a7f3d0',
  },
  rowTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  badgeOpen: {
    backgroundColor: '#ffedd5',
  },
  badgeDone: {
    backgroundColor: '#dcfce7',
  },
  badgeText: {
    fontSize: 12,
    fontWeight: '800',
  },
  badgeTextOpen: {
    color: '#9a3412',
  },
  badgeTextDone: {
    color: '#166534',
  },
  date: {
    fontSize: 12,
    color: '#64748b',
  },
  preview: {
    marginTop: 10,
    fontSize: 15,
    fontWeight: '600',
    color: '#0f172a',
  },
  meta: {
    marginTop: 6,
    fontSize: 12,
    color: '#64748b',
  },
});
