import * as ImageManipulator from 'expo-image-manipulator';

const MAX_PX = 1080;

export async function resizePhoto(uri: string, width: number, height: number): Promise<string> {
  const longest = Math.max(width, height);
  if (longest <= MAX_PX) return uri;
  const action: ImageManipulator.Action =
    width >= height ? { resize: { width: MAX_PX } } : { resize: { height: MAX_PX } };
  const result = await ImageManipulator.manipulateAsync(uri, [action], {
    compress: 0.8,
    format: ImageManipulator.SaveFormat.JPEG,
  });
  return result.uri;
}
