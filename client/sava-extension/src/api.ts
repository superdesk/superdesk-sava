import {superdeskApi} from './superdeskApi';

/** One action the agent took (or tried to take) while handling a command. */
export interface ISavaAction {
    tool: string;
    summary: string;
    ok: boolean;
    detail?: string;
}

/** Response from POST /sava/command. */
export interface ISavaResult {
    reply: string;
    actions: Array<ISavaAction>;
}

/**
 * Send a natural-language command to the SAVA server agent.
 * Resolves to the agent's reply plus the list of actions it performed.
 */
export function sendCommand(prompt: string): Promise<ISavaResult> {
    return superdeskApi.httpRequestJsonLocal<ISavaResult>({
        method: 'POST',
        path: '/sava/command',
        payload: {prompt},
    });
}
