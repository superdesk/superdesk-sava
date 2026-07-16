import * as React from 'react';
import {superdeskApi} from './superdeskApi';
import {sendCommand, ISavaResult} from './api';

const EXAMPLES: Array<string> = [
    'Create a text article with a headline and slugline and publish',
    'Show me all the articles that were authored by XYZ',
    "Create a planning item for today with the topic 'AI conference' and add an image coverage to it",
];

interface IState {
    prompt: string;
    loading: boolean;
    result: ISavaResult | null;
    error: string | null;
}

export class SavaApp extends React.Component<{setupFullWidthCapability: (config: any) => void}, IState> {
    constructor(props: any) {
        super(props);
        this.state = {prompt: '', loading: false, result: null, error: null};
        this.submit = this.submit.bind(this);
        this.onKeyDown = this.onKeyDown.bind(this);
    }

    submit() {
        const prompt = this.state.prompt.trim();

        if (prompt.length === 0 || this.state.loading) {
            return;
        }

        this.setState({loading: true, error: null, result: null});

        sendCommand(prompt).then(
            (result) => this.setState({loading: false, result}),
            (err) => this.setState({
                loading: false,
                error: (err && (err.message || err.error)) || 'Something went wrong talking to the agent.',
            }),
        );
    }

    onKeyDown(e: React.KeyboardEvent) {
        // Cmd/Ctrl + Enter submits
        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
            e.preventDefault();
            this.submit();
        }
    }

    render() {
        const {gettext} = superdeskApi.localization;
        const {prompt, loading, result, error} = this.state;

        return (
            <div style={{height: '100%', overflowY: 'auto', background: 'var(--sd-colour-bg__sidebar, #f8f8f8)'}}>
                <div style={{maxWidth: 720, margin: '0 auto', padding: '48px 24px 64px'}}>
                    <h1 style={{fontSize: 28, fontWeight: 300, marginBottom: 8, textAlign: 'center'}}>
                        {gettext('What would you like to do?')}
                    </h1>
                    <p style={{textAlign: 'center', opacity: 0.6, marginBottom: 24}}>
                        {gettext('Describe it in plain language and SAVA will do it for you.')}
                    </p>

                    <textarea
                        autoFocus
                        value={prompt}
                        disabled={loading}
                        onChange={(e) => this.setState({prompt: e.target.value})}
                        onKeyDown={this.onKeyDown}
                        placeholder={gettext('e.g. Create a text article with the headline "Messi goes to the finals" and publish it')}
                        style={{
                            width: '100%', minHeight: 96, padding: 16, fontSize: 16,
                            borderRadius: 8, border: '1px solid var(--sd-colour-line--medium, #d0d0d0)',
                            resize: 'vertical', boxSizing: 'border-box', fontFamily: 'inherit',
                        }}
                    />

                    <div style={{display: 'flex', justifyContent: 'flex-end', marginTop: 12}}>
                        <button
                            className="btn btn--primary"
                            disabled={loading || prompt.trim().length === 0}
                            onClick={this.submit}
                        >
                            {loading ? gettext('Working…') : gettext('Send')}
                        </button>
                    </div>

                    {result == null && error == null && (
                        <div style={{marginTop: 32}}>
                            <div style={{fontSize: 12, textTransform: 'uppercase', opacity: 0.5, marginBottom: 8}}>
                                {gettext('Examples')}
                            </div>
                            {EXAMPLES.map((ex, i) => (
                                <button
                                    key={i}
                                    onClick={() => this.setState({prompt: ex})}
                                    style={{
                                        display: 'block', width: '100%', textAlign: 'left', marginBottom: 8,
                                        padding: '12px 16px', borderRadius: 8, cursor: 'pointer',
                                        border: '1px solid var(--sd-colour-line--light, #e0e0e0)',
                                        background: 'var(--sd-colour-bg, #fff)', fontSize: 14,
                                    }}
                                >
                                    {ex}
                                </button>
                            ))}
                        </div>
                    )}

                    {error != null && (
                        <div
                            style={{
                                marginTop: 24, padding: 16, borderRadius: 8,
                                background: 'var(--sd-colour-alert--025, #fdecea)',
                                border: '1px solid var(--sd-colour-alert, #e57373)',
                            }}
                        >
                            <strong>{gettext('Error')}: </strong>{error}
                        </div>
                    )}

                    {result != null && (
                        <div style={{marginTop: 24}}>
                            <div
                                style={{
                                    padding: 16, borderRadius: 8, marginBottom: 16,
                                    background: 'var(--sd-colour-bg, #fff)',
                                    border: '1px solid var(--sd-colour-line--light, #e0e0e0)',
                                }}
                            >
                                {result.reply}
                            </div>

                            {result.actions.length > 0 && (
                                <div>
                                    <div style={{fontSize: 12, textTransform: 'uppercase', opacity: 0.5, marginBottom: 8}}>
                                        {gettext('Actions')}
                                    </div>
                                    {result.actions.map((a, i) => (
                                        <div
                                            key={i}
                                            style={{
                                                display: 'flex', alignItems: 'flex-start', gap: 10,
                                                padding: '10px 14px', marginBottom: 6, borderRadius: 6,
                                                background: 'var(--sd-colour-bg, #fff)',
                                                border: '1px solid var(--sd-colour-line--light, #e0e0e0)',
                                            }}
                                        >
                                            <span style={{color: a.ok ? '#2e7d32' : '#c62828'}}>
                                                {a.ok ? '✓' : '✕'}
                                            </span>
                                            <span style={{flex: 1}}>
                                                <code style={{opacity: 0.6, marginRight: 8}}>{a.tool}</code>
                                                {a.summary}
                                                {a.detail != null && (
                                                    <div style={{opacity: 0.6, fontSize: 13, marginTop: 2}}>{a.detail}</div>
                                                )}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}

                            <div style={{marginTop: 16}}>
                                <button
                                    className="btn"
                                    onClick={() => this.setState({prompt: '', result: null, error: null})}
                                >
                                    {gettext('New command')}
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        );
    }
}
