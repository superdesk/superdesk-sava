import * as React from 'react';
import {ISavaItemCard} from './api';
import {superdeskApi} from './superdeskApi';

function formatWhen(value: string | null | undefined): string | null {
    if (value == null || value.length === 0) {
        return null;
    }

    const date = new Date(value);

    if (isNaN(date.getTime())) {
        return null;
    }

    return superdeskApi.localization.formatDateTime(date);
}

/** Items a tool returned, as a grid of small cards that open the item. */
export function ItemCards({items}: {items: Array<ISavaItemCard>}) {
    return (
        <div className="sava-cards">
            {items.map((item) => {
                const when = formatWhen(item.date);

                return (
                    <a
                        key={item.kind + ':' + item.id}
                        className="sava-card"
                        data-kind={item.kind}
                        href={window.location.origin + '/#' + item.route}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={item.title}
                    >
                        <div className="sava-card__top">
                            <span className="sava-card__kind">{item.kind}</span>
                            {item.state != null && item.state.length > 0 && (
                                <span className="sava-card__state" data-state={item.state}>
                                    {item.state.replace(/_/g, ' ')}
                                </span>
                            )}
                        </div>
                        <div className="sava-card__title">{item.title}</div>
                        {item.subtitle != null && item.subtitle.length > 0 && (
                            <div className="sava-card__subtitle">{item.subtitle}</div>
                        )}
                        {(item.desk != null || when != null) && (
                            <div className="sava-card__meta">
                                {item.desk != null && <span>{item.desk}</span>}
                                {when != null && <span>{when}</span>}
                            </div>
                        )}
                    </a>
                );
            })}
        </div>
    );
}
