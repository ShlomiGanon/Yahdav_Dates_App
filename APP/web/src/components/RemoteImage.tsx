import type { ImgHTMLAttributes } from 'react';
import { resolveMediaUrl } from '@shared/utils/resolveMediaUrl';
import { axiosClient } from '../api/client';

interface Props extends Omit<ImgHTMLAttributes<HTMLImageElement>, 'src'>
{
    src: string | null | undefined;
}

// The only place on web that turns a stored relative media path (a
// Profile.photo_url, a Photo.url, ...) into a real <img src>. Every photo
// render should go through this instead of a raw <img src={...}>, so
// "where do uploads live" can't silently drift per call site again (see
// shared/utils/resolveMediaUrl.ts for why the bare path never worked).
export function RemoteImage({ src, alt = '', ...rest }: Props)
{
    const resolved = resolveMediaUrl(src, axiosClient.defaults.baseURL ?? '');

    if (!resolved)
    {
        return null;
    }

    return <img src={resolved} alt={alt} {...rest} />;
}
