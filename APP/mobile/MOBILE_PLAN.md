# Mobile App Plan — React Native (Expo)

> **Status:** ✅ Fully Implemented (Phases 1–8)
> **Depends on:** `APP/MASTER_PLAN.md`, `APP/backend/BACKEND_PLAN.md`
> **Replaces:** `src/` (Flet desktop app — deleted ✅)

---

## 1. Overview

React Native / Expo mobile app for iOS and Android. Feature-for-feature replacement of the Flet app. Connects to the FastAPI backend via REST and WebSocket. Hebrew-first, RTL layout throughout.

---

## 2. Technology Stack

| Component | Choice |
|-----------|--------|
| Framework | React Native + Expo SDK 57 (managed workflow) |
| Language | TypeScript |
| Navigation | React Navigation v6 (`createNativeStackNavigator`) |
| HTTP | Axios (JWT auto-refresh interceptor) |
| WebSocket | Native WebSocket API + exponential-backoff reconnect |
| Token storage | Expo SecureStore |
| Push | `expo-notifications` (FCM + APNs via Expo) |
| Image picker | `expo-image-picker` |
| Image resize | `expo-image-manipulator` (cap longest side at 1080 px) |
| Bottom sheet | `@gorhom/bottom-sheet` v5 |
| Offline guard | `@react-native-community/netinfo` |
| RTL | `I18nManager.forceRTL(true)` |
| Dates | `date-fns` with `he` locale |
| State | React Context + custom hooks |

---

## 3. Locked Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Menu | **3-button screen** (MyProfile, Discover, ChatHistory) + logout — no tab bar |
| 2 | Discover UX | Member list + bottom sheet (`@gorhom/bottom-sheet`) |
| 3 | Dropdowns | `ModalPicker.tsx` — one custom component for all ~6 dropdowns |
| 4 | Font | System default; `theme.fontFamily = undefined`; swap in one line |
| 5 | Block button | "⋯" header on `PeerProfileScreen` → `Alert.alert` → "חסום משתמש" |
| 6 | Offline | `NetworkGuard.tsx` global overlay wrapping entire app |
| 7 | Chat order | Newest messages at **top**, oldest at bottom (reversed data array, no `inverted` prop) |
| 8 | Photo limit | Max 4 additional photos; add button disabled at limit |
| 9 | Photo gallery | `PeerPhotosScreen` = horizontal `FlatList pagingEnabled` fullscreen swipe |

---

## 4. Folder Structure

```
mobile/src/
├── main.tsx                      # entry — RTL setup, GestureHandlerRootView, render app
│
├── api/
│   ├── axios.ts                  # Axios instance + JWT interceptor + auto-refresh
│   ├── users.ts                  # usersApi — all /users/* calls
│   └── chat.ts                   # chatApi  — all /chat/* calls
│
├── auth/
│   ├── AuthContext.tsx           # user state + login/logout (incl. push token cleanup)
│   ├── storage.ts                # Expo SecureStore wrappers + in-memory access token
│   └── useAutoLogin.ts           # boot-time token rehydration
│
├── navigation/
│   ├── RootNavigator.tsx         # auth vs main stack; notification tap listener
│   ├── navigationRef.ts          # NavigationContainerRef for use outside React
│   ├── AuthStack.tsx             # Welcome → Login → Signup (animation: fade)
│   └── MainStack.tsx             # Menu + all protected screens (animation: slide_from_right)
│
├── screens/
│   ├── welcome/WelcomeScreen.tsx
│   ├── login/LoginScreen.tsx
│   ├── signup/SignupScreen.tsx
│   ├── menu/MenuScreen.tsx
│   ├── profile/
│   │   ├── MyProfileScreen.tsx
│   │   └── AdditionalPhotosScreen.tsx
│   ├── discover/DiscoverScreen.tsx
│   ├── peer/
│   │   ├── PeerProfileScreen.tsx
│   │   └── PeerPhotosScreen.tsx
│   └── chat/
│       ├── ChatHistoryScreen.tsx
│       └── ChatScreen.tsx
│
├── hooks/
│   ├── useMyProfile.ts           # load + save profile + upload main photo
│   ├── useMyPhotos.ts            # load / add / remove additional photos
│   ├── useCandidates.ts          # paginated discover list
│   ├── usePeerProfile.ts         # load peer + block action
│   ├── usePeerPhotos.ts          # load peer's photo gallery
│   ├── useConversations.ts       # conversation list + WS refresh + reconnect
│   ├── useMessages.ts            # messages + WS + reconnect + pagination + optimistic send
│   ├── usePushToken.ts           # register push token after login
│
├── notifications/
│   ├── setup.ts                  # request permission + register token (via usersApi)
│   └── usePushToken.ts           # hook that calls setup when user is available
│
├── components/
│   ├── PrimaryButton.tsx         # Animated scale press; disabled + loading props
│   ├── SecondaryButton.tsx       # Animated scale press
│   ├── HebrewInput.tsx           # RTL TextInput; label + error
│   ├── ModalPicker.tsx           # Pressable → Modal → FlatList options
│   ├── NetworkGuard.tsx          # offline overlay
│   ├── Avatar.tsx                # expo-image; initials fallback
│   ├── UnreadBadge.tsx           # red circle with count
│   ├── MemberRow.tsx             # Avatar + name/subtitle + timestamp + trailing slot
│   ├── ChatBubble.tsx            # RTL-safe alignSelf bubble
│   ├── PhotoTile.tsx             # image tile; optional remove button
│   ├── StatusBanner.tsx          # imperative showStatus(msg, ok) via ref
│   ├── LoadingOverlay.tsx        # transparent Modal + ActivityIndicator
│   ├── ScreenHeading.tsx
│   ├── ErrorCard.tsx
│   └── Divider.tsx
│
├── utils/
│   ├── constants.ts              # WS_RECONNECT config (delays, max attempts)
│   ├── formatDate.ts             # formatMessageTime / formatConversationTime (date-fns he)
│   └── resizePhoto.ts            # cap longest side at 1080 px via expo-image-manipulator
│
├── style/theme.ts                # design tokens
│
└── types/
    ├── navigation.ts             # AuthStackParams, MainStackParams
    ├── user.ts                   # Profile, Photo, Candidate, PeerProfile
    └── chat.ts                   # Message, Conversation
```

