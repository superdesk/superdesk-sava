import * as React from 'react';
import {ISavaAction} from './api';
import {LinkButtons} from './LinkButtons';

/** Tool calls rendered as a vertical activity log, one per line. */
export function ActivityLog({actions}: {actions: Array<ISavaAction>}) {
    return (
        <div className="sava-actions">
            {actions.map((a, i) => (
                <div className="sava-action" key={i} title={a.detail || ''}>
                    <span className={'sava-action__icon ' + (a.ok ? 'is-ok' : 'is-fail')}>
                        {a.ok ? '✓' : '✕'}
                    </span>
                    <code className="sava-action__tool">{a.tool}</code>
                    <span className="sava-action__summary">{a.summary}</span>
                    <LinkButtons links={a.links} />
                </div>
            ))}
        </div>
    );
}
