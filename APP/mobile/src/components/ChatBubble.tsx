import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { theme } from '../style/theme';

type Props = {
  content: string;
  mine: boolean;
  createdAt?: string;
};

export function ChatBubble({ content, mine, createdAt }: Props) {
  return (
    <View style={[styles.wrapper, mine ? styles.wrapperMine : styles.wrapperPeer]}>
      <View style={[styles.bubble, mine ? styles.mine : styles.peer]}>
        <Text style={[styles.text, mine ? styles.textMine : styles.textPeer]}>{content}</Text>
        {createdAt && (
          <Text style={[styles.time, mine ? styles.timeMine : styles.timePeer]}>{createdAt}</Text>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    marginVertical: theme.spacing.xs,
    paddingHorizontal: theme.spacing.md,
  },
  // alignItems flex-end/start is immune to RTL axis flip on the cross-axis of a column
  wrapperMine: { alignItems: 'flex-end' },
  wrapperPeer: { alignItems: 'flex-start' },
  bubble: {
    maxWidth: '75%',
    borderRadius: theme.radius.bubble,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.sm,
  },
  mine:     { backgroundColor: theme.palette.selfBubble },
  peer:     { backgroundColor: theme.palette.peerBubble },
  text:     { fontSize: theme.type.body, fontFamily: theme.fontFamily },
  textMine: { color: theme.palette.surface },
  textPeer: { color: theme.palette.textMain },
  time:     { fontSize: theme.type.small, marginTop: theme.spacing.xs },
  timeMine: { color: 'rgba(255,255,255,0.7)' },
  timePeer: { color: theme.palette.offline },
});
