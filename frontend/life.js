'use strict';
// Holy Planner 5.0: captura rápida, lembretes, revisão semanal, diário e cartões do Meu dia.
let reviewState, reviewWeek = '', reviewDraft = null, journalState, journalDraft = null;
let lifeReminders = [], lifeSettings = null, lifeReminderTimer = null, lifeLastReminderCheck = 0;
const lifeMoodLabels = ['', 'Muito difícil', 'Difícil', 'Neutro', 'Bom', 'Ótimo'];
const lifeEnergyLabels = ['', 'Sem energia', 'Baixa', 'Média', 'Boa', 'Alta'];

/* ================= Captura rápida: interpretação do texto (pura, testada em test_life.js) ================= */
const quickPlain = text => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const quickIso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const quickAddDays = (iso, n) => { const d = new Date(iso + 'T12:00:00'); d.setDate(d.getDate() + n); return quickIso(d); };
const quickWord = (source, flags = 'iu') => new RegExp(`(?<![\\p{L}\\d])(?:${source})(?![\\p{L}\\d])`, flags);
const QUICK_WEEKDAYS = {domingo: 0, segunda: 1, terca: 2, quarta: 3, quinta: 4, sexta: 5, sabado: 6};
const QUICK_FINANCE = /\b(pagar|paguei|pago|conta|boleto|fatura|gastei|gasto|comprei|compra|recebi|receber|salario|aporte|aportei|investi|investir|apliquei|aplicar|resgate|resgatei|rendimento|dividendo|dividendos|proventos?|mercado|uber|ifood|aluguel|pix|reais)\b/;
const QUICK_CARDIO = /\b(corrida|correr|caminhada|caminhar|bike|bicicleta|esteira|natacao|eliptico|pedal|cardio|remo|escada|spinning)\b/;

