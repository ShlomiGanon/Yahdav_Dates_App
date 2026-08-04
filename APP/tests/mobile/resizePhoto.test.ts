jest.mock('expo-image-manipulator', () => ({
  manipulateAsync: jest.fn(),
  SaveFormat: { JPEG: 'jpeg' },
}));

import * as ImageManipulator from 'expo-image-manipulator';
import { resizePhoto } from '../../mobile/src/utils/resizePhoto';

const manipulateAsyncMock = ImageManipulator.manipulateAsync as jest.Mock;

beforeEach(() =>
{
  manipulateAsyncMock.mockReset();
});

describe('resizePhoto', () =>
{
  it('returns the original uri unchanged when both dimensions are within the 1080px cap', async () =>
  {
    const uri = await resizePhoto('file://original.jpg', 800, 600);

    expect(uri).toBe('file://original.jpg');
    expect(manipulateAsyncMock).not.toHaveBeenCalled();
  });

  it('returns the original uri unchanged exactly at the 1080px boundary', async () =>
  {
    const uri = await resizePhoto('file://boundary.jpg', 1080, 500);

    expect(uri).toBe('file://boundary.jpg');
    expect(manipulateAsyncMock).not.toHaveBeenCalled();
  });

  it('resizes by width when the image is wider than it is tall and over the cap', async () =>
  {
    manipulateAsyncMock.mockResolvedValue({ uri: 'file://resized.jpg' });

    const uri = await resizePhoto('file://wide.jpg', 4000, 2000);

    expect(uri).toBe('file://resized.jpg');
    expect(manipulateAsyncMock).toHaveBeenCalledWith(
      'file://wide.jpg',
      [{ resize: { width: 1080 } }],
      expect.objectContaining({ compress: 0.8, format: 'jpeg' }),
    );
  });

  it('resizes by height when the image is taller than it is wide and over the cap', async () =>
  {
    manipulateAsyncMock.mockResolvedValue({ uri: 'file://resized-tall.jpg' });

    const uri = await resizePhoto('file://tall.jpg', 2000, 4000);

    expect(uri).toBe('file://resized-tall.jpg');
    expect(manipulateAsyncMock).toHaveBeenCalledWith(
      'file://tall.jpg',
      [{ resize: { height: 1080 } }],
      expect.anything(),
    );
  });

  it('resizes by width for a square image over the cap (width >= height branch)', async () =>
  {
    manipulateAsyncMock.mockResolvedValue({ uri: 'file://resized-square.jpg' });

    await resizePhoto('file://square.jpg', 2000, 2000);

    expect(manipulateAsyncMock).toHaveBeenCalledWith(
      'file://square.jpg',
      [{ resize: { width: 1080 } }],
      expect.anything(),
    );
  });

  it('propagates a manipulation failure as a rejected promise', async () =>
  {
    // resizePhoto itself correctly lets a manipulateAsync rejection
    // propagate — that part is fine and this confirms it stays that way.
    // The real gap from improve.md Mobile Medium #8 is one level up: its
    // callers (useMyProfile.ts / useMyPhotos.ts) don't wrap this call in a
    // try/catch before flipping `uploading` state, so a rejection here
    // becomes an unhandled promise rejection at the call site rather than a
    // caught, user-visible error. That's a hook-level fix, out of scope for
    // this pure-util test.
    manipulateAsyncMock.mockRejectedValue(new Error('corrupt image'));

    await expect(resizePhoto('file://corrupt.jpg', 4000, 4000)).rejects.toThrow('corrupt image');
  });
});
