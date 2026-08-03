import { createNavigationContainerRef } from '@react-navigation/native';
import type { MainStackParams } from '../types/navigation';

export const navigationRef = createNavigationContainerRef<MainStackParams>();

export function navigateToChat(peer_id: string, peer_name: string): void {
  if (navigationRef.isReady()) {
    navigationRef.navigate('Chat', { peer_id, peer_name });
  }
}