function quickParse(text, today) {
    const raw = String(text || '').trim();
    const base = {type: '', title: '', day: '', time: '', amount: '', kind: 'expense', status: '', priority: 'Média', exercises: [], cardio: [], body: ''};
    if (!raw) return base;
    const note = raw.match(/^(nota|ideia|anotar|anotacao|anotação|obs)\s*[:\-–]\s*/i);
    if (note) {
        const body = raw.slice(note[0].length).trim();
        return {...base, type: 'note', title: (body.split('\n')[0] || 'Nota rápida').slice(0, 80), body};
    }
    let rest = raw;
    const remove = pattern => { rest = rest.replace(pattern, ' '); };
    const plain = quickPlain(raw);
    // Treino: "supino 4x10 60kg, agachamento 3x12 80kg" ou "corrida 30min 5km".
    const exercises = [], cardio = [];
    for (const part of raw.split(/[;+]|,(?!\d)|\be\b(?=\s+[a-zà-ú]+\s+\d+\s*[x×])/i)) {
        const strength = part.match(/^\s*(?:treino\s*:?\s*)?([a-zà-ú][a-zà-ú\s\-]*?)\s+(\d{1,2})\s*[x×]\s*(\d{1,3})(?:\s*(?:com|de|@)?\s*(\d+(?:[.,]\d+)?)\s*kg)?\s*$/i);
        if (strength) {
            exercises.push({name: strength[1].trim().replace(/^./, c => c.toUpperCase()), sets: Number(strength[2]), reps: Number(strength[3]), weight: strength[4] ? Number(strength[4].replace(',', '.')) : 0});
            continue;
        }
        const partPlain = quickPlain(part);
        const minutes = partPlain.match(/(\d+(?:[.,]\d+)?)\s*(?:min|minutos?)\b/);
        const sport = partPlain.match(QUICK_CARDIO);
        if (minutes && sport) {
            const km = partPlain.match(/(\d+(?:[.,]\d+)?)\s*km\b/);
            const name = part.trim().split(/\s+\d/)[0].trim();
            cardio.push({name: (name || sport[1]).replace(/^./, c => c.toUpperCase()), minutes: Number(minutes[1].replace(',', '.')), distance_km: km ? Number(km[1].replace(',', '.')) : ''});
        }
    }
    if (exercises.length || cardio.length) {
        const label = raw.match(/^treino\s+([^:]+):/i);
        return {...base, type: 'workout', title: label ? `Treino ${label[1].trim()}` : 'Treino rápido', day: today, exercises, cardio};
    }
    // Datas e horários.
    let day = '';
    const lowerRest = () => quickPlain(rest);
    if (/\bdepois de amanha\b/.test(plain)) { day = quickAddDays(today, 2); remove(quickWord('depois de amanh[ãa]')); }
    else if (/\bamanha\b/.test(plain)) { day = quickAddDays(today, 1); remove(quickWord('amanh[ãa]')); }
    else if (/\bhoje\b/.test(plain)) { day = today; remove(quickWord('hoje')); }
    else if (/\bontem\b/.test(plain)) { day = quickAddDays(today, -1); remove(quickWord('ontem')); }
    const full = rest.match(/\b(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?\b/);
    if (!day && full) {
        const year = full[3] ? (full[3].length === 2 ? 2000 + Number(full[3]) : Number(full[3])) : Number(today.slice(0, 4));
        let candidate = `${year}-${String(full[2]).padStart(2, '0')}-${String(full[1]).padStart(2, '0')}`;
        if (!full[3] && candidate < today && quickAddDays(candidate, 0) === candidate) candidate = `${year + 1}${candidate.slice(4)}`;
        if (quickAddDays(candidate, 0) === candidate) { day = candidate; remove(full[0]); }
    }
    const dayOf = rest.match(/\b(?:no\s+)?dia\s+(\d{1,2})\b/i);
    if (!day && dayOf) {
        const n = Number(dayOf[1]);
        if (n >= 1 && n <= 31) {
            let [y, m] = today.split('-').map(Number);
            if (n < Number(today.slice(8))) { m += 1; if (m > 12) { m = 1; y += 1; } }
            const last = new Date(y, m, 0).getDate();
            day = `${y}-${String(m).padStart(2, '0')}-${String(Math.min(n, last)).padStart(2, '0')}`;
            remove(dayOf[0]);
        }
    }
    if (!day) {
        const weekday = lowerRest().match(/\b(?:na |no |proxim[ao] )?(domingo|segunda|terca|quarta|quinta|sexta|sabado)(?:-feira)?\b/);
        if (weekday) {
            const current = new Date(today + 'T12:00:00').getDay();
            const target = QUICK_WEEKDAYS[weekday[1]];
            day = quickAddDays(today, (target - current + 7) % 7);
            remove(quickWord(`(?:na |no |pr[óo]xim[ao] )?${weekday[1].replace('a', '[aá]').replace('c', '[cç]')}(?:-feira)?`));
        }
    }
    let time = '';
    const clock = rest.match(/(?<![\p{L}\d])(?:[àa]s?\s+)?(\d{1,2})(?::(\d{2})|h(\d{2})?)(?![\p{L}\d])(?!\s*(?:kg|km|min))/iu);
    if (clock && Number(clock[1]) <= 23) {
        const minutes = clock[2] || clock[3] || '00';
        if (Number(minutes) <= 59) { time = `${String(clock[1]).padStart(2, '0')}:${minutes}`; remove(clock[0]); }
    }
    // Prioridade.
    let priority = 'Média';
    if (/\b(urgente|importante|prioridade)\b|!{1,}\s*$/.test(plain)) { priority = 'Alta'; remove(quickWord('urgente|importante|prioridade', 'giu')); remove(/!+\s*$/); }
    // Dinheiro.
    let amount = '';
    const currency = rest.match(/r\$\s*(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)/i);
    const decimal = rest.match(/\b(\d{1,3}(?:\.\d{3})+,\d{1,2}|\d+,\d{1,2})\b/);
    const reais = rest.match(/\b(\d+(?:[.,]\d{1,2})?)\s*reais\b/i);
    const financeWords = QUICK_FINANCE.test(quickPlain(rest));
    const bare = financeWords ? rest.match(/\b(\d+(?:[.,]\d{1,2})?)\b/) : null;
    const money = currency || reais || decimal || bare;
    if (money) { amount = money[1]; remove(money[0]); }
    rest = rest.replace(/\breais\b/gi, ' ');
    const title = rest.replace(/\s+/g, ' ').replace(/^[\s,.;:–-]+|[\s,.;:–-]+$/g, '').replace(/\s+(?:as|às|no|na|em|de|para)$/i, '').trim();
    const finalTitle = title ? title[0].toUpperCase() + title.slice(1) : '';
    if (amount && (financeWords || currency || reais)) {
        const words = quickPlain(raw);
        const kind = /\b(recebi|receber|salario|entrada|pix recebido)\b/.test(words) ? 'income'
            : /\b(aporte|aportei|investi|investir|aplicar|apliquei)\b/.test(words) ? 'investment'
            : /\b(resgate|resgatei)\b/.test(words) ? 'redemption'
            : /\b(rendimento|dividendos?|proventos?)\b/.test(words) ? 'yield' : 'expense';
        const finalDay = day || today;
        const past = /\b(paguei|pago|gastei|comprei|recebi|aportei|investi|apliquei|resgatei)\b/.test(words);
        const future = /\b(pagar|receber|vence|vencimento|boleto|fatura|conta)\b/.test(words);
        const status = finalDay > today ? 'pending' : past ? 'paid' : future ? 'pending' : 'paid';
        return {...base, type: 'finance', title: finalTitle || 'Lançamento rápido', day: finalDay, amount, kind, status};
    }
    return {...base, type: 'task', title: finalTitle || raw, day, time, priority};
}

/* ================= Captura rápida: diálogo ================= */
let quickDraft = null;
function openQuickCapture() {
    if (!state) return;
    if (!$('#quick-dialog')) setupQuickDialog();
    quickDraft = null;
    $('#quick-input').value = '';
    $('#quick-error').textContent = '';
    drawQuickPreview();
    $('#quick-dialog').showModal();
    $('#quick-input').focus();
}
function setupQuickDialog() {
    document.body.insertAdjacentHTML('beforeend', `<dialog id="quick-dialog" aria-labelledby="quick-title"><form id="quick-form"><div class="modal-head"><div><p class="eyebrow">CAPTURA RÁPIDA · TECLA Q</p><h2 id="quick-title">O que você quer registrar?</h2></div><button type="button" class="icon" data-qclose aria-label="Fechar">×</button></div><input id="quick-input" autocomplete="off" maxlength="500" placeholder="Ex.: pagar luz 180 dia 15 · supino 4x10 60kg · reunião sexta 14h · nota: ideia…"><div class="quick-examples"><button type="button" data-qexample="Pagar internet 120 dia 10">Conta</button><button type="button" data-qexample="Ligar para o dentista amanhã 9h">Tarefa</button><button type="button" data-qexample="Supino 4x10 60kg, remada 3x12 40kg">Treino</button><button type="button" data-qexample="Gastei 45,90 no mercado">Gasto</button><button type="button" data-qexample="Nota: ideia para o fim de semana">Nota</button></div><div id="quick-preview" aria-live="polite"></div><p class="error" id="quick-error" role="alert"></p><div class="modal-actions"><button type="button" class="secondary" data-qclose>Cancelar</button><button type="submit" class="primary" id="quick-save">Salvar</button></div></form></dialog>`);
    const dialog = $('#quick-dialog');
    $('#quick-input').addEventListener('input', () => { quickDraft = null; drawQuickPreview(); });
    dialog.addEventListener('click', e => {
        if (e.target.closest('[data-qclose]')) { dialog.close(); return; }
        const example = e.target.closest('[data-qexample]');
        if (example) { $('#quick-input').value = example.dataset.qexample; quickDraft = null; drawQuickPreview(); $('#quick-input').focus(); return; }
        const type = e.target.closest('[data-qtype]');
        if (type) { readQuickFields(); quickDraft.type = type.dataset.qtype; drawQuickPreview(true); }
    });
    dialog.addEventListener('input', e => { if (e.target.closest('#quick-preview')) readQuickFields(); });
    $('#quick-form').onsubmit = async e => { e.preventDefault(); await saveQuick(); };
}
function drawQuickPreview(keep = false) {
    const text = $('#quick-input').value;
    if (!keep || !quickDraft) quickDraft = quickParse(text, state.today);
    const d = quickDraft, box = $('#quick-preview');
    $('#quick-save').disabled = !d.type;
    if (!d.type) { box.innerHTML = '<p class="hint">Escreva como você falaria. O app identifica se é tarefa, conta, gasto, treino ou nota; você pode corrigir antes de salvar.</p>'; return; }
    const types = [['task', 'Tarefa'], ['finance', 'Lançamento'], ['workout', 'Treino'], ['note', 'Nota']];
    const tabs = `<div class="segmented quick-types" role="group" aria-label="Tipo do registro">${types.map(([v, t]) => `<button type="button" data-qtype="${v}" class="${d.type === v ? 'selected' : ''}" aria-pressed="${d.type === v}">${t}</button>`).join('')}</div>`;
    let fields = '';
    if (d.type === 'task') fields = `<div class="quick-grid"><label class="wide">Tarefa<input data-q="title" maxlength="200" value="${esc(d.title)}"></label><label>Prazo<input data-q="day" type="date" value="${esc(d.day)}"></label><label>Horário<input data-q="time" type="time" value="${esc(d.time)}"></label><label>Prioridade<select data-q="priority">${['Baixa', 'Média', 'Alta'].map(p => `<option ${p === d.priority ? 'selected' : ''}>${p}</option>`).join('')}</select></label></div>`;
    if (d.type === 'finance') fields = `<div class="quick-grid"><label class="wide">Descrição<input data-q="title" maxlength="200" value="${esc(d.title)}"></label><label>Tipo<select data-q="kind">${Object.entries(financeKinds).map(([v, t]) => `<option value="${v}" ${v === d.kind ? 'selected' : ''}>${t}</option>`).join('')}</select></label><label>Valor (R$)<input data-q="amount" inputmode="decimal" value="${esc(d.amount)}"></label><label>Data<input data-q="day" type="date" value="${esc(d.day || state.today)}"></label><label>Situação<select data-q="status"><option value="paid" ${d.status !== 'pending' ? 'selected' : ''}>Efetivado</option><option value="pending" ${d.status === 'pending' ? 'selected' : ''}>Previsto</option></select></label></div><p class="hint">A categoria é sugerida pelo seu histórico e pode ser mudada depois em Finanças.</p>`;
    if (d.type === 'workout') fields = d.exercises.length || d.cardio.length ? `<div class="quick-workout"><strong>${esc(d.title)} · hoje</strong>${d.exercises.map(e => `<span>${esc(e.name)}: ${e.sets} × ${e.reps}${e.weight ? ` · ${String(e.weight).replace('.', ',')} kg` : ' · peso corporal'}</span>`).join('')}${d.cardio.map(c => `<span>${esc(c.name)}: ${String(c.minutes).replace('.', ',')} min${c.distance_km ? ` · ${String(c.distance_km).replace('.', ',')} km` : ''}</span>`).join('')}</div>` : '<p class="hint">Para treino, use o formato <strong>supino 4x10 60kg</strong> ou <strong>corrida 30min 5km</strong>. Separe exercícios por vírgula.</p>';
    if (d.type === 'note') fields = `<label>Título<input data-q="title" maxlength="200" value="${esc(d.title || text.slice(0, 80))}"></label><label>Texto<textarea data-q="body" maxlength="30000">${esc(d.body || text)}</textarea></label>`;
    box.innerHTML = `<p class="quick-label">Entendi como:</p>${tabs}${fields}`;
}
function readQuickFields() {
    if (!quickDraft) return;
    document.querySelectorAll('#quick-preview [data-q]').forEach(el => { quickDraft[el.dataset.q] = el.value; });
}
async function saveQuick() {
    readQuickFields();
    const d = quickDraft, button = $('#quick-save');
    if (!d?.type) return;
    button.disabled = true;
    try {
        let message = 'Registrado.';
        if (d.type === 'task') {
            await call('save', 'tasks', {title: d.title, due: d.day, scheduled_time: d.time, priority: d.priority, status: 'A fazer', notes: '', project_id: '', estimate_minutes: 0});
            message = d.day ? `Tarefa criada para ${fmt(d.day)}.` : 'Tarefa criada sem prazo.';
        } else if (d.type === 'finance') {
            const status = d.day > state.today ? 'pending' : d.status;
            await call('save_transaction', {title: d.title, kind: d.kind, amount: d.amount, day: d.day || state.today, status, category: '', auto_category: true,
                account: '', asset: ['investment', 'redemption', 'yield'].includes(d.kind) ? d.title : '', notes: ''});
            message = `${financeKinds[d.kind]} de R$ ${d.amount} ${status === 'pending' ? 'prevista' : 'registrada'}.`;
        } else if (d.type === 'workout') {
            if (!d.exercises.length && !d.cardio.length) throw new Error('Não encontrei exercícios. Use o formato supino 4x10 60kg.');
            await call('save_workout', {title: d.title, day: state.today, notes: 'Registrado pela captura rápida.', client_id: quickId(),
                exercises: d.exercises.map(e => ({name: e.name, notes: '', sets: Array.from({length: e.sets}, () => ({weight: e.weight, reps: e.reps}))})),
                cardio: d.cardio.map(c => ({name: c.name, minutes: c.minutes, distance_km: c.distance_km, notes: ''}))});
            message = 'Treino registrado.';
        } else {
            await call('save_productivity', 'notes', {title: d.title || 'Nota rápida', body: d.body, pinned: 0});
            message = 'Nota guardada.';
        }
        $('#quick-dialog').close();
        await afterMutation({}, d.type === 'task', message);
    } catch (err) { $('#quick-error').textContent = err.message; }
    finally { button.disabled = false; }
}
const quickId = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), n => n.toString(16).padStart(2, '0')).join('');

