import { useRouter } from 'expo-router';
import { FlatList, Pressable, StyleSheet } from 'react-native';

import { Text, View } from '@/components/Themed';
import Colors from '@/constants/Colors';
import { useColorScheme } from '@/components/useColorScheme';
import { hrefDisputeDetail } from '@/lib/navigation';
import { useSubmissions } from '@/lib/SubmissionsContext';

export default function DisputePickScreen() {
  const colorScheme = useColorScheme() ?? 'light';
  const theme = Colors[colorScheme];
  const { submissions } = useSubmissions();
  const router = useRouter();

  return (
    <View style={[styles.root, { backgroundColor: theme.background }]}>
      <Text style={[styles.intro, { color: theme.muted }]}>
        Choose an analysis you believe is wrong. Your dispute will be queued for admin review in the
        full system.
      </Text>
      <FlatList
        data={submissions}
        keyExtractor={(item) => item.id}
        contentContainerStyle={submissions.length === 0 ? styles.emptyWrap : styles.list}
        ListEmptyComponent={
          <Text style={[styles.empty, { color: theme.muted }]}>
            No analyses yet. Run a check from the home tab, then return here to dispute that verdict.
          </Text>
        }
        renderItem={({ item }) => (
          <Pressable
            onPress={() => router.push(hrefDisputeDetail(item.id))}
            style={({ pressed }) => [
              styles.row,
              { backgroundColor: theme.card, borderColor: theme.border, opacity: pressed ? 0.88 : 1 },
            ]}>
            <Text style={{ color: theme.text, fontWeight: '700' }} numberOfLines={2}>
              {item.textPreview || (item.imageUri ? 'Image check' : 'Submission')}
            </Text>
            <Text style={{ color: theme.muted, marginTop: 6, fontSize: 13 }}>
              {new Date(item.createdAt).toLocaleString()}
              {item.dispute ? ' · Dispute filed' : ''}
            </Text>
          </Pressable>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    paddingTop: 12,
  },
  intro: {
    paddingHorizontal: 20,
    paddingBottom: 12,
    fontSize: 14,
    lineHeight: 20,
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
});
