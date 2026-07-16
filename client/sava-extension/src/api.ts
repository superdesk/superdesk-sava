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
}

/**
 * Opaque conversation state round-tripped between client and server so the agent
 * remembers prior turns. The client never inspects it — it just stores whatever
 * the server returns and sends it back on the next request.
 */
export type SavaConversation = Array<unknown>;

/** Response from POST /sava/command. */
export interface ISavaResult {
    reply: string;
    actions: Array<ISavaAction>;
    conversation: SavaConversation;
    pending: ISavaPending | null;
}

/**
 * Send a turn to the SAVA server agent: a new prompt and/or a decision resolving
 * a pending confirmation, along with the prior conversation for context.
 */
export function sendCommand(
    prompt: string,
    conversation: SavaConversation,
    decision?: ISavaDecision,
): Promise<ISavaResult> {
    return superdeskApi.httpRequestJsonLocal<ISavaResult>({
        method: 'POST',
        path: '/sava/command',
        payload: {prompt, conversation, decision},
    });
}