---

## 5. Navigation Structure

```
RootNavigator
│   ├─ notification tap listener (addNotificationResponseReceivedListener)
│   └─ cold-start tap handler    (getLastNotificationResponseAsync)
│
├── AuthStack          (animation: fade)
│   ├── Welcome
│   ├── Login
│   └── Signup
│
└── MainStack          (animation: slide_from_right)
    ├── Menu
    ├── MyProfile
    ├── AdditionalPhotos
    ├── Discover
    ├── PeerProfile      { peer_id: string }
    ├── PeerPhotos       { peer_id: string }
    ├── ChatHistory
    └── Chat             { peer_id: string, peer_name: string }
```

**Boot flow** (`useAutoLogin.ts`):
```
read SecureStore for refresh_token
  found  → POST /auth/refresh → success → save tokens → show MainStack
  missing or expired → clear storage → show AuthStack
```

**Static background:** `View` with `theme.palette.background` at `RootNavigator` level — all screen cards render on top. Replace with `ImageBackground` when BG asset is ready.

**Deep linking:**
- URL scheme `yahdav://` in `app.json`
- `navigationRef.ts` exposes `navigateToChat(peer_id, peer_name)` for use outside React
- Notification tap reads `data.peer_id` + `data.peer_name` from push payload → `navigateToChat`

---

## 6. Design System

`style/theme.ts` mirrors `src/style/design_system.py`. All components import from here — no inline magic numbers.

```ts
theme = {
  fontFamily: undefined,    // system default; to swap: set name here + expo-font in main.tsx

  palette: {
    primary:    "#C0392B",   secondary: "#2C3E50",  background: "#1A1A2E",
    surface:    "#FFFFFF",   textMain:  "#2C3E50",   danger:    "#E74C3C",
    success:    "#27AE60",   online:    "#2ECC71",   offline:   "#BDC3C7",
    selfBubble: "#27AE60",   peerBubble:"#ECF0F1",
  },
  type:    { h1:50, h2:28, heading:24, button:22, body:16, input:20, small:14, caption:12 },
  sizing:  { buttonWidth:400, buttonHeight:70, avatarSm:40, avatarLg:80 },
  spacing: { none:0, xs:4, sm:8, md:14, lg:24 },
  radius:  { card:16, bubble:18 },
  motion:  { animMs:240 },
  opacity: { formOverlay:0.85, hover:0.8 },
}
```

---

## 7. Component Library