/* ================= Lembretes ================= */
async function checkReminders(force = false) {
    if (!state || (!force && Date.now() - lifeLastReminderCheck < 60000)) return;
    lifeLastReminderCheck = Date.now();
    try {
        const result = await call('reminders');
        lifeReminders = result.items || [];
        lifeSettings = result.settings || lifeSettings;
        updateReminderBadge();
        notifyNewReminders();
    } catch { /* Sem conexão: tenta de novo no próximo ciclo. */ }
}
function updateReminderBadge() {
    for (const badge of [$('#reminder-count')]) {
        if (!badge) continue;
        badge.textContent = lifeReminders.length;
        badge.hidden = !lifeReminders.length;
    }
    $('#reminders-button')?.setAttribute('aria-label', `Lembretes: ${lifeReminders.length}`);
}
function notifyNewReminders() {
    if (!lifeSettings || lifeSettings.system_notifications !== '1') return;
    const today = state.today, stored = localRead('holy-notified', {});
    const seen = stored.day === today ? new Set(stored.keys) : new Set();
    const fresh = lifeReminders.filter(r => !seen.has(r.key));
    if (!fresh.length) return;
    fresh.forEach(r => seen.add(r.key));
    localWrite('holy-notified', {day: today, keys: [...seen]});
    const title = fresh.length === 1 ? fresh[0].title : `${fresh.length} lembretes do Holy Planner`;
    const body = fresh.length === 1 ? fresh[0].detail : fresh.slice(0, 3).map(r => r.title).join(' · ');
    if (!window.holyWeb) { call('notify', title, body).catch(() => {}); return; }
    try { if ('Notification' in window && Notification.permission === 'granted') new Notification(title, {body, icon: '/icon-192.png', tag: 'holy-reminders'}); }
    catch { /* Alguns navegadores só notificam pela PWA instalada. */ }
}
async function openReminders() {
    if (!$('#reminder-dialog')) setupReminderDialog();
    await checkReminders(true);
    let settings = {};
    try { settings = await call('app_settings'); } catch (err) { toast(err.message); }
    const canBrowser = window.holyWeb && 'Notification' in window;
    $('#reminder-list').innerHTML = lifeReminders.map(r => `<article class="reminder-item reminder-${r.kind}"><span>${uiIcon({tasks: 'checkSquare', routines: 'repeat', finance: 'dollar', planning: 'trend', review: 'calendar', journal: 'heart'}[r.kind] || 'bell')}</span><div><strong>${esc(r.title)}</strong><small>${esc(r.detail)}</small></div><button class="secondary" data-rgo="${r.page}">Abrir</button></article>`).join('')
        || '<div class="empty"><strong>Tudo em dia.</strong>Nenhum lembrete agora.</div>';
    $('#reminder-settings').innerHTML = `<h3>Lembretes</h3><label class="plan-check"><input type="checkbox" id="rs-enabled" ${settings.reminders_enabled ? 'checked' : ''}>Mostrar lembretes</label><label>Lembrar rotinas e diário a partir de<select id="rs-hour">${Array.from({length: 24}, (_, h) => `<option value="${h}" ${h === settings.reminder_hour ? 'selected' : ''}>${String(h).padStart(2, '0')}:00</option>`).join('')}</select></label><label class="plan-check"><input type="checkbox" id="rs-system" ${settings.system_notifications ? 'checked' : ''}>${window.holyWeb ? 'Notificar neste aparelho' : 'Notificações do Windows'}</label>${canBrowser ? `<button type="button" class="secondary" id="rs-permission" ${Notification.permission === 'granted' ? 'disabled' : ''}>${Notification.permission === 'granted' ? 'Notificações permitidas neste navegador' : 'Permitir notificações neste navegador'}</button>` : ''}${!window.holyWeb && settings.autostart_available ? `<label class="plan-check"><input type="checkbox" id="rs-autostart" ${settings.autostart ? 'checked' : ''}>Abrir o Holy Planner ao ligar o computador</label>` : ''}<p class="hint">As notificações aparecem enquanto o Holy Planner estiver aberto (pode ficar minimizado). ${!window.holyWeb ? 'Abrir ao ligar o computador garante os lembretes do dia.' : 'No celular, mantenha a página aberta ou instale como app com HTTPS.'}</p>`;
    $('#reminder-dialog').showModal();
}
function setupReminderDialog() {
    document.body.insertAdjacentHTML('beforeend', `<dialog id="reminder-dialog" aria-labelledby="reminder-title"><div class="modal-head"><div><p class="eyebrow">AGORA</p><h2 id="reminder-title">Seus lembretes</h2></div><button class="icon" data-rclose aria-label="Fechar">×</button></div><div id="reminder-list"></div><div id="reminder-settings" class="reminder-settings"></div><div class="modal-actions"><button class="primary" data-rclose>Fechar</button></div></dialog>`);
    const dialog = $('#reminder-dialog');
    dialog.addEventListener('click', async e => {
        if (e.target.closest('[data-rclose]')) { dialog.close(); return; }
        const go = e.target.closest('[data-rgo]');
        if (go) { dialog.close(); navigatePage(go.dataset.rgo); return; }
        if (e.target.id === 'rs-permission') {
            try { await Notification.requestPermission(); } catch { /* recusado */ }
            openReminders();
        }
    });
    dialog.addEventListener('change', async e => {
        try {
            if (e.target.id === 'rs-autostart') { await call('set_autostart', e.target.checked); toast(e.target.checked ? 'O Holy Planner vai abrir ao ligar o computador.' : 'Abertura automática desligada.'); return; }
            const payload = {};
            if (e.target.id === 'rs-enabled') payload.reminders_enabled = e.target.checked;
            if (e.target.id === 'rs-system') payload.system_notifications = e.target.checked;
            if (e.target.id === 'rs-hour') payload.reminder_hour = Number(e.target.value);
            if (Object.keys(payload).length) { await call('save_app_settings', payload); await checkReminders(true); toast('Preferência salva.'); }
        } catch (err) { toast(err.message); }
    });
}

