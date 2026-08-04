import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { WelcomeScreen } from '../screens/welcome/WelcomeScreen';
import { LoginScreen }   from '../screens/login/LoginScreen';
import { SignupScreen }  from '../screens/signup/SignupScreen';
import type { AuthStackParams } from '../types/navigation';
import { SCREEN_NAMES } from './screenNames';

const Stack = createNativeStackNavigator<AuthStackParams>();

export function AuthStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false, contentStyle: { backgroundColor: 'transparent' }, animation: 'fade' }}>
      <Stack.Screen name={SCREEN_NAMES.welcome} component={WelcomeScreen} />
      <Stack.Screen name={SCREEN_NAMES.login}   component={LoginScreen}   />
      <Stack.Screen name={SCREEN_NAMES.signup}  component={SignupScreen}  />
    </Stack.Navigator>
  );
}
