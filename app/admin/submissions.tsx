import FontAwesome from '@expo/vector-icons/FontAwesome';
import { useRouter } from 'expo-router';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import { hrefAdminReview } from '@/lib/navigation';
import { useSubmissions } from '@/lib/SubmissionsContext';

function verdictLabel(v: string) {
  if (v === 'credible') return 'Credible';
  if (v === 'misleading') return 'Misleading';
  return 'Uncertain';
}

export default function AdminSubmissionsScreen() {
  const router = useRouter();
  const { submissions } = useSubmissions();

  return (
    <View style={styles.root}>
      <FlatList
        data={submissions}
        keyExtractor={(item) => item.id}
        contentContainerStyle={submissions.length === 0 ? styles.emptyWrap : styles.list}
        ListEmptyComponent={
          <Text style={styles.empty}>No submissions yet.</Text>
        }
        renderItem={({ item }) => (
          <Pressable
            onPress={() => {
              if (item.dispute) router.push(hrefAdminReview(item.id));
            }}
            style={({ pressed }) => [styles.row, { opacity: pressed ? 0.9 : 1 }]}>
            <View style={styles.rowMain}>
              <Text style={styles.preview} numberOfLines={2}>
                {item.textPreview || (item.imageUri ? 'Image' : '—')}
              </Text>
              <View style={styles.tags}>
                <Text style={[styles.tag, { backgroundColor: '#e0f2fe', color: '#0369a1' }]}>
                  {verdictLabel(item.verdict)}
                </Text>
                {item.dispute ? (
                  <Text style={[styles.tag, { backgroundColor: '#ffedd5', color: '#9a3412' }]}>
                    Dispute
                  </Text>
                ) : null}
                {item.adminReview ? (
                  <Text style={[styles.tag, { backgroundColor: '#dcfce7', color: '#166534' }]}>
                    Reviewed
                  </Text>
                ) : null}
              </View>
            </View>
            <FontAwesome
              name={item.dispute ? 'chevron-right' : 'lock'}
              size={14}
              color="#94a3b8"
              style={{ alignSelf: 'center' }}
            />
          </Pressable>
        )}
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
    gap: 8,
  },
  emptyWrap: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
  },
  empty: {
    textAlign: 'center',
    color: '#64748b',
    fontSize: 15,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: '#fff',
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: '#d1fae5',
  },
  rowMain: {
    flex: 1,
  },
  preview: {
    fontSize: 15,
    fontWeight: '600',
    color: '#0f172a',
  },
  tags: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 8,
  },
  tag: {
    fontSize: 11,
    fontWeight: '700',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    overflow: 'hidden',
  },
});
