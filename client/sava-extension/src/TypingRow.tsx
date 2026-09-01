import * as React from 'react';

/** "SAVA is working…" indicator shown while a request is in flight. */
export function TypingRow({label}: {label: string}) {
    return (
        <div className="sava-row sava-row--assistant">
            <div className="sava-avatar"><i className="big-icon--general-ai" /></div>
            <div className="sava-typing">
                <span className="sava-typing__dot" />
                <span className="sava-typing__dot" />
                <span className="sava-typing__dot" />
                <span className="sava-typing__label">{label}</span>
            </div>
        </div>
    );
}
