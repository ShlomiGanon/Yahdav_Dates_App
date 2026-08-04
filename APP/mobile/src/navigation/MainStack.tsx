import React from 'react';
import { View, Text } from 'react-native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { MenuScreen }             from '../screens/menu/MenuScreen';
import { ProfileScreen }          from '../screens/profile/ProfileScreen';
import { AdditionalPhotosScreen } from '../screens/profile/AdditionalPhotosScreen';
import { DiscoverScreen }         from '../screens/discover/DiscoverScreen';
import { PeerProfileScreen }      from '../screens/peer/PeerProfileScreen';
import { PeerPhotosScreen }       from '../screens/peer/PeerPhotosScreen';
import { ChatHistoryScreen }      from '../screens/chat/ChatHistoryScreen';
import { ChatScreen }             from '../screens/chat/ChatScreen';
import type { MainStackParams } from '../types/navigation';
import { SCREEN_NAMES } from './screenNames';

const Stack = createNativeStackNavigator<MainStackParams>();

export function MainStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: 'transparent' },
        animation: 'slide_from_right',
      }}
    >
      <Stack.Screen name={SCREEN_NAMES.menu}             component={MenuScreen}             />
      <Stack.Screen name={SCREEN_NAMES.profile}          component={ProfileScreen}          />
      <Stack.Screen name={SCREEN_NAMES.additionalPhotos} component={AdditionalPhotosScreen} />
      <Stack.Screen name={SCREEN_NAMES.discover}         component={DiscoverScreen}         />
      <Stack.Screen name={SCREEN_NAMES.peerProfile}      component={PeerProfileScreen}      />
      <Stack.Screen name={SCREEN_NAMES.peerPhotos}       component={PeerPhotosScreen}       />
      <Stack.Screen name={SCREEN_NAMES.chatHistory}      component={ChatHistoryScreen}      />
      <Stack.Screen name={SCREEN_NAMES.chat}             component={ChatScreen}             />
    </Stack.Navigator>
  );
}
