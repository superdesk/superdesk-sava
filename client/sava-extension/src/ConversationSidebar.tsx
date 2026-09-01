import * as React from 'react';
import {ISavaConversationSummary} from './api';
import {superdeskApi} from './superdeskApi';

interface IProps {
    conversations: Array<ISavaConversationSummary>;
    activeId: string | null;
    busy: boolean;
    onSelect: (id: string) => void;
    onNew: () => void;
    onRename: (id: string, title: string) => void;
    onDelete: (id: string) => void;
}

interface IGroup {
    label: string;
    items: Array<ISavaConversationSummary>;
}

const DAY_MS = 24 * 60 * 60 * 1000;

/** Bucket conversations by last activity: Today / Yesterday / Previous 7 days / Older. */
export function groupByDay(
    conversations: Array<ISavaConversationSummary>,
    now: Date,
    gettext: (s: string) => string,
): Array<IGroup> {
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const buckets: Array<IGroup> = [
        {label: gettext('Today'), items: []},
        {label: gettext('Yesterday'), items: []},
        {label: gettext('Previous 7 days'), items: []},
        {label: gettext('Older'), items: []},
    ];

    conversations.forEach((c) => {
        const when = c.updated != null ? new Date(c.updated).getTime() : 0;
        let index = 3;

        if (when >= startOfToday) {
            index = 0;
        } else if (when >= startOfToday - DAY_MS) {
            index = 1;
        } else if (when >= startOfToday - 7 * DAY_MS) {
            index = 2;
        }
        buckets[index].items.push(c);
    });

    return buckets.filter((b) => b.items.length > 0);
}

/** Left-hand list of the user's past chats, ChatGPT-style. */
export function ConversationSidebar(props: IProps) {
    const {gettext} = superdeskApi.localization;
    const [editingId, setEditingId] = React.useState<string | null>(null);
    const [draft, setDraft] = React.useState('');
    const [query, setQuery] = React.useState('');
    const needle = query.trim().toLowerCase();
    const visible = needle.length === 0
        ? props.conversations
        : props.conversations.filter((c) => c.title.toLowerCase().indexOf(needle) >= 0);
    const groups = groupByDay(visible, new Date(), gettext);

    function startRename(c: ISavaConversationSummary) {
        setEditingId(c.id);
        setDraft(c.title);
    }

    function commitRename() {
        const title = draft.trim();

        if (editingId != null && title.length > 0) {
            props.onRename(editingId, title);
        }
        setEditingId(null);
    }

    function onDraftKey(event: React.KeyboardEvent<HTMLInputElement>) {
        if (event.key === 'Enter') {
            commitRename();
        } else if (event.key === 'Escape') {
            setEditingId(null);
        }
    }

    function confirmDelete(c: ISavaConversationSummary) {
        superdeskApi.ui.confirm(
            gettext('Delete this chat? This cannot be undone.'),
            c.title,
            gettext('Delete'),
        ).then((ok) => {
            if (ok) {
                props.onDelete(c.id);
            }
        });
    }

    return (
        <aside className="sava-sidebar">
            <button
                className="sava-sidebar__new"
                onClick={props.onNew}
                disabled={props.busy}
            >
                <i className="icon-plus-sign" /> {gettext('New chat')}
            </button>

            {props.conversations.length > 0 && (
                <input
                    className="sava-sidebar__search"
                    type="search"
                    placeholder={gettext('Search chats…')}
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                />
            )}

            <div className="sava-sidebar__list">
                {groups.length === 0 && (
                    <div className="sava-sidebar__empty">
                        {needle.length > 0 ? gettext('No chats match.') : gettext('Your chats will appear here.')}
                    </div>
                )}
                {groups.map((group) => (
                    <div className="sava-sidebar__group" key={group.label}>
                        <div className="sava-sidebar__label">{group.label}</div>
                        {group.items.map((c) => (
                            <div
                                key={c.id}
                                className={'sava-sidebar__item' + (c.id === props.activeId ? ' is-active' : '')}
                            >
                                {editingId === c.id ? (
                                    <input
                                        className="sava-sidebar__rename"
                                        value={draft}
                                        autoFocus
                                        onChange={(e) => setDraft(e.target.value)}
                                        onKeyDown={onDraftKey}
                                        onBlur={commitRename}
                                    />
                                ) : (
                                    <button
                                        className="sava-sidebar__title"
                                        title={c.title}
                                        disabled={props.busy}
                                        onClick={() => props.onSelect(c.id)}
                                    >
                                        {c.pending && (
                                            <span
                                                className="sava-sidebar__dot"
                                                title={gettext('Awaiting your decision')}
                                            />
                                        )}
                                        {c.title}
                                    </button>
                                )}
                                <span className="sava-sidebar__actions">
                                    <button
                                        className="sava-sidebar__action"
                                        title={gettext('Rename')}
                                        disabled={props.busy}
                                        onClick={() => startRename(c)}
                                    >
                                        <i className="icon-pencil" />
                                    </button>
                                    <button
                                        className="sava-sidebar__action"
                                        title={gettext('Delete')}
                                        disabled={props.busy}
                                        onClick={() => confirmDelete(c)}
                                    >
                                        <i className="icon-trash" />
                                    </button>
                                </span>
                            </div>
                        ))}
                    </div>
                ))}
            </div>
        </aside>
    );
}
