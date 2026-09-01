import * as React from 'react';
import {ISavaAction} from './api';
import {Markdown} from './Markdown';
import {ActivityLog} from './ActivityLog';

export interface IChatMessage {
    id: number;
    role: 'user' | 'assistant';
    text: string;
    actions?: Array<ISavaAction>;
    error?: boolean;
    /** The user stopped the turn before it finished. */
    stopped?: boolean;
}

interface IProps {
    message: IChatMessage;
    /** Offered on error rows: re-send the prompt that failed. */
    onRetry?: () => void;
    retryLabel?: string;
    stoppedLabel?: string;
}

/** One message in the thread: a user bubble, or an assistant bubble with its activity log. */
export function MessageRow({message, onRetry, retryLabel, stoppedLabel}: IProps) {
    if (message.role === 'user') {
        return (
            <div className="sava-row sava-row--user">
                <div className="sava-bubble sava-bubble--user">
                    <div className="sava-text">{message.text}</div>
                </div>
            </div>
        );
    }

    let body: React.ReactNode = null;

    if (message.text && message.error) {
        body = <div className="sava-text" data-error="true">{message.text}</div>;
    } else if (message.text) {
        body = <Markdown text={message.text} />;
    }

    return (
        <div className="sava-row sava-row--assistant">
            <div className="sava-avatar"><i className="big-icon--general-ai" /></div>
            <div className="sava-bubble sava-bubble--assistant">
                {body}
                {message.actions != null && message.actions.length > 0 && (
                    <ActivityLog actions={message.actions} />
                )}
                {message.stopped && <div className="sava-note">{stoppedLabel}</div>}
                {message.error && onRetry != null && (
                    <button className="sava-retry" onClick={onRetry}>{retryLabel}</button>
                )}
            </div>
        </div>
    );
}