| Component | Notes |
|-----------|-------|
| `PrimaryButton` | `Animated.spring` scale 0.96 on press; `disabled` + `loading` props |
| `SecondaryButton` | Same press animation |
| `HebrewInput` | `textAlign:'right'`, `writingDirection:'rtl'`; label + multiline support |
| `ModalPicker` | Pressable → bottom Modal → `FlatList` options; used for all dropdowns |
| `Avatar` | `expo-image`; initials fallback circle |
| `UnreadBadge` | Red circle with count |
| `MemberRow` | Avatar + name/subtitle + optional `timestamp` (top-right) + `trailing` slot (badge) |
| `ChatBubble` | `alignSelf: flex-end/start` — RTL-safe |
| `PhotoTile` | `expo-image` tile; optional `showRemove` × button |
| `StatusBanner` | Imperative `showStatus(msg, ok)` via forwarded ref |
| `LoadingOverlay` | Transparent `Modal` + `ActivityIndicator` |
| `NetworkGuard` | Wraps root; Hebrew "אין חיבור לאינטרנט" overlay when offline |

---

## 8. API Modules

All screens go through typed API objects — no screen calls `api.get/post` directly.

### `api/users.ts` — `usersApi`
| Function | Endpoint |
|----------|----------|
| `getMyProfile()` | `GET /users/me` |
| `updateMyProfile(data)` | `PUT /users/me` |
| `uploadMainPhoto(form)` | `POST /users/me/photo` |
| `getMyPhotos()` | `GET /users/me/photos` |
| `uploadPhoto(form)` | `POST /users/me/photos` |
| `deletePhoto(id)` | `DELETE /users/me/photos/:id` |
| `discoverCandidates(page, limit)` | `GET /users/discover?page=&limit=` |
| `getPeerProfile(peer_id)` | `GET /users/:peer_id` |
| `blockUser(peer_id)` | `POST /users/:peer_id/block` |
| `getPeerPhotos(peer_id)` | `GET /users/:peer_id/photos` |
| `registerPushToken(token, platform)` | `POST /users/me/push-token` |
| `unregisterPushToken()` | `DELETE /users/me/push-token` |

### `api/chat.ts` — `chatApi`
| Function | Endpoint |
|----------|----------|
| `getConversations()` | `GET /chat/conversations` |
| `getMessages(peer_id, params)` | `GET /chat/:peer_id?limit=&before=` |
| `sendMessage(peer_id, content, type)` | `POST /chat/:peer_id` |
| `markRead(peer_id)` | `PUT /chat/:peer_id/read` |

---

## 9. Screen Inventory

| Screen | Hook | Key Behavior |
|--------|------|--------------|
| `WelcomeScreen` | — | Two nav buttons |
| `LoginScreen` | — | Email/password → tokens → MainStack |
| `SignupScreen` | — | Email/password/confirm → Login |
| `MenuScreen` | — | 3 nav buttons + logout (logout also unregisters push token) |
| `MyProfileScreen` | `useMyProfile` | Load/edit/save; DOB = 3 ModalPickers; main photo via image picker + resize |
| `AdditionalPhotosScreen` | `useMyPhotos` | 3-col grid; add (max 4, button disabled at limit); remove with Alert confirm |
| `DiscoverScreen` | `useCandidates` | Paginated list (20/page); bottom sheet on tap; load-more on scroll |
| `PeerProfileScreen` | `usePeerProfile` | Read-only view; "⋯" → block confirm → navigate to Discover |
| `PeerPhotosScreen` | `usePeerPhotos` | Fullscreen horizontal swipe gallery (`FlatList pagingEnabled`); counter overlay |
| `ChatHistoryScreen` | `useConversations` | Thread list; pull-to-refresh; auto-refresh on WS message; unread badge + timestamp |
| `ChatScreen` | `useMessages` | Newest at top; WS real-time; optimistic send; load-older pagination on scroll |

---

## 10. Chat Implementation

### WebSocket (`useMessages` / `useConversations`)
```
on mount:
  open WS: ws://host/ws?token=<access_token>
  onopen  → reset reconnect delay + count
  onclose → schedule reconnect with exponential backoff (1s → 2s → 4s … 30s max, 10 attempts)

on unmount:
  set unmounted flag → cancel pending timer → close WS

reconnect constants (src/utils/constants.ts):
  INITIAL_DELAY_MS: 1000
  MAX_DELAY_MS:     30000
  BACKOFF_FACTOR:   2
  MAX_ATTEMPTS:     10
```

### ChatScreen message order
```
API returns: [oldest … newest]  (chronological)
Stored as:   [newest … oldest]  (reversed on load)
  → messages[0] = newest = visual top
  → messages[last] = oldest = visual bottom
  → new WS messages  → prepend to index 0
  → optimistic send  → prepend to index 0
  → onEndReached     → load older (before = messages[last].message_id)
```

