import { ChatMasterDetail } from '../components/ChatMasterDetail';

// Same master-detail view as ChatPage — see ChatMasterDetail for why both
// PageIds render it. Here peer_id is simply absent, so the right pane
// shows the "pick a conversation" empty state.
export function ChatHistoryPage()
{
    return <ChatMasterDetail />;
}
