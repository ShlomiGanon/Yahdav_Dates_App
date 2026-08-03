import React, { useRef } from 'react';
import { View, StyleSheet, SafeAreaView, FlatList, Dimensions } from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useMyPhotos } from '../../hooks/useMyPhotos';
import { ScreenHeading } from '../../components/ScreenHeading';
import { PhotoTile } from '../../components/PhotoTile';
import { PrimaryButton } from '../../components/PrimaryButton';
import { SecondaryButton } from '../../components/SecondaryButton';
import { StatusBanner, StatusBannerRef } from '../../components/StatusBanner';
import { LoadingOverlay } from '../../components/LoadingOverlay';
import type { MainStackParams } from '../../types/navigation';
import { theme } from '../../style/theme';

type Props = NativeStackScreenProps<MainStackParams, 'AdditionalPhotos'>;

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const COLS         = 3;
const TILE_GAP     = theme.spacing.sm;
const TILE_PADDING = theme.spacing.lg;
const TILE_SIZE    = Math.floor((SCREEN_WIDTH - TILE_PADDING * 2 - TILE_GAP * (COLS - 1)) / COLS);

export function AdditionalPhotosScreen({ navigation }: Props) {
  const bannerRef = useRef<StatusBannerRef>(null);

  const { photos, loading, uploading, addPhoto, removePhoto } =
    useMyPhotos((msg, ok) => bannerRef.current?.showStatus(msg, ok));

  return (
    <SafeAreaView style={styles.safe}>
      <LoadingOverlay visible={loading || uploading} />
      <View style={styles.container}>
        <ScreenHeading>תמונות נוספות</ScreenHeading>
        <StatusBanner ref={bannerRef} />

        <FlatList
          data={photos}
          keyExtractor={(item) => item.photo_id}
          numColumns={COLS}
          contentContainerStyle={styles.grid}
          columnWrapperStyle={styles.row}
          renderItem={({ item }) => (
            <PhotoTile
              uri={item.url}
              size={TILE_SIZE}
              showRemove
              onRemove={() => removePhoto(item.photo_id)}
            />
          )}
          ListEmptyComponent={!loading ? <View /> : null}
        />

        <View style={styles.actions}>
          <PrimaryButton
            text={photos.length >= 4 ? 'הגעת למקסימום תמונות' : 'הוסף תמונה'}
            onPress={addPhoto}
            loading={uploading}
            disabled={photos.length >= 4}
          />
          <SecondaryButton text="חזור לפרופיל שלי" onPress={() => navigation.navigate('MyProfile')} />
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe:      { flex: 1 },
  container: { flex: 1, padding: theme.spacing.lg, gap: theme.spacing.md },
  grid:      { gap: TILE_GAP },
  row:       { gap: TILE_GAP },
  actions:   { alignItems: 'center', gap: theme.spacing.md },
});
