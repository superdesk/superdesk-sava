import * as React from 'react';
import {ISavaAction} from './api';
import {LinkButtons} from './LinkButtons';
import {ItemCards} from './ItemCards';

/** "create_planning_item" -> "Create planning item". The raw id stays in the tooltip. */
export function friendlyToolName(tool: string): string {
    const words = tool.replace(/[_-]+/g, ' ').trim();

    return words.length === 0 ? tool : words.charAt(0).toUpperCase() + words.slice(1);
}

/** What the agent did while handling the command: one compact step per tool call. */
export function ActivityLog({actions}: {actions: Array<ISavaAction>}) {
    return (
        <div className="sava-steps">
            {actions.map((a, i) => (
                <React.Fragment key={i}>
                    <div
                        className={'sava-step' + (a.ok ? '' : ' is-fail')}
                        title={a.tool + (a.detail ? ' — ' + a.detail : '')}
                    >
                        <span className="sava-step__icon">{a.ok ? '✓' : '✕'}</span>
                        <span className="sava-step__name">{friendlyToolName(a.tool)}</span>
                        <span className="sava-step__summary">{a.summary}</span>
                        <LinkButtons links={a.links} />
                    </div>
                    {a.items != null && a.items.length > 0 && <ItemCards items={a.items} />}
                </React.Fragment>
            ))}
        </div>
    );
}
