import { createChatApi } from '@shared/api/chat';
import { api } from './axios';

// All four endpoints match shared/api/chat.ts's signatures exactly — no
// bridging needed. See APP/review.md finding 2.2.
export const chatApi = createChatApi(api);
