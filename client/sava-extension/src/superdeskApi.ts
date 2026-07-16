import {ISuperdesk} from 'superdesk-api';

// Populated in extension.activate(); imported by components so they can reach
// the Superdesk client API (http, localization, ui, ...). Mirrors the pattern
// used by the sams extension.
export const superdeskApi = {} as ISuperdesk;