### Pagination
- **Discover:** `GET /users/discover?page=X&limit=20` — `onEndReached` appends next page
- **Chat:** `GET /chat/:id?limit=20` initial; `?before=<oldest_id>&limit=20` on scroll to bottom

### Push Notifications
```
on login:
  requestPermissionsAsync
  → getExpoPushTokenAsync
  → POST /users/me/push-token { token, platform }

on logout:
  DELETE /users/me/push-token   (parallel with POST /auth/logout)

on notification tap:
  RootNavigator reads data.peer_id + data.peer_name
  → navigateToChat(peer_id, peer_name) via navigationRef
  handles: foreground tap, background tap, cold-start tap
```

---

## 11. Photo Handling

- **Pick:** `expo-image-picker` (quality: 0.8)
- **Resize:** `resizePhoto(uri, w, h)` — if longest side > 1080 px, `expo-image-manipulator` resizes before upload
- **Upload:** `FormData` multipart → `POST /users/me/photo` (main) or `/users/me/photos` (extra)
- **Limit:** max 4 additional photos; button label changes + `disabled` prop set at limit
- **Delete:** `Alert.alert` confirmation → `DELETE /users/me/photos/:id`
- **Peer gallery:** `PeerPhotosScreen` — horizontal `FlatList pagingEnabled`; black bg; `expo-image contentFit="contain"`; counter overlay; safe-area aware

---

## 12. RTL & Hebrew

- `I18nManager.forceRTL(true)` called once in `main.tsx` before any render
- All `TextInput`: `textAlign:'right'`, `writingDirection:'rtl'`
- Chat bubbles: `alignSelf: flex-end/start` — immune to RTL axis flip
- Message order: newest at top (reversed array — NOT `inverted` FlatList)
- Dates: `date-fns` with `he` locale
  - `formatMessageTime(iso)` → `HH:mm` (chat bubbles)
  - `formatConversationTime(iso)` → "עכשיו" / "לפני X דקות" / "אתמול" / "dd/MM"
- `MemberRow` shows conversation `timestamp` above the unread badge

---

## 13. Flet → RN Concept Mapping

### Layout Primitives

| Flet | React Native |
|------|-------------|
| `ft.Column` | `View` with `flexDirection:'column'` |
| `ft.Row` | `View` with `flexDirection:'row'` |
| `ft.Container` | `View` (static) or `Pressable` (tappable) |
| `ft.ListView` | `FlatList` |
| `ft.ScrollView` | `ScrollView` |
| `ft.Hero` (background) | `View` with background color at RootNavigator level |
| `expand=True` | `flex: 1` |

### Interactive Controls

| Flet | React Native |
|------|-------------|
| `ft.ElevatedButton` | `PrimaryButton.tsx` |
| `ft.OutlinedButton` | `SecondaryButton.tsx` |
| `ft.TextField` | `HebrewInput.tsx` |
| `ft.Dropdown` | `ModalPicker.tsx` |
| `ft.FilePicker` | `expo-image-picker` |
| `ft.ProgressRing` | `ActivityIndicator` |
| `ft.AlertDialog` | `Alert.alert()` |
| `ft.BottomSheet` | `@gorhom/bottom-sheet` |

### Services & State

| Flet | React Native |
|------|-------------|
| `IAuthService` | `api/axios.ts` + `AuthContext` |
| `IProfileRepository` | `api/users.ts` + `useMyProfile` |
| `IMessagingService` | `api/chat.ts` + `useMessages` |
| `IStorageService` | `api/users.ts` (server handles storage) |
| `page.session.store[CURRENT_USER_ID]` | `AuthContext.user.user_id` |
| `page.session.store[SELECTED_PEER_ID]` | Route param `peer_id` |
| `local_storage.py` (remember-me) | `auth/storage.ts` (Expo SecureStore) |
| `boot_resolver.py` | `auth/useAutoLogin.ts` |
| `router.py` | `navigation/RootNavigator.tsx` |

---

## 14. Phased Build Order

### Phase 1 — Foundation ✅ COMPLETED
1. ✅ Expo project init + TypeScript config
2. ✅ `I18nManager.forceRTL(true)` in `main.tsx`
3. ✅ `style/theme.ts` (design system)
4. ✅ `api/axios.ts` (Axios instance + JWT interceptor)
5. ✅ `AuthContext.tsx` + `auth/storage.ts`
6. ✅ `navigation/RootNavigator.tsx` + empty `AuthStack` + `MainStack`
7. ✅ `NetworkGuard.tsx` — offline overlay

