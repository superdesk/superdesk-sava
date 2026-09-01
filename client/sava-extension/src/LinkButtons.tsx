import * as React from 'react';
import {ISavaLink} from './api';

/** Client-navigable links: prepend the app's own hash router (host-agnostic). */
export function LinkButtons({links}: {links?: Array<ISavaLink>}) {
    if (links == null || links.length === 0) {
        return null;
    }

    return (
        <span className="sava-links">
            {links.map((l, i) => (
                <a
                    key={i}
                    className="sava-link"
                    href={window.location.origin + '/#' + l.route}
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    {l.label} ↗
                </a>
            ))}
        </span>
    );
}
