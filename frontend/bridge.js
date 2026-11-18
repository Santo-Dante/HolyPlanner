'use strict';
// A janela nativa mantém sua ponte Python. Navegadores usam a API autenticada.
async function connectWebBridge() {
    if (document.body.dataset.runtime !== 'web' || window.pywebview) return;
    window.holyWeb = true;
    const send = async (path, data) => {
        let response;
        try {
            response = await fetch(path, {method: 'POST', headers: {
                'Content-Type': 'application/json', 'X-Holy-Planner': '1'
            }, body: JSON.stringify(data)});
        } catch {
            document.querySelector('#connection-status').textContent = 'Sem conexão com o computador';
            throw new Error('Sem conexão. Mantenha o servidor aberto no computador e conecte-se à mesma rede.');
        }
        const result = await response.json();
        if (response.ok) document.querySelector('#connection-status').textContent = 'Conectado ao seu computador';
        if (response.status === 401 && path !== '/api/login') document.querySelector('#pair-dialog').showModal();
        return result;
    };
    window.pywebview = {api: new Proxy({}, {get: (_, method) => async (...args) => {
        const result = await send('/api/call', {method, args});
        if (result.download) {
            const bytes = Uint8Array.from(atob(result.download.data), c => c.charCodeAt(0));
            const url = URL.createObjectURL(new Blob([bytes]));
            const link = document.createElement('a');
            link.href = url; link.download = result.download.name; link.click();
            setTimeout(() => URL.revokeObjectURL(url), 30000);
            delete result.download;
        }
        return result;
    }})};
    document.querySelector('#pair-form').addEventListener('submit', async event => {
        event.preventDefault();
        const button = event.submitter;
        button.disabled = true;
        try {
            const result = await send('/api/login', {code: document.querySelector('#pair-code').value.trim()});
            if (!result.ok) throw new Error(result.error);
            document.querySelector('#pair-dialog').close();
            document.querySelector('#pair-code').value = '';
            document.querySelector('#connection-status').textContent = 'Conectado ao seu computador';
            window.dispatchEvent(new Event('pywebviewready'));
        } catch (error) { document.querySelector('#pair-error').textContent = error.message; }
        finally { button.disabled = false; }
    });
    document.querySelector('#connection-status').textContent = 'Conectado ao seu computador';
    // app.js starts after this script and sees the bridge even while offline.
}
connectWebBridge();
