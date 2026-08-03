import React from 'react';
import { View, Text } from 'react-native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { MenuScreen }             from '../screens/menu/MenuScreen';
import { MyProfileScreen }        from '../screens/profile/MyProfileScreen';
import { AdditionalPhotosScreen } from '../screens/profile/AdditionalPhotosScreen';
import { DiscoverScreen }         from '../screens/discover/DiscoverScreen';
import { PeerProfileScreen }      from '../screens/peer/PeerProfileScreen';
import { PeerPhotosScreen }       from '../screens/peer/PeerPhotosScreen';
import { ChatHistoryScreen }      from '../screens/chat/ChatHistoryScreen';
import { ChatScreen }             from '../screens/chat/ChatScreen';
import type { MainStackParams } from '../types/navigation';

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
      <Stack.Screen name="Menu"             component={MenuScreen}             />
      <Stack.Screen name="MyProfile"        component={MyProfileScreen}        />
      <Stack.Screen name="AdditionalPhotos" component={AdditionalPhotosScreen} />
      <Stack.Screen name="Discover"         component={DiscoverScreen}         />
      <Stack.Screen name="PeerProfile"      component={PeerProfileScreen}      />
      <Stack.Screen name="PeerPhotos"       component={PeerPhotosScreen}       />
      <Stack.Screen name="ChatHistory"      component={ChatHistoryScreen}      />
      <Stack.Screen name="Chat"             component={ChatScreen}             />
    </Stack.Navigator>
  );
}
