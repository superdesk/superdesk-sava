import * as React from 'react';
import {marked} from 'marked';
import DOMPurify from 'dompurify';

/** Render an assistant reply as sanitized markdown (bold, lists, links, code). */
export function Markdown({text}: {text: string}) {
    const html = React.useMemo(() => {
        const raw = marked.parse(text || '', {async: false}) as string;

        return DOMPurify.sanitize(raw);
    }, [text]);

    return <div className="sava-md" dangerouslySetInnerHTML={{__html: html}} />;
}
