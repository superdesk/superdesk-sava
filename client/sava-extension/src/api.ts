import {superdeskApi} from './superdeskApi';

/** A client-navigable link returned by a tool (client prepends its own origin). */
export interface ISavaLink {
    label: string;
    route: string;
}

/** One action the agent took (or tried to take) while handling a command. */
export interface ISavaAction {
    tool: string;
    summary: string;
    ok: boolean;
    detail?: string;
    links?: Array<ISavaLink>;
}

/** A confirmation-gated action awaiting the user's approval. */
export interface ISavaPending {
    id: string;
    tool: string;
    title: string;
    confirm_label: string;
    cancel_label: string;
    links?: Array<ISavaLink>;
}

/** The user's decision on a pending action. */
export interface ISavaDecision {
    id: string;
    approved: boolean;
    label?: string;
}

/** Response from POST /sava/command. */
export interface ISavaResult {
    reply: string;
    actions: Array<ISavaAction>;
    pending: ISavaPending | null;
    conversation_id: string | null;
    title: string | null;
}

/** Sidebar entry for one of the user's conversations. */
export interface ISavaConversationSummary {
    id: string;
    title: string;
    created: string | null;
    updated: string | null;
    pending: boolean;
}

/** One rendered turn of a stored conversation. */
export interface ISavaTurn {
    role: 'user' | 'assistant';
    text: string;
    actions?: Array<ISavaAction>;
    error?: boolean;
}

/** A stored conversation, ready to be reopened. */
export interface ISavaConversationDetail {
    id: string;
    title: string;
    turns: Array<ISavaTurn>;
    pending: ISavaPending | null;
    created: string | null;
    updated: string | null;
}

/**
 * Send a turn to the SAVA server agent: a new prompt and/or a decision resolving
 * a pending confirmation. History lives on the server; pass the conversation id
 * to continue one, or null to start a new one (the result carries the new id).
 */
export function sendCommand(
    prompt: string,
    conversationId: string | null,
    decision?: ISavaDecision,
): Promise<ISavaResult> {
    return superdeskApi.httpRequestJsonLocal<ISavaResult>({
        method: 'POST',
        path: '/sava/command',
        payload: {prompt: prompt, conversation_id: conversationId, decision: decision},
    });
}

export function listConversations(): Promise<Array<ISavaConversationSummary>> {
    return superdeskApi.httpRequestJsonLocal<{_items: Array<ISavaConversationSummary>}>({
        method: 'GET',
        path: '/sava/conversations',
    }).then((res) => res._items);
}

export function getConversation(id: string): Promise<ISavaConversationDetail> {
    return superdeskApi.httpRequestJsonLocal<ISavaConversationDetail>({
        method: 'GET',
        path: '/sava/conversations/' + encodeURIComponent(id),
    });
}

export function renameConversation(id: string, title: string): Promise<{id: string; title: string}> {
    return superdeskApi.httpRequestJsonLocal<{id: string; title: string}>({
        method: 'PATCH',
        path: '/sava/conversations/' + encodeURIComponent(id),
        payload: {title},
    });
}

export function deleteConversation(id: string): Promise<void> {
    return superdeskApi.httpRequestVoidLocal({
        method: 'DELETE',
        path: '/sava/conversations/' + encodeURIComponent(id),
    });
}

/** One server-sent event from POST /sava/command/stream. */
export interface ISavaStreamEvent extends Partial<ISavaResult> {
    type: 'status' | 'tool_start' | 'action' | 'delta' | 'discard' | 'done' | 'error';
    text?: string;
    tool?: string;
    action?: ISavaAction;
    status?: number;
}

function readEventStream(res: Response, onEvent: (event: ISavaStreamEvent) => void): Promise<void> {
    if (res.body == null) {
        return Promise.reject(new Error('Streaming is not supported by this browser.'));
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    function dispatch(block: string) {
        block.split('\n').forEach((line) => {
            if (line.indexOf('data: ') === 0) {
                onEvent(JSON.parse(line.slice(6)));
            }
        });
    }

    function pump(): Promise<void> {
        return reader.read().then(({done, value}) => {
            if (done) {
                return;
            }
            buffer += decoder.decode(value, {stream: true});

            let separator = buffer.indexOf('\n\n');

            while (separator >= 0) {
                dispatch(buffer.slice(0, separator));
                buffer = buffer.slice(separator + 2);
                separator = buffer.indexOf('\n\n');
            }

            return pump();
        });
    }

    return pump();
}

/**
 * Streaming variant of sendCommand: progress and reply text arrive as events,
 * ending with a `done` event carrying the same body sendCommand returns.
 * Aborting the signal stops the turn server-side as well.
 */
export function streamCommand(
    prompt: string,
    conversationId: string | null,
    decision: ISavaDecision | undefined,
    onEvent: (event: ISavaStreamEvent) => void,
    abortSignal: AbortSignal,
): Promise<void> {
    return superdeskApi.httpRequestRawLocal<ISavaStreamEvent>({
        method: 'POST',
        path: '/sava/command/stream',
        payload: {prompt: prompt, conversation_id: conversationId, decision: decision},
        abortSignal: abortSignal,
    }).then((res) => readEventStream(res, onEvent));
}
