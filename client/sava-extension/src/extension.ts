import {ISuperdesk, IExtension, IExtensionActivationResult} from 'superdesk-api';
import {superdeskApi} from './superdeskApi';
import {SavaApp} from './SavaApp';

const extension: IExtension = {
    activate: (superdesk: ISuperdesk) => {
        // Share the client API with the rest of the extension.
        Object.assign(superdeskApi, superdesk);

        const {gettext} = superdesk.localization;

        const result: IExtensionActivationResult = {
            contributions: {
                pages: [{
                    title: gettext('SAVA'),
                    url: '/sava',
                    component: SavaApp,
                    showTopMenu: false,
                    showSideMenu: true,
                    addToMainMenu: false,
                    addToSideMenu: {
                        icon: 'general-ai',
                        // Sidenav sorts ascending by order; Planning is the current
                        // lowest at 1100. Keep SAVA last (after Planning) while it's
                        // in beta.
                        order: 1200,
                        keyBinding: 'ctrl+alt+a',
                    },
                }],
            },
        };

        return Promise.resolve(result);
    },
};

export default extension;
