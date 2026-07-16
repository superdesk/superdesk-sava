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
import {sendCommand, ISavaAction, ISavaLink, ISavaPending, ISavaResult, SavaConversation} from './api';

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

/** Client-navigable links: prepend the app's own hash router (host-agnostic). */
function LinkButtons({links}: {links?: Array<ISavaLink>}) {
    if (links == null || links.length === 0) {
        return null;
    }
    return (
        <span className="sava-links">
            {links.map((l, i) => (
                <a key={i} className="sava-link" href={'#' + l.route}>{l.label} ↗</a>
            ))}
        </span>
    );
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
                    <LinkButtons links={a.links} />
                </div>
            ))}
        </div>
    );
}

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
        sendCommand('', conversation, {id: p.id, approved}).then(applyResult, applyError);
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

    const rows: Array<React.ReactNode> = messages.map((m) => (
        m.role === 'user' ? (
            <div className="sava-row sava-row--user" key={m.id}>
                <div className="sava-bubble sava-bubble--user">
                    <div className="sava-text">{m.text}</div>
                </div>
            </div>
        ) : (
            <div className="sava-row sava-row--assistant" key={m.id}>
                <div className="sava-avatar"><i className="big-icon--general-ai" /></div>
                <div className="sava-bubble sava-bubble--assistant">
                    {m.text ? (
                        <div className="sava-text" data-error={m.error ? 'true' : 'false'}>{m.text}</div>
                    ) : null}
                    {m.actions != null && m.actions.length > 0 && (
                        <ActivityLog actions={m.actions} />
                    )}
                </div>
            </div>
        )
    ));

    if (loading) {
        rows.push(
            <div className="sava-row sava-row--assistant" key="typing">
                <div className="sava-avatar"><i className="big-icon--general-ai" /></div>
                <div className="sava-typing">
                    <span className="sava-typing__dot" />
                    <span className="sava-typing__dot" />
                    <span className="sava-typing__dot" />
                    <span className="sava-typing__label">{gettext('SAVA is working…')}</span>
                </div>
            </div>,
        );
    }

    if (pending != null && !loading) {
        rows.push(
            <div className="sava-row sava-row--assistant" key="pending">
                <div className="sava-avatar"><i className="big-icon--general-ai" /></div>
                <div className="sava-confirm">
                    <div className="sava-confirm__title">{pending.title}</div>
                    {pending.links != null && pending.links.length > 0 && (
                        <div className="sava-confirm__links"><LinkButtons links={pending.links} /></div>
                    )}
                    <div className="sava-confirm__actions">
                        <button
                            className="sava-confirm__btn sava-confirm__btn--cancel"
                            onClick={() => decide(false)}
                        >
                            {pending.cancel_label}
                        </button>
                        <button
                            className="sava-confirm__btn sava-confirm__btn--confirm"
                            onClick={() => decide(true)}
                        >
                            {pending.confirm_label}
                        </button>
                    </div>
                </div>
            </div>,
        );
    }

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