/* ================= Meu dia: diário rápido e quanto posso gastar ================= */
function renderTodayExtras() {
    const j = state.journal_today, m = state.money_today;
    const mood = `<section class="panel today-journal"><div><span class="eyebrow">DIÁRIO</span><h2>Como você está hoje?</h2></div><div class="mood-row" role="group" aria-label="Humor de hoje">${[1, 2, 3, 4, 5].map(n => `<button class="mood-button ${j?.mood === n ? 'selected' : ''}" data-action="life-mood" data-mood="${n}" aria-pressed="${j?.mood === n}" title="${lifeMoodLabels[n]}"><strong>${n}</strong><small>${lifeMoodLabels[n]}</small></button>`).join('')}</div><button class="text-button" data-action="prod-page" data-page="journal">${j ? 'Completar diário' : 'Abrir diário'} <span>↗</span></button></section>`;
    if (!m) return `<div class="today-extras single">${mood}</div>`;
    const negative = m.allowance_cents != null && m.allowance_cents < 0;
    return `<div class="today-extras">${mood}<section class="panel today-money"><div><span class="eyebrow">FINANÇAS DO MÊS</span><h2>Para gastar por dia</h2></div><strong class="${negative ? 'cash-out' : ''}">${m.allowance_cents == null ? '—' : money(m.allowance_cents)}</strong><small>${negative ? 'Os previstos do mês passam do saldo. Reveja saídas ou adie algo.' : `Até o fim do mês (${m.days_left} dia${m.days_left === 1 ? '' : 's'}), já descontados ${money(m.pending_out_cents)} de contas e aportes previstos.`}</small><button class="text-button" data-action="prod-page" data-page="finance">Ver finanças <span>↗</span></button></section></div>`;
}

