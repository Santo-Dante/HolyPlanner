'use strict';
// Runs before the CSS paints: dark theme by default and the saved sidebar state.
(() => {
    const read = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };
    const theme = read('holy-theme-v2', 'dark') === 'light' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    if (read('holy-nav-collapsed', false)) document.documentElement.classList.add('nav-collapsed');
    const meta = document.querySelector('meta[name=theme-color]');
    if (meta) meta.content = theme === 'dark' ? '#14161c' : '#f7f8fa';
})();
