import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { AppText, Button, useAppTheme } from '@/components/ui';
import { space } from '@/constants/theme';

type Props = {
  /** Rows loaded so far, and the total the server reported. */
  loaded: number;
  total: number;
  loading: boolean;
  onLoadMore: () => void;
  noun?: string;
};

/**
 * Footer for paged lists. Lists also load the next page when scrolled to the
 * end; the button is there for when the list is too short to scroll.
 */
export function LoadMoreFooter({ loaded, total, loading, onLoadMore, noun = 'checks' }: Props) {
  const { colors } = useAppTheme();
  if (total === 0) return null;
  const more = loaded < total;
  return (
    <View style={styles.wrap}>
      <AppText variant="caption" color="textSubtle" align="center">
        {more ? `Showing ${loaded} of ${total} ${noun}` : `All ${total} ${noun} loaded`}
      </AppText>
      {more ? (
        loading
          ? <ActivityIndicator color={colors.primary} />
          : <Button label="Load more" variant="secondary" size="sm" onPress={onLoadMore} />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', gap: space.sm, paddingTop: space.lg, paddingBottom: space.sm },
});