/* ================= Revisão semanal ================= */
const lifeWeekdays = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
function renderReview() {
    const r = reviewState;
    if (!r) return empty('Carregando sua semana…', '');
    if (reviewDraft && $('[data-review]')) readReviewForm();
    if (!reviewDraft || reviewDraft.week !== r.week) reviewDraft = {week: r.week, wins: r.review.wins, lessons: r.review.lessons, priorities: [...r.review.priorities, '', '', ''].slice(0, 3), plan: {}};
    const routinePct = r.routines.scheduled ? Math.round(r.routines.done / r.routines.scheduled * 100) : null;
    const nextDays = Array.from({length: 7}, (_, i) => shiftDay(r.next_week, i));
    const toPlan = [...r.tasks_missed.map(t => ({...t, late: true})), ...r.undated];
    const option = (task) => `<select data-review-task="${task.id}" aria-label="Novo dia para ${esc(task.title)}"><option value="">${task.late ? `Manter (${fmt(task.due)})` : 'Sem data'}</option>${nextDays.map((d, i) => `<option value="${d}" ${reviewDraft.plan[task.id] === d ? 'selected' : ''}>${lifeWeekdays[i]} ${smallDate(d)}</option>`).join('')}</select>`;
    const stat = (icon, label, value, detail, color) => overviewStat(icon, label, value, detail, color);
    return `<div class="review-head"><div><span class="eyebrow">REVISÃO SEMANAL</span><h2>${smallDate(r.week)} — ${smallDate(r.end)}</h2><p>${r.review.updated ? `Revisão salva em ${new Date(r.review.updated).toLocaleDateString('pt-BR')}.` : 'Uns 10 minutos para olhar para trás e preparar a próxima semana.'}</p></div><div class="week-controls"><button class="secondary" data-action="life-review-week" data-step="0">Semana atual</button><button class="secondary" data-action="life-review-week" data-step="-1" aria-label="Semana anterior">←</button><button class="secondary" data-action="life-review-week" data-step="1" aria-label="Próxima semana">→</button></div></div>
    <section class="review-step"><div class="review-step-title"><span>1</span><h3>Como foi a semana</h3></div>
    <div class="overview-stats">${stat('checkSquare', 'Tarefas concluídas', r.tasks_done.length, r.tasks_missed.length ? `${r.tasks_missed.length} atrasada(s)` : 'Nenhuma atrasada', 'lavender')}${stat('repeat', 'Rotinas cumpridas', routinePct == null ? '—' : `${routinePct}%`, `${r.routines.done} de ${r.routines.scheduled} programadas`, 'mint')}${stat('clock', 'Foco', minuteLabel(r.focus_minutes), `${r.focus_sessions} sessão(ões)`, 'peach')}${stat('dumbbell', 'Treinos', r.workouts, r.cardio_minutes ? `${r.cardio_minutes} min de cardio` : 'Sessões registradas', 'blue')}</div>
    <div class="review-grid"><article class="panel review-card"><h4>Concluído</h4>${r.tasks_done.slice(0, 8).map(t => `<p>${uiIcon('check')}${esc(t.title)}</p>`).join('') || '<p class="hint">Nenhuma tarefa concluída nesta semana.</p>'}${r.tasks_done.length > 8 ? `<p class="hint">+ ${r.tasks_done.length - 8} outras</p>` : ''}</article>
    <article class="panel review-card"><h4>Dinheiro</h4><dl><div><dt>Entradas</dt><dd class="cash-in">${money(r.money.income)}</dd></div><div><dt>Saídas</dt><dd class="cash-out">${money(r.money.expense)}</dd></div><div><dt>Investido (líquido)</dt><dd>${money(r.money.invested)}</dd></div></dl>${r.money.categories.length ? `<p class="hint">Maiores gastos: ${r.money.categories.map(c => `${esc(c.category)} ${money(c.total)}`).join(' · ')}</p>` : ''}</article>
    <article class="panel review-card"><h4>Bem-estar</h4>${r.journal.days ? `<dl><div><dt>Humor médio</dt><dd>${String(r.journal.mood ?? '—').replace('.', ',')} de 5</dd></div><div><dt>Energia média</dt><dd>${String(r.journal.energy ?? '—').replace('.', ',')} de 5</dd></div><div><dt>Sono médio</dt><dd>${r.journal.sleep == null ? '—' : String(r.journal.sleep).replace('.', ',') + ' h'}</dd></div></dl><p class="hint">${r.journal.days} dia(s) registrados no diário.</p>` : '<p class="hint">Sem registros no diário nesta semana. Use o cartão de humor no Meu dia.</p>'}${r.routines.items.length ? `<h4>Rotinas</h4>${r.routines.items.map(i => `<p class="review-routine"><span>${esc(i.title)}</span><b>${i.done}/${i.scheduled}</b></p>`).join('')}` : ''}</article></div></section>
    <section class="review-step"><div class="review-step-title"><span>2</span><h3>Reflexão</h3></div><div class="review-reflection"><label>O que deu certo?<textarea data-review="wins" maxlength="5000" placeholder="Pequenas vitórias também contam.">${esc(reviewDraft.wins)}</textarea></label><label>O que aprendi ou quero mudar?<textarea data-review="lessons" maxlength="5000" placeholder="Um ajuste para a próxima semana.">${esc(reviewDraft.lessons)}</textarea></label></div></section>
    <section class="review-step"><div class="review-step-title"><span>3</span><h3>Próxima semana · ${smallDate(r.next_week)} a ${smallDate(r.next_end)}</h3></div>
    <div class="review-plan"><div class="panel review-card"><h4>Três prioridades</h4>${[0, 1, 2].map(i => `<label class="review-priority"><span>${i + 1}</span><input data-review-priority="${i}" maxlength="200" value="${esc(reviewDraft.priorities[i])}" placeholder="${['O que mais importa?', 'E depois?', 'Uma terceira, se couber'][i]}"></label>`).join('')}</div>
    <div class="panel review-card"><h4>Distribuir tarefas</h4>${toPlan.length ? `<p class="hint">Escolha um dia para as tarefas atrasadas e sem data.</p>${toPlan.slice(0, 25).map(t => `<div class="review-task"><span><strong>${esc(t.title)}</strong><small>${t.late ? `<b class="late">Atrasada</b> · ${fmt(t.due)}` : 'Sem data'}${t.priority === 'Alta' ? ' · Alta' : ''}</small></span>${option(t)}</div>`).join('')}` : '<p class="hint">Nada pendente sem data. 🎉</p>'}</div>
    <div class="panel review-card"><h4>Já marcado</h4>${r.upcoming.slice(0, 8).map(t => `<p>${uiIcon('calendar')}${smallDate(t.due)} · ${esc(t.title)}</p>`).join('') || '<p class="hint">Nenhuma tarefa com prazo na próxima semana.</p>'}${r.bills.length ? `<h4>Contas previstas</h4>${r.bills.map(b => `<p>${uiIcon('dollar')}${smallDate(b.day)} · ${esc(b.title)} · ${money(b.amount_cents)}</p>`).join('')}` : ''}</div></div></section>
    <div class="review-save"><button class="primary" data-action="life-review-save">${uiIcon('check')}Salvar revisão e plano</button><p class="hint">As tarefas recebem os dias escolhidos e as prioridades ficam registradas nesta revisão.</p></div>`;
}
function readReviewForm() {
    if (!reviewDraft) return;
    document.querySelectorAll('[data-review]').forEach(el => { reviewDraft[el.dataset.review] = el.value; });
    document.querySelectorAll('[data-review-priority]').forEach(el => { reviewDraft.priorities[Number(el.dataset.reviewPriority)] = el.value; });
    document.querySelectorAll('[data-review-task]').forEach(el => { if (el.value) reviewDraft.plan[el.dataset.reviewTask] = el.value; else delete reviewDraft.plan[el.dataset.reviewTask]; });
}
async function saveReview(button) {
    readReviewForm();
    button.disabled = true;
    try {
        await call('save_review', {week: reviewDraft.week, wins: reviewDraft.wins, lessons: reviewDraft.lessons, priorities: reviewDraft.priorities});
        const plan = Object.entries(reviewDraft.plan).map(([id, due]) => ({id: Number(id), due}));
        const result = plan.length ? await call('schedule_tasks', plan) : {};
        reviewDraft.plan = {};
        await afterMutation(result, plan.length > 0, plan.length ? `Revisão salva e ${plan.length} tarefa(s) planejada(s).` : 'Revisão salva.');
        checkReminders(true);
    } catch (err) { toast(err.message); }
    finally { button.disabled = false; }
}

