import React, { useCallback, useMemo, useRef, useState } from 'react';
import {
  View, Text, FlatList, StyleSheet, SafeAreaView, ActivityIndicator,
} from 'react-native';
import BottomSheet, { BottomSheetView, BottomSheetBackdrop } from '@gorhom/bottom-sheet';
import type { BottomSheetBackdropProps } from '@gorhom/bottom-sheet';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useCandidates } from '../../hooks/useCandidates';
import { ScreenHeading } from '../../components/ScreenHeading';
import { MemberRow } from '../../components/MemberRow';
import { PrimaryButton } from '../../components/PrimaryButton';
import { SecondaryButton } from '../../components/SecondaryButton';
import { ErrorCard } from '../../components/ErrorCard';
import { LoadingOverlay } from '../../components/LoadingOverlay';
import type { MainStackParams } from '../../types/navigation';
import type { Candidate } from '../../types/user';
import { theme } from '../../style/theme';
import { formatCandidateMetaSegments, EMPTY_CANDIDATE_META_LABEL } from '@shared/utils/formatCandidateMeta';
import { clientMessage } from '@shared/copy/client';

type Props = NativeStackScreenProps<MainStackParams, 'Discover'>;

const metaLine = (c: Candidate) =>
{
    const segments = formatCandidateMetaSegments(c);
    return segments.length ? segments.join('  ·  ') : EMPTY_CANDIDATE_META_LABEL;
};

export function DiscoverScreen({ navigation }: Props) {
  const sheetRef   = useRef<BottomSheet>(null);
  const snapPoints = useMemo(() => ['55%'], []);
  const [selected, setSelected] = useState<Candidate | null>(null);

  const { candidates, loading, loadingMore, error, loadMore } = useCandidates();

  const handleTap = (candidate: Candidate) => {
    setSelected(candidate);
    sheetRef.current?.expand();
  };

  const handleViewProfile = () => {
    if (!selected) return;
    sheetRef.current?.close();
    navigation.navigate('PeerProfile', { peer_id: selected.user_id });
  };

  const handleStartChat = () => {
    if (!selected) return;
    sheetRef.current?.close();
    navigation.navigate('Chat', { peer_id: selected.user_id, peer_name: selected.name });
  };

  const renderBackdrop = useCallback(
    (props: BottomSheetBackdropProps) => (
      <BottomSheetBackdrop {...props} disappearsOnIndex={-1} appearsOnIndex={0} pressBehavior="close" />
    ),
    [],
  );

  return (
    <View style={styles.root}>
      <SafeAreaView style={styles.safe}>
        <LoadingOverlay visible={loading} />
        <View style={styles.container}>
          <ScreenHeading>אנשים שתרצו להכיר</ScreenHeading>

          {error ? (
            <ErrorCard message={error} />
          ) : (
            <FlatList
              style={styles.list}
              data={candidates}
              keyExtractor={(item) => item.user_id}
              onEndReached={loadMore}
              onEndReachedThreshold={0.3}
              renderItem={({ item }) => (
                <MemberRow
                  src={item.photo_url}
                  name={item.name || clientMessage('unknown_user_label')}
                  subtitle={metaLine(item)}
                  onPress={() => handleTap(item)}
                />
              )}
              ListEmptyComponent={
                !loading ? (
                  <Text style={styles.emptyText}>
                    עדיין אין פרופילים להצגה. חזרו מאוחר יותר 🙂
                  </Text>
                ) : null
              }
              ListFooterComponent={
                loadingMore ? (
                  <ActivityIndicator style={styles.footerSpinner} color={theme.palette.primary} />
                ) : null
              }
            />
          )}

          <SecondaryButton text="חזור לתפריט הראשי" onPress={() => navigation.navigate('Menu')} />
        </View>
      </SafeAreaView>

      <BottomSheet
        ref={sheetRef}
        index={-1}
        snapPoints={snapPoints}
        enablePanDownToClose
        backdropComponent={renderBackdrop}
        backgroundStyle={styles.sheetBg}
        handleIndicatorStyle={styles.sheetHandle}
      >
        <BottomSheetView style={styles.sheetContent}>
          {selected && (
            <>
              <Text style={styles.sheetName}>{selected.name || clientMessage('unknown_user_label')}</Text>
              <Text style={styles.sheetMeta}>{metaLine(selected)}</Text>
              <Text style={styles.sheetPrompt}>מה תרצו לעשות?</Text>
              <PrimaryButton   text="צפייה בפרופיל שלו / שלה"  onPress={handleViewProfile} />
              <PrimaryButton   text="התחל שיחה / שלח הודעה"    onPress={handleStartChat}   />
              <SecondaryButton text={clientMessage('close_label')} onPress={() => sheetRef.current?.close()} />
            </>
          )}
        </BottomSheetView>
      </BottomSheet>
    </View>
  );
}

const styles = StyleSheet.create({
  root:      { flex: 1 },
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
  footerSpinner: { paddingVertical: theme.spacing.md },
  sheetBg:       { backgroundColor: theme.palette.surface },
  sheetHandle:   { backgroundColor: theme.palette.offline },
  sheetContent: {
    flex: 1,
    alignItems: 'center',
    paddingHorizontal: theme.spacing.lg,
    paddingBottom: theme.spacing.lg,
    gap: theme.spacing.md,
  },
  sheetName: {
    fontSize: theme.type.h2,
    fontWeight: 'bold',
    color: theme.palette.textMain,
    textAlign: 'center',
    fontFamily: theme.fontFamily,
  },
  sheetMeta: {
    fontSize: theme.type.body,
    color: theme.palette.secondary,
    textAlign: 'center',
    fontFamily: theme.fontFamily,
  },
  sheetPrompt: {
    fontSize: theme.type.body,
    fontWeight: '600',
    color: theme.palette.textMain,
    textAlign: 'center',
    fontFamily: theme.fontFamily,
  },
});
