import * as React from 'react';
import '@chatscope/chat-ui-kit-styles/dist/default/styles.min.css';
import './sava.css';
import {
    MainContainer,
    ChatContainer,
    ConversationHeader,
    MessageList,
    MessageInput,
    TypingIndicator,
} from '@chatscope/chat-ui-kit-react';

import {superdeskApi} from './superdeskApi';
import {sendCommand, ISavaAction, SavaConversation} from './api';

const EXAMPLES: Array<string> = [
    'Create a text article with a headline and slugline and publish',
    'Show me all the articles that were authored by XYZ',
    "Create a planning item for today with the topic 'AI conference' and add an image coverage to it",
];

interface IChatMessage {
    id: number;
    role: 'user' | 'assistant';
    text: string;
    actions?: Array<ISavaAction>;
    error?: boolean;
}

/** Tool calls rendered as a vertical activity log, one per line. */
function ActivityLog({actions}: {actions: Array<ISavaAction>}) {
    return (
        <div className="sava-actions">
            {actions.map((a, i) => (
                <div className="sava-action" key={i} title={a.detail || ''}>
                    <span className={'sava-action__icon ' + (a.ok ? 'is-ok' : 'is-fail')}>
                        {a.ok ? '✓' : '✕'}
                    </span>
                    <code className="sava-action__tool">{a.tool}</code>
                    <span className="sava-action__summary">{a.summary}</span>
                </div>
            ))}
        </div>
    );
}

export function SavaApp(_props: {setupFullWidthCapability: (config: any) => void}) {
    const {gettext} = superdeskApi.localization;
    const [messages, setMessages] = React.useState<Array<IChatMessage>>([]);
    const [conversation, setConversation] = React.useState<SavaConversation>([]);
    const [loading, setLoading] = React.useState(false);
    const nextId = React.useRef(1);

    const submit = React.useCallback((raw: string) => {
        const prompt = (raw || '').trim();

        if (prompt.length === 0 || loading) {
            return;
        }

        const userMsg: IChatMessage = {id: nextId.current++, role: 'user', text: prompt};
        setMessages((prev) => prev.concat(userMsg));
        setLoading(true);

        sendCommand(prompt, conversation).then(
            (result) => {
                setConversation(result.conversation);
                setMessages((prev) => prev.concat({
                    id: nextId.current++,
                    role: 'assistant',
                    text: result.reply,
                    actions: result.actions,
                }));
                setLoading(false);
            },
            (err) => {
                setMessages((prev) => prev.concat({
                    id: nextId.current++,
                    role: 'assistant',
                    error: true,
                    text: (err && (err.message || err.error)) || gettext('Something went wrong talking to the agent.'),
                }));
                setLoading(false);
            },
        );
    }, [loading, conversation, gettext]);

    const resetChat = React.useCallback(() => {
        if (loading) {
            return;
        }
        setMessages([]);
        setConversation([]);
    }, [loading]);

    const isEmpty = messages.length === 0;

    return (
        <div className="sava-root">
            <MainContainer>
                <ChatContainer>
                    <ConversationHeader>
                        <ConversationHeader.Content userName="SAVA" info={gettext('Ask me to do things in Superdesk')} />
                        <ConversationHeader.Actions>
                            <button
                                className="btn btn--small"
                                onClick={resetChat}
                                disabled={loading || isEmpty}
                                title={gettext('Start a new chat')}
                            >
                                {gettext('New chat')}
                            </button>
                        </ConversationHeader.Actions>
                    </ConversationHeader>

                    <MessageList
                        typingIndicator={
                            loading ? <TypingIndicator content={gettext('SAVA is working…')} /> : undefined
                        }
                    >
                        {isEmpty ? (
                            <div className="sava-empty">
                                <div className="sava-empty__mark"><i className="icon--general-ai" /></div>
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
                        ) : (
                            messages.map((m) => (
                                m.role === 'user' ? (
                                    <div className="sava-row sava-row--user" key={m.id}>
                                        <div className="sava-bubble sava-bubble--user">
                                            <div className="sava-text">{m.text}</div>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="sava-row sava-row--assistant" key={m.id}>
                                        <div className="sava-avatar"><i className="icon--general-ai" /></div>
                                        <div className="sava-bubble sava-bubble--assistant">
                                            <div className="sava-text" data-error={m.error ? 'true' : 'false'}>
                                                {m.text}
                                            </div>
                                            {m.actions != null && m.actions.length > 0 && (
                                                <ActivityLog actions={m.actions} />
                                            )}
                                        </div>
                                    </div>
                                )
                            ))
                        )}
                    </MessageList>

                    <MessageInput
                        placeholder={gettext('Message SAVA…')}
                        onSend={(_html: string, textContent: string) => submit(textContent)}
                        attachButton={false}
                        disabled={loading}
                        autoFocus
                    />
                </ChatContainer>
            </MainContainer>
        </div>
    );
}
