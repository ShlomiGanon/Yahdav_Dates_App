import { formatMessageTime } from '@shared/utils/formatDate';

interface Props
{
    content:    string;
    created_at: string;
    isSelf:     boolean;
}

export function ChatBubble({ content, created_at, isSelf }: Props)
{
    const alignment = isSelf ? 'items-end' : 'items-start';
    const colour    = isSelf
        ? 'bg-self-bubble text-white'
        : 'bg-peer-bubble text-secondary';

    return (
        <div className={`flex flex-col ${alignment} mb-2`}>
            <div className={`max-w-xs px-4 py-2 rounded-bubble ${colour}`}>
                <p className="text-base">{content}</p>
            </div>
            <span className="text-xs text-gray-400 mt-1">
                {formatMessageTime(created_at)}
            </span>
        </div>
    );
}