/* ================= Diário ================= */
function renderJournal() {
    const s = journalState;
    if (!s) return empty('Carregando seu diário…', '');
    if (journalDraft && $('#journal-note')) readJournalForm();
    const day = journalDraft?.day || s.today;
    const entry = journalDraft || s.entries.find(e => e.day === day) || {day, mood: null, energy: null, sleep: null, note: ''};
    journalDraft = {...entry};
    const scale = (key, labels) => `<div class="mood-row" role="group" aria-label="${key === 'mood' ? 'Humor' : 'Energia'}">${[1, 2, 3, 4, 5].map(n => `<button type="button" class="mood-button ${entry[key] === n ? 'selected' : ''}" data-action="life-journal-pick" data-key="${key}" data-value="${n}" aria-pressed="${entry[key] === n}"><strong>${n}</strong><small>${labels[n]}</small></button>`).join('')}</div>`;
    const recent = [...s.entries].slice(0, 30).reverse();
    return `<div class="journal-layout"><section class="panel journal-form"><div class="section-head"><div><span class="eyebrow">UM MINUTO POR DIA</span><h2>${day === s.today ? 'Como foi hoje?' : `Diário de ${fmt(day)}`}</h2></div><label class="journal-day">Data<input type="date" id="journal-day" max="${s.today}" value="${day}"></label></div>
    <h3>Humor</h3>${scale('mood', lifeMoodLabels)}<h3>Energia</h3>${scale('energy', lifeEnergyLabels)}
    <div class="journal-row"><label>Horas de sono<input id="journal-sleep" inputmode="decimal" maxlength="4" placeholder="Ex.: 7,5" value="${entry.sleep == null ? '' : String(entry.sleep).replace('.', ',')}"></label></div>
    <label>Uma linha sobre o dia<textarea id="journal-note" maxlength="5000" placeholder="O que marcou o seu dia?">${esc(entry.note || '')}</textarea></label>
    <div class="journal-actions"><button class="primary" data-action="life-journal-save">Salvar diário</button>${s.entries.some(e => e.day === day) ? `<button class="text-button" data-action="life-journal-delete" data-day="${day}">Excluir este dia</button>` : ''}</div></section>
    <section class="panel journal-side"><div class="section-head"><div><span class="eyebrow">ÚLTIMOS 90 DIAS</span><h2>Seus padrões</h2></div></div><div class="journal-averages"><div><strong>${s.averages.mood == null ? '—' : String(s.averages.mood).replace('.', ',')}</strong><small>humor médio</small></div><div><strong>${s.averages.energy == null ? '—' : String(s.averages.energy).replace('.', ',')}</strong><small>energia média</small></div><div><strong>${s.averages.sleep == null ? '—' : String(s.averages.sleep).replace('.', ',') + ' h'}</strong><small>sono médio</small></div></div>
    ${journalChart(recent)}
    ${s.insights.length ? s.insights.map(i => { const diff = i.a_value - i.b_value; return `<article class="journal-insight"><strong>${esc(i.label)}</strong><div><span>${esc(i.a_label)}<b>${String(i.a_value).replace('.', ',')} ${i.unit}</b><small>${i.a_count} dias</small></span><span>${esc(i.b_label)}<b>${String(i.b_value).replace('.', ',')} ${i.unit}</b><small>${i.b_count} dias</small></span></div><p class="hint">${Math.abs(diff) < (i.unit === 'min' ? 5 : 0.3) ? 'Pouca diferença até agora.' : diff > 0 ? `Mais alto quando: ${esc(i.a_label.toLowerCase())}.` : `Mais alto quando: ${esc(i.b_label.toLowerCase())}.`}</p></article>`; }).join('') : '<p class="hint">Com alguns dias de registro (pelo menos 3 em cada situação), o diário mostra relações entre humor, sono, treinos, rotinas e foco.</p>'}
    <p class="hint">São comparações dos seus próprios registros, não conclusões médicas. Correlação não é causa.</p></section></div>
    <section class="panel journal-history"><div class="section-head"><div><span class="eyebrow">HISTÓRICO</span><h2>Dias registrados</h2></div></div>${s.entries.filter(e => `${e.note}`.toLocaleLowerCase().includes(query.toLocaleLowerCase())).slice(0, 60).map(e => `<button class="journal-entry" data-action="life-journal-open" data-day="${e.day}"><span class="journal-date">${fmt(e.day)}</span><span>Humor <b>${e.mood ?? '—'}</b></span><span>Energia <b>${e.energy ?? '—'}</b></span><span>Sono <b>${e.sleep == null ? '—' : String(e.sleep).replace('.', ',') + 'h'}</b></span>${e.workout ? '<span class="badge">Treino</span>' : ''}<small>${esc(e.note || '')}</small></button>`).join('') || empty('Seu diário começa hoje.', 'Escolha seu humor acima e salve.')}</section>`;
}
function journalChart(entries) {
    const points = entries.filter(e => e.mood != null || e.energy != null);
    if (points.length < 2) return '';
    const W = 420, H = 120, x = i => 10 + i / (points.length - 1) * (W - 20), y = v => H - 12 - (v - 1) / 4 * (H - 28);
    const line = key => points.map((p, i) => p[key] == null ? null : [x(i), y(p[key])]).filter(Boolean).map((pt, i) => `${i ? 'L' : 'M'}${pt[0].toFixed(1)},${pt[1].toFixed(1)}`).join('');
    return `<div class="journal-chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Humor e energia nos últimos ${points.length} registros">${[1, 3, 5].map(v => `<line x1="10" x2="${W - 10}" y1="${y(v)}" y2="${y(v)}" class="plan-grid"/>`).join('')}<path d="${line('energy')}" class="journal-energy"/><path d="${line('mood')}" class="journal-mood"/></svg><div class="plan-legend"><span class="plan-legend-item"><i class="plan-swatch journal-mood-swatch"></i>Humor</span><span class="plan-legend-item"><i class="plan-swatch journal-energy-swatch"></i>Energia</span></div></div>`;
}
function readJournalForm() {
    if (!journalDraft) return;
    journalDraft.sleep = $('#journal-sleep')?.value ?? journalDraft.sleep;
    journalDraft.note = $('#journal-note')?.value ?? journalDraft.note;
}

