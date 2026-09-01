import * as React from 'react';
import {ISavaPending} from './api';
import {LinkButtons} from './LinkButtons';

/** Approval card for a confirmation-gated action the agent wants to run. */
export function PendingCard({pending, onDecide}: {pending: ISavaPending; onDecide: (approved: boolean) => void}) {
    return (
        <div className="sava-row sava-row--assistant">
            <div className="sava-avatar"><i className="big-icon--general-ai" /></div>
            <div className="sava-confirm">
                <div className="sava-confirm__title">{pending.title}</div>
                {pending.links != null && pending.links.length > 0 && (
                    <div className="sava-confirm__links"><LinkButtons links={pending.links} /></div>
                )}
                <div className="sava-confirm__actions">
                    <button
                        className="sava-confirm__btn sava-confirm__btn--cancel"
                        onClick={() => onDecide(false)}
                    >
                        {pending.cancel_label}
                    </button>
                    <button
                        className="sava-confirm__btn sava-confirm__btn--confirm"
                        onClick={() => onDecide(true)}
                    >
                        {pending.confirm_label}
                    </button>
                </div>
            </div>
        </div>
    );
}
