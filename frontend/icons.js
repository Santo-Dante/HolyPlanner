'use strict';
const iconPaths = {
    home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z"/>',
    folder: '<path d="M3 6a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1Z"/>',
    list: '<path d="M9 5h12M9 12h12M9 19h12M3 5h1M3 12h1M3 19h1"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 10h18"/>',
    repeat: '<path d="M3 10a9 9 0 1 0 3-6M3 3v7h7"/>',
    dollar: '<path d="M12 2v20m5-16H9a4 4 0 0 0 0 8h6a4 4 0 0 1 0 8H6"/>',
    search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    settings: '<path d="m10 3-.6 2.2-2 .8-2-.8-2 3.4L5 10v2l-1.6 1.5 2 3.4 2-.7 2 .8L10 19h4l.6-2 2-.8 2 .7 2-3.4L19 12v-2l1.6-1.4-2-3.4-2 .8-2-.8L14 3Z"/><circle cx="12" cy="11" r="3"/>',
    plus: '<path d="M12 4v16M4 12h16"/>',
    checkSquare: '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="m7 12 3 3 7-7"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l5 3"/>',
    target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    drop: '<path d="M12 3S5 11 5 15a7 7 0 0 0 14 0c0-4-7-12-7-12Z"/><path d="M8 15a4 4 0 0 0 4 4"/>',
    book: '<path d="M12 5v16M3 4c4-1 6 0 9 2 3-2 5-3 9-2v15c-4-1-6 0-9 2-3-2-5-3-9-2Z"/>',
    bell: '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4Z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
    bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7Z"/>',
    heart: '<path d="M12 20s-7-4.4-9-9a5 5 0 0 1 9-3 5 5 0 0 1 9 3c-2 4.6-9 9-9 9Z"/>',
    trend: '<path d="M3 20h18"/><path d="m4 16 5-5 4 3 7-8"/><path d="M15 6h5v5"/>',
    dumbbell: '<path d="M3 8v8m4-11v14m10-14v14m4-11v8M7 9h10v6H7M3 10h4m10 0h4M3 14h4m10 0h4"/>',
    more: '<circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/>',
    edit: '<path d="m14 5 5 5M4 20l4-1 12-12a2 2 0 0 0-4-4L4 15Z"/>',
    trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/>',
    upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6"/>',
    close: '<path d="m6 6 12 12M6 18 18 6"/>',
    chevron: '<path d="m9 5 7 7-7 7"/>',
};
function uiIcon(name, extraClass='') {
    return `<svg class="ui-icon ${extraClass}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${iconPaths[name] || iconPaths.repeat}</svg>`;
}
function calendarLogo() {
    return '<svg class="calendar-logo" viewBox="0 0 44 44" aria-hidden="true"><path fill="#4285f4" d="M6 1h32a5 5 0 0 1 5 5v31L32 43H6a5 5 0 0 1-5-5V6a5 5 0 0 1 5-5Z"/><path fill="#fff" d="M10 10h25v25H10Z"/><path fill="#34a853" d="M10 35h25l-4 8H10Z"/><path fill="#fbbc04" d="M35 10h8v25h-8Z"/><path fill="#ea4335" d="m35 35 8-1-11 9Z"/><path fill="#1967d2" d="M1 10h9v25H1Z"/><text x="22" y="29" text-anchor="middle" font-size="19" font-family="Arial,sans-serif" font-weight="700" fill="#4285f4">31</text></svg>';
}
