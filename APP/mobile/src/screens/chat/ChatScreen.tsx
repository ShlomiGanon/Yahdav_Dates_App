import React, { useRef, useState } from 'react';
import {
  View, StyleSheet, SafeAreaView, FlatList, ActivityIndicator,
  KeyboardAvoidingView, Platform, Keyboard,
} from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useMessages } from '../../hooks/useMessages';
import { ScreenHeading } from '../../components/ScreenHeading';
import { HebrewInput } from '../../components/HebrewInput';
import { PrimaryButton } from '../../components/PrimaryButton';
import { SecondaryButton } from '../../components/SecondaryButton';
import { ChatBubble } from '../../components/ChatBubble';
import { StatusBanner, StatusBannerRef } from '../../components/StatusBanner';
import { LoadingOverlay } from '../../components/LoadingOverlay';
import { useAuth } from '../../auth/AuthContext';
import type { MainStackParams } from '../../types/navigation';
import { theme } from '../../style/theme';
import { formatMessageTime } from '../../utils/formatDate';

type Props = NativeStackScreenProps<MainStackParams, 'Chat'>;

export function ChatScreen({ route, navigation }: Props) {
  const { peer_id, peer_name } = route.params;
  const { user } = useAuth();

  const bannerRef = useRef<StatusBannerRef>(null);
  const flatRef   = useRef<FlatList>(null);

  const { messages, loading, sending, loadingMore, loadOlder, sendMessage } =
    useMessages(peer_id, (msg, ok) => bannerRef.current?.showStatus(msg, ok));

  const [text, setText] = useState('');

  React.useEffect(() => {
    const kbSub = Keyboard.addListener('keyboardDidShow', () => {
      flatRef.current?.scrollToOffset({ offset: 0, animated: true });
    });
    return () => kbSub.remove();
  }, []);

  const handleSend = () => {
    const content = text.trim();
    if (!content) return;
    setText('');
    sendMessage(content);
  };

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <SafeAreaView style={styles.flex}>
        <LoadingOverlay visible={loading} />

        <View style={styles.header}>
          <ScreenHeading>{peer_name}</ScreenHeading>
          <StatusBanner ref={bannerRef} />
        </View>

        <FlatList
          ref={flatRef}
          style={styles.list}
          data={messages}
          keyExtractor={(item) => item.message_id}
          onEndReached={loadOlder}
          onEndReachedThreshold={0.3}
          renderItem={({ item }) => (
            <ChatBubble
              content={item.content}
              mine={item.sender_id === user?.user_id}
              createdAt={formatMessageTime(item.created_at)}
            />
          )}
          ListFooterComponent={
            loadingMore ? (
              <ActivityIndicator style={styles.footerSpinner} color={theme.palette.primary} />
            ) : null
          }
        />

        <View style={styles.sendBar}>
          <View style={styles.inputWrap}>
            <HebrewInput
              value={text}
              onChangeText={setText}
              placeholder="הקלידו הודעה…"
              onSubmitEditing={handleSend}
            />
          </View>
          <View style={styles.sendBtnWrap}>
            <PrimaryButton text="שלח" onPress={handleSend} loading={sending} />
          </View>
        </View>

        <View style={styles.backRow}>
          <SecondaryButton text="חזור" onPress={() => navigation.goBack()} />
        </View>
      </SafeAreaView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex:          { flex: 1 },
  header:        { paddingHorizontal: theme.spacing.lg, paddingTop: theme.spacing.md },
  list:          { flex: 1 },
  footerSpinner: { paddingVertical: theme.spacing.md },
  sendBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: theme.spacing.lg,
    paddingVertical: theme.spacing.sm,
    gap: theme.spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: theme.palette.offline,
  },
  inputWrap:   { flex: 1 },
  sendBtnWrap: { width: 90 },
  backRow: {
    alignItems: 'center',
    paddingHorizontal: theme.spacing.lg,
    paddingBottom: theme.spacing.md,
  },
});
