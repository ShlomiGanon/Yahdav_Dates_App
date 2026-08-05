import React from 'react';
import { Image } from 'expo-image';
import type { ImageProps } from 'expo-image';
import { resolveMediaUrl } from '@shared/utils/resolveMediaUrl';
import { api } from '../api/axios';

type Props = Omit<ImageProps, 'source'> & { uri: string | null | undefined };

// The only place on mobile that turns a stored relative media path (a
// Profile.photo_url, a Photo.url, ...) into a real Image source. Every
// photo render should go through this instead of a raw
// <Image source={{ uri: ... }}>, so "where do uploads live" can't
// silently drift per screen again (see shared/utils/resolveMediaUrl.ts
// for why the bare path never worked).
export function RemoteImage({ uri, ...rest }: Props) {
  const resolved = resolveMediaUrl(uri, api.defaults.baseURL ?? '');

  if (!resolved) {
    return null;
  }

  return <Image source={{ uri: resolved }} {...rest} />;
}
