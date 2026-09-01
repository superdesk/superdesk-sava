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
import {
    sendCommand,
    listConversations,
    getConversation,
    renameConversation,
    deleteConversation,
    ISavaConversationSummary,
    ISavaPending,
    ISavaResult,
    ISavaTurn,
} from './api';
import {IChatMessage, MessageRow} from './MessageRow';
import {PendingCard} from './PendingCard';
import {TypingRow} from './TypingRow';
import {ConversationSidebar} from './ConversationSidebar';

const EXAMPLES: Array<string> = [
    'Show me the articles I have authored',
    'What\'s on the Default Desk right now?',
    'Create a planning item for today about the AI conference and add a text coverage',
];

const ACTIVE_KEY = 'sava.activeConversation';

function readActiveId(): string | null {
    try {
        return window.localStorage.getItem(ACTIVE_KEY);
    } catch (_e) {
        return null;
    }
}

function writeActiveId(id: string | null) {
    try {
        if (id == null) {
            window.localStorage.removeItem(ACTIVE_KEY);
        } else {
            window.localStorage.setItem(ACTIVE_KEY, id);
        }
    } catch (_e) {
        // storage unavailable: the chat still works, it just won't be restored on reload
    }
}

export function SavaApp(_props: {setupFullWidthCapability: (config: any) => void}) {
    const {gettext} = superdeskApi.localization;
    const [messages, setMessages] = React.useState<Array<IChatMessage>>([]);
    const [conversationId, setConversationId] = React.useState<string | null>(null);
    const [title, setTitle] = React.useState<string | null>(null);
    const [conversations, setConversations] = React.useState<Array<ISavaConversationSummary>>([]);
    const [pending, setPending] = React.useState<ISavaPending | null>(null);
    const [loading, setLoading] = React.useState(false);
    const nextId = React.useRef(1);

    function toMessages(turns: Array<ISavaTurn>): Array<IChatMessage> {
        return turns.map((t) => ({id: nextId.current++, ...t}));
    }

    function pushAssistant(text: string, extra: Partial<IChatMessage> = {}) {
        setMessages((prev) => prev.concat({id: nextId.current++, role: 'assistant', text: text, ...extra}));
    }

    function refreshList() {
        listConversations().then(setConversations, () => { /* sidebar just stays stale */ });
    }

    function openConversation(id: string) {
        setLoading(true);
        getConversation(id).then((detail) => {
            setMessages(toMessages(detail.turns));
            setPending(detail.pending);
            setConversationId(detail.id);
            setTitle(detail.title);
            writeActiveId(detail.id);
            setLoading(false);
        }, () => {
            writeActiveId(null);
            setLoading(false);
        });
    }

    React.useEffect(() => {
        refreshList();
        const remembered = readActiveId();

        if (remembered != null) {
            openConversation(remembered);
        }
    }, []);

    function applyResult(result: ISavaResult) {
        if (result.reply || (result.actions != null && result.actions.length > 0)) {
            pushAssistant(result.reply, {actions: result.actions});
        }
        setPending(result.pending);
        if (result.conversation_id != null) {
            setConversationId(result.conversation_id);
            setTitle(result.title);
            writeActiveId(result.conversation_id);
            refreshList();
        }
        setLoading(false);
    }

    function applyError(err: any) {
        pushAssistant(
            (err && (err.message || err.error)) || gettext('Something went wrong talking to the agent.'),
            {error: true},
        );
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
        sendCommand(prompt, conversationId).then(applyResult, applyError);
    }

    function decide(approved: boolean) {
        if (pending == null || loading) {
            return;
        }

        const p = pending;
        const label = approved ? p.confirm_label : p.cancel_label;

        // Reflect the choice in the thread for continuity.
        setMessages((prev) => prev.concat({id: nextId.current++, role: 'user', text: label}));
        setPending(null);
        setLoading(true);
        sendCommand('', conversationId, {id: p.id, approved: approved, label: label}).then(applyResult, applyError);
    }

    function resetChat() {
        if (loading) {
            return;
        }
        setMessages([]);
        setPending(null);
        setConversationId(null);
        setTitle(null);
        writeActiveId(null);
    }

    function rename(id: string, newTitle: string) {
        renameConversation(id, newTitle).then((res) => {
            setConversations((prev) => prev.map((c) => (c.id === id ? {...c, title: res.title} : c)));
            if (id === conversationId) {
                setTitle(res.title);
            }
        }, () => refreshList());
    }

    function remove(id: string) {
        deleteConversation(id).then(() => {
            setConversations((prev) => prev.filter((c) => c.id !== id));
            if (id === conversationId) {
                resetChat();
            }
        }, () => refreshList());
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
            <ConversationSidebar
                conversations={conversations}
                activeId={conversationId}
                busy={loading}
                onSelect={openConversation}
                onNew={resetChat}
                onRename={rename}
                onDelete={remove}
            />
            <MainContainer>
                <ChatContainer>
                    <ConversationHeader>
                        <ConversationHeader.Content
                            userName={title || 'SAVA'}
                            info={gettext('Ask me to do things in Superdesk')}
                        />
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
