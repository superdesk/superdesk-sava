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
    streamCommand,
    listConversations,
    getConversation,
    renameConversation,
    deleteConversation,
    ISavaConversationSummary,
    ISavaPending,
    ISavaResult,
    ISavaStreamEvent,
    ISavaTurn,
    ISavaAction,
    ISavaDecision,
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

interface IDraft {
    text: string;
    actions: Array<ISavaAction>;
}

export function SavaApp(_props: {setupFullWidthCapability: (config: any) => void}) {
    const {gettext} = superdeskApi.localization;
    const [messages, setMessages] = React.useState<Array<IChatMessage>>([]);
    const [draft, setDraft] = React.useState<IDraft | null>(null);
    const [status, setStatus] = React.useState<string>('');
    const [lastPrompt, setLastPrompt] = React.useState<string | null>(null);
    const abortRef = React.useRef<AbortController | null>(null);
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
        setDraft(null);
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
        setDraft(null);
        pushAssistant(
            (err && (err.reply || err.message || err.error)) || gettext('Something went wrong talking to the agent.'),
            {error: true},
        );
        setPending(null);
        setLoading(false);
    }

    /** The user pressed Stop: keep what streamed in, mark it, and let the sidebar catch up. */
    function applyStopped() {
        setDraft((d) => {
            if (d != null && (d.text.length > 0 || d.actions.length > 0)) {
                pushAssistant(d.text, {actions: d.actions, stopped: true});
            }
            return null;
        });
        setLoading(false);
        refreshList();
    }

    function onEvent(event: ISavaStreamEvent) {
        switch (event.type) {
        case 'status':
            setStatus(event.text || '');
            break;
        case 'tool_start':
            setStatus(gettext('Running {{tool}}…', {tool: event.tool || ''}));
            break;
        case 'action':
            setDraft((d) => ({
                text: d != null ? d.text : '',
                actions: (d != null ? d.actions : []).concat(event.action!),
            }));
            break;
        case 'delta':
            setDraft((d) => ({
                text: (d != null ? d.text : '') + (event.text || ''),
                actions: d != null ? d.actions : [],
            }));
            break;
        case 'discard':
            setDraft((d) => ({text: '', actions: d != null ? d.actions : []}));
            break;
        case 'done':
            applyResult(event as ISavaResult);
            break;
        case 'error':
            applyError(event);
            break;
        }
    }

    function runTurn(prompt: string, decision?: ISavaDecision) {
        const controller = new AbortController();

        abortRef.current = controller;
        setPending(null);
        setLoading(true);
        setDraft({text: '', actions: []});
        setStatus(gettext('Thinking…'));
        streamCommand(prompt, conversationId, decision, onEvent, controller.signal).then(
            () => setLoading(false),
            (err) => (controller.signal.aborted ? applyStopped() : applyError(err)),
        );
    }

    function stop() {
        if (abortRef.current != null) {
            abortRef.current.abort();
        }
    }

    function submit(raw: string) {
        const prompt = (raw || '').trim();

        if (prompt.length === 0 || loading) {
            return;
        }

        setMessages((prev) => prev.concat({id: nextId.current++, role: 'user', text: prompt}));
        setLastPrompt(prompt);
        runTurn(prompt);
    }

    /** Re-send the last prompt after a failure, dropping the error row. */
    function retry() {
        if (lastPrompt == null || loading) {
            return;
        }
        setMessages((prev) => prev.filter((m) => !m.error));
        runTurn(lastPrompt);
    }

    function decide(approved: boolean) {
        if (pending == null || loading) {
            return;
        }

        const p = pending;
        const label = approved ? p.confirm_label : p.cancel_label;

        // Reflect the choice in the thread for continuity.
        setMessages((prev) => prev.concat({id: nextId.current++, role: 'user', text: label}));
        runTurn('', {id: p.id, approved: approved, label: label});
    }

    function resetChat() {
        if (loading) {
            return;
        }
        setMessages([]);
        setDraft(null);
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

    function buildRows(): Array<React.ReactNode> {
        const rows: Array<React.ReactNode> = messages.map((m) => (
            <MessageRow
                key={m.id}
                message={m}
                onRetry={m.error && lastPrompt != null ? retry : undefined}
                retryLabel={gettext('Retry')}
                stoppedLabel={gettext('Stopped')}
            />
        ));

        if (draft != null && (draft.text.length > 0 || draft.actions.length > 0)) {
            rows.push(
                <MessageRow
                    key="draft"
                    message={{id: -1, role: 'assistant', text: draft.text, actions: draft.actions}}
                />,
            );
        }

        if (loading) {
            rows.push(<TypingRow key="typing" label={status} stopLabel={gettext('Stop')} onStop={stop} />);
        } else if (pending != null) {
            rows.push(<PendingCard key="pending" pending={pending} onDecide={decide} />);
        }

        return rows;
    }

    const isEmpty = messages.length === 0 && pending == null && !loading;

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
                        ) : buildRows()}
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
