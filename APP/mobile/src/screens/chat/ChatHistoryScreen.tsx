import React from 'react';
import { View, Text, FlatList, StyleSheet, SafeAreaView, RefreshControl } from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useConversations } from '../../hooks/useConversations';
import { ScreenHeading } from '../../components/ScreenHeading';
import { MemberRow } from '../../components/MemberRow';
import { UnreadBadge } from '../../components/UnreadBadge';
import { SecondaryButton } from '../../components/SecondaryButton';
import { ErrorCard } from '../../components/ErrorCard';
import { LoadingOverlay } from '../../components/LoadingOverlay';
import { useAuth } from '../../auth/AuthContext';
import type { MainStackParams } from '../../types/navigation';
import { theme } from '../../style/theme';
import { formatConversationTime } from '@shared/utils/formatDate';
import { formatConversationPreview } from '@shared/utils/formatConversationPreview';
import { clientMessage } from '@shared/copy/client';

type Props = NativeStackScreenProps<MainStackParams, 'ChatHistory'>;

export function ChatHistoryScreen({ navigation }: Props) {
  const { user } = useAuth();
  const { conversations, loading, refreshing, error, refresh } = useConversations();

  return (
    <SafeAreaView style={styles.safe}>
      <LoadingOverlay visible={loading} />
      <View style={styles.container}>
        <ScreenHeading>היסטוריית שיחות</ScreenHeading>

        {error ? (
          <ErrorCard message={error} />
        ) : (
          <FlatList
            style={styles.list}
            data={conversations}
            keyExtractor={(item) => item.peer_id}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={refresh}
                tintColor={theme.palette.primary}
                colors={[theme.palette.primary]}
              />
            }
            renderItem={({ item }) => (
              <MemberRow
                name={item.peer_name || clientMessage('unknown_user_label')}
                subtitle={formatConversationPreview(item, user?.user_id ?? '')}
                timestamp={formatConversationTime(item.last_created_at)}
                onPress={() =>
                  navigation.navigate('Chat', {
                    peer_id:   item.peer_id,
                    peer_name: item.peer_name,
                  })
                }
                trailing={
                  item.unread_count > 0
                    ? <UnreadBadge count={item.unread_count} />
                    : undefined
                }
              />
            )}
            ListEmptyComponent={
              !loading ? (
                <Text style={styles.emptyText}>
                  עדיין אין שיחות. התחילו שיחה ממסך הגילוי 🙂
                </Text>
              ) : null
            }
          />
        )}

        <SecondaryButton text="חזור לתפריט הראשי" onPress={() => navigation.navigate('Menu')} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe:      { flex: 1 },
  container: { flex: 1, padding: theme.spacing.lg, gap: theme.spacing.md },
  list:      { flex: 1 },
  emptyText: {
    fontSize: theme.type.body,
    color: theme.palette.offline,
    textAlign: 'center',
    marginTop: theme.spacing.lg,
    fontFamily: theme.fontFamily,
  },
});
