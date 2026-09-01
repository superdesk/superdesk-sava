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
