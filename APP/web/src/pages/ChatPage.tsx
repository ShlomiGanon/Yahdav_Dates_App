import { ChatMasterDetail } from '../components/ChatMasterDetail';

// Same master-detail view as ChatHistoryPage — see ChatMasterDetail for why
// both PageIds render it. Here peer_id comes from the route, so the right
// pane opens straight to that conversation.
export function ChatPage()
{
    return <ChatMasterDetail />;
}
