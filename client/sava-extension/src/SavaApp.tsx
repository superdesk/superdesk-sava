import * as React from 'react';
import '@chatscope/chat-ui-kit-styles/dist/default/styles.min.css';
import './sava.css';
import {
    MainContainer,
    ChatContainer,
    ConversationHeader,
    MessageList,
    MessageInput,
} from '@chatscope/chat-ui-kit-react';

import {superdeskApi} from './superdeskApi';
import {sendCommand, ISavaPending, ISavaResult, SavaConversation} from './api';
import {IChatMessage, MessageRow} from './MessageRow';
import {PendingCard} from './PendingCard';
import {TypingRow} from './TypingRow';

const EXAMPLES: Array<string> = [
    'Show me the articles I have authored',
    'What\'s on the Default Desk right now?',
    'Create a planning item for today about the AI conference and add a text coverage',
];

export function SavaApp(_props: {setupFullWidthCapability: (config: any) => void}) {
    const {gettext} = superdeskApi.localization;
    const [messages, setMessages] = React.useState<Array<IChatMessage>>([]);
    const [conversation, setConversation] = React.useState<SavaConversation>([]);
    const [pending, setPending] = React.useState<ISavaPending | null>(null);
    const [loading, setLoading] = React.useState(false);
    const nextId = React.useRef(1);

    function applyResult(result: ISavaResult) {
        setConversation(result.conversation);
        if (result.reply || (result.actions != null && result.actions.length > 0)) {
            setMessages((prev) => prev.concat({
                id: nextId.current++,
                role: 'assistant',
                text: result.reply,
                actions: result.actions,
            }));
        }
        setPending(result.pending);
        setLoading(false);
    }

    function applyError(err: any) {
        setMessages((prev) => prev.concat({
            id: nextId.current++,
            role: 'assistant',
            error: true,
            text: (err && (err.message || err.error)) || gettext('Something went wrong talking to the agent.'),
        }));
        setPending(null);
        setLoading(false);
    }

    function submit(raw: string) {
        const prompt = (raw || '').trim();

        if (prompt.length === 0 || loading) {
            return;
        }

        setMessages((prev) => prev.concat({id: nextId.current++, role: 'user', text: prompt}));
        setPending(null);
        setLoading(true);
        sendCommand(prompt, conversation).then(applyResult, applyError);
    }

    function decide(approved: boolean) {
        if (pending == null || loading) {
            return;
        }

        const p = pending;

        // Reflect the choice in the thread for continuity.
        setMessages((prev) => prev.concat({
            id: nextId.current++,
            role: 'user',
            text: approved ? p.confirm_label : p.cancel_label,
        }));
        setPending(null);
        setLoading(true);
        sendCommand('', conversation, {id: p.id, approved: approved}).then(applyResult, applyError);
    }

    function resetChat() {
        if (loading) {
            return;
        }
        setMessages([]);
        setConversation([]);
        setPending(null);
    }

    const isEmpty = messages.length === 0 && pending == null && !loading;
    const rows: Array<React.ReactNode> = messages.map((m) => <MessageRow key={m.id} message={m} />);

    if (loading) {
        rows.push(<TypingRow key="typing" label={gettext('SAVA is working…')} />);
    } else if (pending != null) {
        rows.push(<PendingCard key="pending" pending={pending} onDecide={decide} />);
    }

    return (
        <div className="sava-root">
            <MainContainer>
                <ChatContainer>
                    <ConversationHeader>
                        <ConversationHeader.Content
                            userName="SAVA"
                            info={gettext('Ask me to do things in Superdesk')}
                        />
                        <ConversationHeader.Actions>
                            <button
                                className="btn btn--small"
                                onClick={resetChat}
                                disabled={loading || messages.length === 0}
                                title={gettext('Start a new chat')}
                            >
                                {gettext('New chat')}
                            </button>
                        </ConversationHeader.Actions>
                    </ConversationHeader>

                    <MessageList>
                        {isEmpty ? (
                            <div className="sava-empty">
                                <div className="sava-empty__mark"><i className="big-icon--general-ai" /></div>
                                <h1 className="sava-empty__title">{gettext('What would you like to do?')}</h1>
                                <p className="sava-empty__subtitle">
                                    {gettext('Describe it in plain language and SAVA will do it for you.')}
                                </p>
                                <div className="sava-suggestions">
                                    {EXAMPLES.map((ex, i) => (
                                        <button key={i} className="sava-suggestion" onClick={() => submit(ex)}>
                                            {ex}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ) : rows}
                    </MessageList>

                    <MessageInput
                        placeholder={pending != null ? gettext('Choose an option above…') : gettext('Message SAVA…')}
                        onSend={(_html: string, textContent: string) => submit(textContent)}
                        attachButton={false}
                        disabled={loading || pending != null}
                        autoFocus
                    />
                </ChatContainer>
            </MainContainer>
        </div>
    );
}
