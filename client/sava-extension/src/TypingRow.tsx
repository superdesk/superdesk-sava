import * as React from 'react';

/** Progress indicator shown while a turn is in flight, with a Stop button. */
export function TypingRow({label, stopLabel, onStop}: {label: string; stopLabel: string; onStop: () => void}) {
    return (
        <div className="sava-row sava-row--assistant">
            <div className="sava-avatar"><i className="big-icon--general-ai" /></div>
            <div className="sava-typing">
                <span className="sava-typing__dot" />
                <span className="sava-typing__dot" />
                <span className="sava-typing__dot" />
                <span className="sava-typing__label">{label}</span>
                <button className="sava-typing__stop" onClick={onStop}>{stopLabel}</button>
            </div>
        </div>
    );
}