### Phase 2 — Shared Components ✅ COMPLETED
8. ✅ `PrimaryButton`, `SecondaryButton`
9. ✅ `HebrewInput`
10. ✅ `ModalPicker`
11. ✅ `ScreenHeading`, `ErrorCard`, `StatusBanner`, `LoadingOverlay`
12. ✅ `Avatar`, `UnreadBadge`
13. ✅ `MemberRow`, `ChatBubble`, `PhotoTile`

### Phase 3 — Auth Flow ✅ COMPLETED
14. ✅ `WelcomeScreen`
15. ✅ `LoginScreen` → `POST /auth/login`
16. ✅ `SignupScreen` → `POST /auth/signup`
17. ✅ `useAutoLogin.ts` (boot token rehydration)

### Phase 4 — Menu + Profile ✅ COMPLETED
18. ✅ `MenuScreen` (3 nav buttons + logout)
19. ✅ `MyProfileScreen` (load + edit + save + main photo)
20. ✅ `AdditionalPhotosScreen` (add/remove extras)

### Phase 5 — Discover ✅ COMPLETED
21. ✅ `DiscoverScreen` (list + `@gorhom/bottom-sheet` action sheet)
22. ✅ `PeerProfileScreen` (read-only + block via Alert)
23. ✅ `PeerPhotosScreen` (fullscreen horizontal swipe gallery)

### Phase 6 — Messaging ✅ COMPLETED
24. ✅ `ChatHistoryScreen` (conversation list + unread badges + preview)
25. ✅ `ChatScreen` (WebSocket + optimistic send + REST fallback)
26. ✅ `notifications/setup.ts` + `usePushToken.ts`

### Phase 7 — Polish ✅ COMPLETED
27. ✅ Screen transition animations (fade / slide_from_right)
28. ✅ Button press animations (`Animated.spring` scale 0.96)
29. ✅ Keyboard avoidance (`KeyboardAvoidingView`; Android `softwareKeyboardLayoutMode: resize`)
30. ✅ RTL visual review — verify on first device run
31. ✅ Network-off testing — `NetworkGuard` in place; verify on first device run

### Phase 8 — Hardening & Features ✅ COMPLETED
32. ✅ `PeerPhotosScreen` rewritten as fullscreen horizontal swipe gallery (pagingEnabled FlatList)
33. ✅ Delete photo confirmation (`Alert.alert` with destructive button)
34. ✅ Max 4 additional photos — button disabled + label updated at limit
35. ✅ Push token unregistration on logout (`DELETE /users/me/push-token`)
36. ✅ Pull-to-refresh in `ChatHistoryScreen` (`RefreshControl`)
37. ✅ `ChatHistoryScreen` auto-refreshes on WS message (conversation list stays live)
38. ✅ Chat message order: newest at top (reversed array, no `inverted` prop)
39. ✅ Pagination — Discover (`page` param) + Chat (`before` cursor)
40. ✅ WebSocket exponential-backoff reconnect (constants in `utils/constants.ts`)
41. ✅ Deep linking + notification tap → `ChatScreen` (foreground, background, cold-start)
42. ✅ `date-fns` Hebrew locale — `formatMessageTime` + `formatConversationTime`
43. ✅ `MemberRow` timestamp slot — conversation list shows friendly relative time
44. ✅ Photo upload capped at 1080 px (`expo-image-manipulator`)
45. ✅ Domain API modules (`api/users.ts`, `api/chat.ts`) — no screen touches `api` directly
46. ✅ Shared type files (`types/user.ts`, `types/chat.ts`)
47. ✅ Custom hooks for all data logic (`hooks/use*.ts`) — screens are pure UI

---

## 15. Dev Setup

```bash
cd APP/mobile
npm install
npx expo start          # Expo Go QR code
npx expo run:android    # Android (requires Android Studio)
npx expo run:ios        # iOS (requires macOS + Xcode)
```

Environment (`.env` or `app.json` extra):
```
EXPO_PUBLIC_API_BASE_URL=http://localhost:3000    # dev
EXPO_PUBLIC_API_BASE_URL=https://api.yahdav.app  # prod
```

Required Babel plugin (`babel.config.js`):
```js
plugins: ['react-native-reanimated/plugin']  // required by @gorhom/bottom-sheet
```
