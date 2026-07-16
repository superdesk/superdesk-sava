import * as React from 'react';
import '@chatscope/chat-ui-kit-styles/dist/default/styles.min.css';
import './sava.css';
import {
    MainContainer,
    ChatContainer,
    ConversationHeader,
    MessageList,
    Message,
    MessageInput,
    TypingIndicator,
} from '@chatscope/chat-ui-kit-react';

import {superdeskApi} from './superdeskApi';
import {sendCommand, ISavaAction} from './api';

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

function ActionChips({actions}: {actions: Array<ISavaAction>}) {
    return (
        <div style={{display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8}}>
            {actions.map((a, i) => (
                <span
                    key={i}
                    title={a.detail || ''}
                    style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        padding: '3px 10px', borderRadius: 12, fontSize: 12,
                        background: a.ok ? 'rgba(46,125,50,0.12)' : 'rgba(198,40,40,0.12)',
                        color: a.ok ? '#2e7d32' : '#c62828',
                        border: `1px solid ${a.ok ? 'rgba(46,125,50,0.35)' : 'rgba(198,40,40,0.35)'}`,
                    }}
                >
                    <span>{a.ok ? '✓' : '✕'}</span>
                    <code style={{background: 'transparent'}}>{a.tool}</code>
                    <span>{a.summary}</span>
                </span>
            ))}
        </div>
    );
}

export function SavaApp(_props: {setupFullWidthCapability: (config: any) => void}) {
    const {gettext} = superdeskApi.localization;
    const [messages, setMessages] = React.useState<Array<IChatMessage>>([]);
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

        sendCommand(prompt).then(
            (result) => {
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
    }, [loading, gettext]);

    const isEmpty = messages.length === 0;

    return (
        <div className="sava-root">
            <MainContainer>
                <ChatContainer>
                    <ConversationHeader>
                        <ConversationHeader.Content userName="SAVA" info={gettext('Ask me to do things in Superdesk')} />
                    </ConversationHeader>

                    <MessageList
                        typingIndicator={
                            loading ? <TypingIndicator content={gettext('SAVA is working…')} /> : undefined
                        }
                    >
                        {isEmpty ? (
                            <div
                                style={{
                                    height: '100%', display: 'flex', flexDirection: 'column',
                                    justifyContent: 'center', alignItems: 'center', textAlign: 'center',
                                    padding: 24, gap: 6,
                                }}
                            >
                                <h1 style={{fontSize: 26, fontWeight: 300, margin: 0}}>
                                    {gettext('What would you like to do?')}
                                </h1>
                                <p style={{opacity: 0.6, marginTop: 0, marginBottom: 12}}>
                                    {gettext('Describe it in plain language and SAVA will do it for you.')}
                                </p>
                                <div style={{display: 'flex', flexDirection: 'column', gap: 8, width: '100%', maxWidth: 520}}>
                                    {EXAMPLES.map((ex, i) => (
                                        <button
                                            key={i}
                                            onClick={() => submit(ex)}
                                            style={{
                                                textAlign: 'left', padding: '12px 16px', borderRadius: 8, cursor: 'pointer',
                                                border: '1px solid var(--sd-colour-line--light, #e0e0e0)',
                                                background: 'var(--sd-colour-bg, #fff)', fontSize: 14,
                                            }}
                                        >
                                            {ex}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            messages.map((m) => (
                                <Message
                                    key={m.id}
                                    model={{
                                        direction: m.role === 'user' ? 'outgoing' : 'incoming',
                                        position: 'single',
                                    }}
                                >
                                    <Message.CustomContent>
                                        <div style={{whiteSpace: 'pre-wrap', color: m.error ? '#c62828' : undefined}}>
                                            {m.text}
                                        </div>
                                        {m.actions != null && m.actions.length > 0 && (
                                            <ActionChips actions={m.actions} />
                                        )}
                                    </Message.CustomContent>
                                </Message>
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
