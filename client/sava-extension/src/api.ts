import {superdeskApi} from './superdeskApi';

/** One action the agent took (or tried to take) while handling a command. */
export interface ISavaAction {
    tool: string;
    summary: string;
    ok: boolean;
    detail?: string;
}

/**
 * Opaque conversation state round-tripped between client and server so the
 * agent remembers prior turns. The client never inspects it — it just stores
 * whatever the server returns and sends it back on the next request.
 */
export type SavaConversation = Array<unknown>;

/** Response from POST /sava/command. */
export interface ISavaResult {
    reply: string;
    actions: Array<ISavaAction>;
    conversation: SavaConversation;
}

/**
 * Send a natural-language command to the SAVA server agent, along with the
 * prior conversation so the agent has context. Resolves to the agent's reply,
 * the actions it performed, and the updated conversation to send back next time.
 */
export function sendCommand(prompt: string, conversation: SavaConversation): Promise<ISavaResult> {
    return superdeskApi.httpRequestJsonLocal<ISavaResult>({
        method: 'POST',
        path: '/sava/command',
        payload: {prompt, conversation},
    });
}
