import React, { useCallback, useRef, useState } from 'react';
import { View, Text, StyleSheet, FlatList, Dimensions, ViewToken } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { usePeerPhotos } from '../../hooks/usePeerPhotos';
import { SecondaryButton } from '../../components/SecondaryButton';
import { ErrorCard } from '../../components/ErrorCard';
import { LoadingOverlay } from '../../components/LoadingOverlay';
import { RemoteImage } from '../../components/RemoteImage';
import type { MainStackParams } from '../../types/navigation';
import { theme } from '../../style/theme';
import { clientMessage } from '@shared/copy/client';

type Props = NativeStackScreenProps<MainStackParams, 'PeerPhotos'>;

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

export function PeerPhotosScreen({ route, navigation }: Props) {
  const { peer_id } = route.params;
  const insets = useSafeAreaInsets();

  const { photos, peerName, loading, loadError } = usePeerPhotos(peer_id);
  const [current, setCurrent] = useState(0);

  const onViewableItemsChanged = useRef(
    ({ viewableItems }: { viewableItems: ViewToken[] }) => {
      if (viewableItems.length > 0 && viewableItems[0].index != null) {
        setCurrent(viewableItems[0].index);
      }
    },
  ).current;

  const viewabilityConfig = useRef({ itemVisiblePercentThreshold: 51 }).current;

  const heading = peerName ? `התמונות של ${peerName}` : clientMessage('additional_photos_label');

  if (loadError) {
    return (
      <View style={[styles.fallback, { paddingTop: insets.top + theme.spacing.lg }]}>
        <ErrorCard message={loadError} />
        <SecondaryButton
          text={clientMessage('back_label')}
          onPress={() => navigation.navigate('PeerProfile', { peer_id })}
        />
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <LoadingOverlay visible={loading} />

      {!loading && photos.length === 0 ? (
        <View style={[styles.fallback, { paddingTop: insets.top + theme.spacing.lg }]}>
          <Text style={styles.emptyText}>אין תמונות להצגה.</Text>
          <SecondaryButton
            text={clientMessage('back_label')}
            onPress={() => navigation.navigate('PeerProfile', { peer_id })}
          />
        </View>
      ) : (
        <>
          <FlatList
            data={photos}
            horizontal
            pagingEnabled
            showsHorizontalScrollIndicator={false}
            keyExtractor={(item, index) => `${item.url}-${index}`}
            onViewableItemsChanged={onViewableItemsChanged}
            viewabilityConfig={viewabilityConfig}
            renderItem={({ item }) => (
              <View style={styles.page}>
                <RemoteImage uri={item.url} style={styles.photo} contentFit="contain" />
              </View>
            )}
          />

          <View
            style={[styles.topOverlay, { paddingTop: insets.top + theme.spacing.sm }]}
            pointerEvents="none"
          >
            <Text style={styles.headingText} numberOfLines={1}>{heading}</Text>
            {photos.length > 0 && (
              <Text style={styles.counterText}>{current + 1} / {photos.length}</Text>
            )}
          </View>

          <View style={[styles.bottomOverlay, { paddingBottom: insets.bottom + theme.spacing.md }]}>
            <SecondaryButton
              text={clientMessage('back_label')}
              onPress={() => navigation.navigate('PeerProfile', { peer_id })}
            />
          </View>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#000' },
  page: {
    width: SCREEN_WIDTH,
    height: SCREEN_HEIGHT,
    justifyContent: 'center',
    alignItems: 'center',
  },
  photo: { width: SCREEN_WIDTH, height: SCREEN_HEIGHT },
  topOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    paddingHorizontal: theme.spacing.lg,
    paddingBottom: theme.spacing.md,
    backgroundColor: 'rgba(0,0,0,0.45)',
    alignItems: 'center',
    gap: theme.spacing.xs,
  },
  headingText: {
    color: '#fff',
    fontSize: theme.type.heading,
    fontFamily: theme.fontFamily,
    fontWeight: '600',
    textAlign: 'center',
  },
  counterText: {
    color: 'rgba(255,255,255,0.75)',
    fontSize: theme.type.caption,
    fontFamily: theme.fontFamily,
  },
  bottomOverlay: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingHorizontal: theme.spacing.lg,
    paddingTop: theme.spacing.md,
    backgroundColor: 'rgba(0,0,0,0.45)',
    alignItems: 'center',
  },
  fallback: {
    flex: 1,
    backgroundColor: theme.palette.background,
    paddingHorizontal: theme.spacing.lg,
    gap: theme.spacing.lg,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: theme.type.body,
    color: theme.palette.offline,
    textAlign: 'center',
    fontFamily: theme.fontFamily,
  },
});