/* ================= Ações e eventos ================= */
function bindLifeEvents() {
    $('#journal-day')?.addEventListener('change', e => {
        if (!e.target.value) return;
        const found = journalState.entries.find(x => x.day === e.target.value);
        journalDraft = found ? {...found} : {day: e.target.value, mood: null, energy: null, sleep: null, note: ''};
        render();
    });
}
async function handleLifeAction(b) {
    const action = b.dataset.action;
    if (action === 'life-mood') {
        b.disabled = true;
        try { await call('save_journal', {day: state.today, mood: Number(b.dataset.mood)}); await refresh(); toast(`Humor registrado: ${lifeMoodLabels[b.dataset.mood]}.`); checkReminders(true); }
        catch (err) { toast(err.message); b.disabled = false; }
        return;
    }
    if (action === 'life-review-week') {
        readReviewForm();
        const step = Number(b.dataset.step);
        reviewWeek = step === 0 ? '' : shiftDay(reviewState.week, step * 7);
        reviewDraft = null;
        await refresh();
        return;
    }
    if (action === 'life-review-save') { await saveReview(b); return; }
    if (action === 'life-journal-pick') {
        readJournalForm();
        const value = Number(b.dataset.value);
        journalDraft[b.dataset.key] = journalDraft[b.dataset.key] === value ? null : value;
        render();
        return;
    }
    if (action === 'life-journal-open') {
        journalDraft = {...journalState.entries.find(e => e.day === b.dataset.day)};
        render();
        window.scrollTo({top: 0, behavior: 'smooth'});
        return;
    }
    if (action === 'life-journal-save') {
        readJournalForm();
        b.disabled = true;
        try {
            await call('save_journal', {day: journalDraft.day, mood: journalDraft.mood ?? '', energy: journalDraft.energy ?? '', sleep: journalDraft.sleep ?? '', note: journalDraft.note || ''});
            journalDraft = null;
            await afterMutation({}, false, 'Diário salvo.');
            checkReminders(true);
        } catch (err) { toast(err.message); b.disabled = false; }
        return;
    }
    if (action === 'life-journal-delete') {
        b.disabled = true;
        try { await call('delete_journal', b.dataset.day); journalDraft = null; await afterMutation({}, false, 'Dia removido do diário.'); }
        catch (err) { toast(err.message); b.disabled = false; }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    $('#quick-capture')?.addEventListener('click', openQuickCapture);
    $('#reminders-button')?.addEventListener('click', openReminders);
    document.querySelectorAll('.workspace-bar [data-icon]').forEach(el => { el.innerHTML = uiIcon(el.dataset.icon); });
    document.addEventListener('keydown', event => {
        if (typeof state === 'undefined' || !state || $('dialog[open]') || event.target.matches('input,textarea,select') || event.ctrlKey || event.metaKey || event.altKey) return;
        if (event.key.toLowerCase() === 'q') { event.preventDefault(); openQuickCapture(); }
    });
    lifeReminderTimer = setInterval(() => checkReminders(true), 5 * 60 * 1000);
});
