'use strict';
const $ = s => document.querySelector(s);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
} [c]));
const days = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'];
const names = {
    today: 'Meu dia', workouts: 'Meus treinos', planning: 'Planejar investimentos', review: 'Revisão semanal', journal: 'Diário',
    calendar: 'Calendário',
    projects: 'Projetos',
    tasks: 'Tarefas',
    routines: 'Rotinas',
    finance: 'Finanças', week: 'Minha semana', goals: 'Metas', focus: 'Modo foco', notes: 'Minhas notas'
};
const subtitles = {
    workouts: 'Cada série conta. Acompanhe sua constância e evolução.',
    planning: 'Veja o caminho até aqui e imagine os próximos anos.',
    review: 'Olhe para a semana que passou e prepare a próxima.',
    journal: 'Como você está? Pequenos registros mostram grandes padrões.',
    calendar: 'Encontre espaço para seus projetos e sua constância.',
    today: 'Menos ruído. Mais direção.',
    projects: 'Seus objetivos, divididos em passos possíveis.',
    tasks: 'Prioridades claras para tirar as ideias do papel.',
    routines: 'Pequenas ações. Uma constância que faz diferença.',
    finance: 'Clareza no presente. Espaço para o seu futuro.',
    week: 'Uma visão do todo. Um passo de cada vez.',
    goals: 'Transforme o que importa em progresso visível.',
    focus: 'Uma coisa de cada vez. Este tempo é seu.',
    notes: 'Libere a mente. Guarde suas ideias aqui.'
};
let state, page = 'today',
    query = '',
    filter = 'Todos',
    selectedDay = '',
    editing = null,
    pendingDelete = null,
    toastTimer;
let calendarMonth = '',
    calendarData = {},
    refreshVersion = 0;
const fmt = value => value ? value.split('-').reverse().join('/') : 'Sem prazo';

function toast(text) {
    $('#toast').textContent = text;
    $('#toast').hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => $('#toast').hidden = true, 6500);
}
async function call(method, ...args) {
    const result = await window.pywebview.api[method](...args);
    if (result?.ok === false) throw new Error(result.error);
    return result;
}
async function refresh() {
    const version = ++refreshVersion;
    const next = await call('snapshot', ['routines', 'calendar'].includes(page) ? (selectedDay || null) : null);
    const productivity = await call('productivity_snapshot');
    Object.assign(next, productivity);
    if (version !== refreshVersion) return;
    if (!selectedDay) selectedDay = next.today;
    if (!calendarMonth) calendarMonth = selectedDay.slice(0, 7);
    let monthData = {};
    let nextFinance;
    let nextWorkouts;
    let nextPlanning, nextReview, nextJournal;
    if (page === 'review') {
        nextReview = await call('review_snapshot', reviewWeek || null);
        if (version !== refreshVersion) return;
    }
    if (page === 'journal') {
        nextJournal = await call('journal_snapshot', 90);
        if (version !== refreshVersion) return;
    }
    if (page === 'planning') {
        nextPlanning = await call('planning_snapshot');
        if (version !== refreshVersion) return;
    }
    if (page === 'workouts') {
        nextWorkouts = await call('workouts_snapshot', workoutStart(next.today));
        if (version !== refreshVersion) return;
    }
    if (page === 'finance') {
        if (!financeMonth) financeMonth = next.today.slice(0, 7);
        nextFinance = await call('finance_snapshot', financeMonth);
        if (version !== refreshVersion) return;
    }
    if (page === 'calendar') {
        const [year, month] = calendarMonth.split('-').map(Number);
        monthData = await call('calendar_month', year, month);
        if (version !== refreshVersion) return;
    }
    state = next;
    if (nextWorkouts) workoutState = nextWorkouts;
    if (nextPlanning) planState = nextPlanning;
    if (nextReview) reviewState = nextReview;
    if (nextJournal) journalState = nextJournal;
    if (nextFinance) financeState = nextFinance;
    calendarData = monthData;
    $('#create').disabled = false;
    $('#date-label').textContent = new Date(state.today + 'T12:00:00').toLocaleDateString('pt-BR', {
        weekday: 'long',
        day: 'numeric',
        month: 'long'
    });
    render();
    renderGoogle(state.google);
    if (typeof checkReminders === 'function') checkReminders();
}

function actions(table, id) {
    return `<details class="row-menu"><summary aria-label="Ações do registro" title="Ações">${uiIcon('more')}</summary><div class="row-menu-items"><button data-action="edit" data-table="${table}" data-id="${id}">${uiIcon('edit')}Editar</button><button class="delete-action" data-action="delete" data-table="${table}" data-id="${id}">${uiIcon('trash')}Excluir</button></div></details>`;
}

function empty(title, detail) {
    return `<div class="empty"><strong>${title}</strong>${detail}</div>`;
}

function taskRow(t) {
    const done = t.status === 'Concluído',
        late = t.due && t.due < state.today && !done;
    return `<div class="task-row"><button class="check ${done?'done':''}" data-action="task" data-id="${t.id}" aria-label="${done?'Reabrir':'Concluir'} tarefa">${done?'✓':''}</button><div class="row-body"><div class="row-title ${done?'done-title':''}">${esc(t.title)}</div><div class="row-meta"><span>${esc(t.project)}</span><span class="${late?'late':''}">${late?'Atrasada · ':''}${fmt(t.due)}</span></div></div><span class="badge ${t.priority==='Alta'?'high':''}">${esc(t.priority)}</span><span class="badge ${t.status==='Em andamento'?'progress':''}">${esc(t.status)}</span>${actions('tasks',t.id)}</div>`;
}

function routineRow(r) {
    const icon = /água|agua|hidrata|beber/i.test(r.title) ? 'drop' : /ler|leitura|estud|livro/i.test(r.title) ? 'book' : /trein|academia|exerc|caminh/i.test(r.title) ? 'dumbbell' : 'repeat';
    const schedule = r.days.split(',').length === 7 ? 'Todos os dias' : r.days.split(',').map(d=>days[Number(d)]).join(', ');
    return `<div class="routine-row"><button class="check ${r.done?'done':''}" data-action="routine" data-id="${r.id}" aria-label="${r.done?'Desmarcar':'Concluir'} rotina: ${esc(r.title)}" ${!r.scheduled || state.day>state.today?'disabled':''}>${r.done?uiIcon('check'):''}</button><span class="routine-symbol">${uiIcon(icon)}</span><div class="row-body"><div class="row-title">${esc(r.title)}</div><div class="row-meta">${schedule}</div></div><span class="badge">${!r.scheduled?'Não programada':r.done?'Feita':'Pendente'}</span>${actions('routines',r.id)}</div>`;
}

function toolbar(extra = '') {
    return `<div class="toolbar"><input type="search" id="search" placeholder="Buscar por título…" aria-label="Buscar por título" value="${esc(query)}">${extra}</div>`;
}

function render() {
    $('#page-title').textContent = names[page];
    $('#subtitle').textContent = '';
    $('#breadcrumb').textContent = names[page];
    $('#create').innerHTML = uiIcon('plus') + (page === 'finance' ? 'Novo lançamento' : page === 'projects' ? 'Novo projeto' : page === 'routines' ? 'Nova rotina' : 'Nova tarefa');
    document.body.dataset.page = page;
    const googlePanel = $('.google-panel');
    $('#google-default').append(googlePanel);
    googlePanel.hidden = page !== 'calendar';
    $('#create').hidden = page === 'focus';
    if (page === 'workouts') $('#create').innerHTML = uiIcon('plus') + 'Registrar treino';
    if (page === 'planning') $('#create').innerHTML = uiIcon('plus') + 'Novo cenário';
    if (page === 'review' || page === 'journal') $('#create').innerHTML = uiIcon('bolt') + 'Captura rápida';
    if (page === 'goals' || page === 'notes') $('#create').innerHTML = uiIcon('plus') + (page === 'goals' ? 'Nova meta' : 'Nova nota');
    const searchValue = page === 'finance' ? financeQuery : query;
    if ($('#global-search').value !== searchValue) $('#global-search').value = searchValue;
    document.querySelectorAll('nav button').forEach(b => {
        b.classList.toggle('active', b.dataset.page === page);
        if (b.dataset.page === page) b.setAttribute('aria-current', 'page');
        else b.removeAttribute('aria-current');
    });
    const match = r => r.title.toLocaleLowerCase().includes(query.toLocaleLowerCase());
    let html = '';
    if (page === 'workouts') {
        html = renderWorkouts();
    } else if (page === 'planning') {
        html = renderPlanning();
    } else if (page === 'review') {
        html = renderReview();
    } else if (page === 'journal') {
        html = renderJournal();
    } else if (['week', 'goals', 'focus', 'notes'].includes(page)) {
        html = renderProductivity(page);
    } else if (page === 'finance') {
        html = renderFinance();
    } else if (page === 'calendar') {
        html = renderCalendar();
    } else if (page === 'today') {
        html = renderToday();
    } else if (page === 'projects') {
        const projects = state.projects.filter(match);
        html = toolbar() + `<div class="project-grid">${projects.map(p=>{const percent=p.total?Math.round(p.done/p.total*100):0;return `<article class="project"><div class="project-head"><h2>${esc(p.title)}</h2><div>${actions('projects',p.id)}</div></div><p>${esc(p.description || 'Um novo objetivo começa aqui.')}</p><span class="badge">${fmt(p.due)}</span><div class="progress-label"><span>${p.done} de ${p.total} tarefas concluídas</span><span>${percent}%</span></div><div class="track"><span style="width:${percent}%"></span></div></article>`;}).join('')}</div>` + (projects.length ? '' : empty('Espaço para suas próximas ideias.', 'Clique em Novo projeto para começar.'));
    } else if (page === 'tasks') {
        html = renderTaskBoard();
    } else {
        html = toolbar(`<label for="routine-date">Consultar data</label><input type="date" id="routine-date" value="${esc(selectedDay)}" aria-label="Data das rotinas">`) + `<div class="panel">${state.routines.filter(match).map(routineRow).join('')||empty('Consistência começa com uma ação.','Clique em Nova rotina para escolher seus dias.')}</div><p class="hint">Marcar uma ocorrência preserva os outros dias. Você pode corrigir registros passados desde a criação da rotina.</p>`;
    }
    $('#content').innerHTML = html;
    if (page === 'today') $('#google-slot').append(googlePanel);
    if (page === 'finance') bindFinanceEvents();
    bindProductivityEvents();
    if (page === 'workouts') bindWorkoutEvents();
    if (page === 'planning') bindPlanningEvents();
    if (page === 'review' || page === 'journal') bindLifeEvents();
    $('#search')?.addEventListener('input', e => {
        const start = e.target.selectionStart;
        query = e.target.value;
        render();
        $('#search').focus();
        $('#search').setSelectionRange(start, start);
    });
    $('#status-filter')?.addEventListener('change', e => {
        filter = e.target.value;
        render();
    });
    $('#routine-date')?.addEventListener('change', async e => {
        if (!e.target.value) return;
        selectedDay = e.target.value;
        try {
            await refresh();

        } catch (err) {
            toast(err.message);
        }
    });
}
const input = (label, name, value = '', type = 'text') => `<label>${label}<input name="${name}" type="${type}" value="${esc(value)}" ${name==='title'?'required maxlength="200"':''}></label>`;
const select = (label, name, options, current) => `<label>${label}<select name="${name}">${options.map(([v,t])=>`<option value="${esc(v)}" ${String(v)===String(current)?'selected':''}>${esc(t)}</option>`).join('')}</select></label>`;

function editor(table, id = null) {
    if (table === 'workouts') return workoutEditor(id);
    if (table === 'workout_templates') return workoutTemplateEditor(id);
    if (table === 'investment_scenarios') return planScenarioEditor(id);
    if (table === 'investment_snapshots') return planRecordEditor(id);
    if (['goals', 'notes'].includes(table)) return productivityEditor(table, id);
    if (table.startsWith('finance_')) return financeEditor(table, id);
    const r = id ? state[table].find(r => r.id === id) : (['today','calendar','week'].includes(page) && table === 'tasks' ? {
        due: page === 'today' ? state.today : selectedDay
    } : {});
    if (!r) return;
    editing = {
        table,
        id
    };
    $('#editor-title').textContent = (id ? 'Editar ' : 'Criar ') + ({
        tasks: 'tarefa',
        projects: 'projeto',
        routines: 'rotina'
    } [table]);
    let html = input('Título *', 'title', r.title);
    if (table === 'tasks') html += select('Projeto', 'project_id', [
        ['', 'Sem projeto'], ...state.projects.map(p => [p.id, p.title])
    ], r.project_id || '') + `<div class="form-grid">${select('Prioridade','priority',['Baixa','Média','Alta'].map(s=>[s,s]),r.priority||'Média')}${select('Status','status',['A fazer','Em andamento','Concluído'].map(s=>[s,s]),r.status||'A fazer')}</div>`;
    if (table === 'routines') {
        const chosen = (r.days || '0,1,2,3,4').split(',');
        html += `<label>Repetir nos dias *</label><div class="days">${days.map((d,i)=>`<label><input type="checkbox" name="days" value="${i}" ${chosen.includes(String(i))?'checked':''}><span>${d}</span></label>`).join('')}</div><label class="plan-check"><input type="checkbox" name="auto_workout" value="1" ${r.auto_workout?'checked':''}>Marcar automaticamente quando eu registrar um treino</label><p class="hint">As rotinas ficam somente neste aplicativo e não são enviadas ao Google Agenda. Editar os dias redefine a programação nas consultas. Os registros de conclusão existentes são preservados.</p>`;
    } else {
        const key = table === 'tasks' ? 'notes' : 'description';
        html += input('Prazo (opcional)', 'due', r.due, 'date') + `<label>Descrição / notas<textarea name="${key}" maxlength="10000">${esc(r[key])}</textarea></label>`;
        if (table === 'tasks') html += `<div class="form-grid">${input('Horário (opcional)', 'scheduled_time', r.scheduled_time, 'time')}<label>Estimativa (minutos)<input name="estimate_minutes" type="number" min="0" max="1440" step="1" value="${r.estimate_minutes || 0}"></label></div>`;
        if (table === 'tasks' && !id) html += `<details class="task-bill"><summary>${uiIcon('dollar')}É uma conta a pagar? Criar lançamento previsto</summary><div class="form-grid"><label>Valor (R$)<input name="finance_amount" inputmode="decimal" maxlength="20" placeholder="0,00"></label><label>Categoria (opcional)<input name="finance_category" maxlength="80" placeholder="Sugerida automaticamente"></label></div><p class="hint">Cria uma saída prevista nas Finanças na data do prazo, com o mesmo título.</p></details>`;
    }
    if (table !== 'routines') html += '<p class="hint">Com o Google conectado, itens com prazo são enviados como eventos de dia inteiro. Itens sem prazo ficam apenas no aplicativo.</p>';
    $('#fields').innerHTML = html;
    $('#form-error').textContent = '';
    $('#editor').showModal();
    $('#fields input').focus();
}
$('#create').addEventListener('click', () => ['review', 'journal'].includes(page) ? openQuickCapture() : editor(page === 'planning' ? 'investment_scenarios' : page === 'finance' ? 'finance_transactions' : ['today', 'calendar', 'week'].includes(page) ? 'tasks' : page));
$('#close-editor').onclick = $('#cancel-editor').onclick = () => $('#editor').close();
$('#cancel-delete').onclick = () => $('#confirmation').close();
$('#edit-form').addEventListener('submit', async e => {
    e.preventDefault();
    const button = e.submitter;
    button.disabled = true;
    try {
        const form = new FormData(e.target),
            values = Object.fromEntries(form);
        if (editing.table === 'routines') { values.days = form.getAll('days'); values.auto_workout = form.has('auto_workout') ? 1 : 0; }
        const financeTable = editing.table.startsWith('finance_');
        const productivityTable = ['goals', 'notes'].includes(editing.table);
        const method = {finance_transactions: 'save_transaction', finance_budgets: 'save_budget', finance_settings: 'save_finance_settings', finance_investment_source: 'save_investment_source'}[editing.table];
        const result = editing.table === 'workout_templates' ? await call('save_workout_template', {name: values.name, exercises: editing.body.exercises, cardio: editing.body.cardio}, editing.id) : editing.table === 'investment_snapshots' ? await call('save_wealth_record', values, editing.id) : financeTable ? await call(method, values, ...(['finance_settings','finance_investment_source'].includes(editing.table) ? [] : [editing.id])) : await call(productivityTable ? 'save_productivity' : 'save', editing.table, values, editing.id);
        $('#editor').close();
        await afterMutation(result, ['tasks','projects'].includes(editing.table), editing.table === 'routines' ? 'Rotina salva somente no aplicativo.' : result.count > 1 ? `${result.count} lançamentos mensais criados. Os futuros ficaram como previstos.` : 'Alterações salvas.');
    } catch (err) {
        $('#form-error').textContent = err.message;
    } finally {
        button.disabled = false;
    }
});

function renderRoutineWeek() {
    const labels=['S','T','Q','Q','S','S','D'];
    return `<div class="routine-week"><p>Progresso da semana</p><div class="week-days">${(state.routine_week || []).map((d,i)=>`<div class="week-day ${d.day===state.today?'week-today':''}"><span class="week-ring ${d.total&&d.done===d.total?'complete':''} ${d.day>state.today?'future':''} ${d.done>0&&d.done<d.total?'partial':''}" style="--week-progress:${d.total?d.done/d.total:0}" role="img" aria-label="${fmt(d.day)}: ${d.done} de ${d.total} rotinas concluídas" title="${fmt(d.day)} · ${d.done} de ${d.total}">${d.total&&d.done===d.total?uiIcon('check'):''}</span><span aria-hidden="true">${labels[i]}</span></div>`).join('')}</div></div>`;
}

document.querySelectorAll('nav [data-icon]').forEach(b=>b.insertAdjacentHTML('afterbegin',uiIcon(b.dataset.icon)));
document.querySelectorAll('.topbar-tools [data-icon], footer [data-icon], #settings-dialog [data-icon], .google-menu [data-icon]').forEach(el=>el.innerHTML=uiIcon(el.dataset.icon));
$('#calendar-logo').innerHTML=calendarLogo();
$('#global-search').addEventListener('input',e=>{
    if (!state) return;
    if(page==='finance') { financeQuery=e.target.value; financeView='transactions'; }
    else query=e.target.value;
    render();
});
$('#brand-home').onclick=e=>{e.preventDefault();$('nav [data-page="today"]').click();};
$('#settings').onclick=()=>$('#settings-dialog').showModal();
$('#settings-close').onclick=()=>$('#settings-dialog').close();
$('#settings-backup').onclick=()=>{$('#settings-dialog').close();$('#backup').click();};
$('#settings-google').onclick=()=>{$('#settings-dialog').close();$('#google-help-dialog').showModal();};
document.addEventListener('click',e=>{
    document.querySelectorAll('.row-menu[open]').forEach(menu=>{if(!menu.contains(e.target))menu.open=false;});
});
$('#confirm-delete-series').onclick = () => { pendingDelete.scope = 'future'; $('#confirm-delete').click(); };
$('#confirm-delete').onclick = async () => {
    const b = $('#confirm-delete');
    b.disabled = true;
    try {
        const financeTable = pendingDelete.table.startsWith('finance_');
        const result = pendingDelete.table === 'workout_templates' ? await call('delete_workout_template', pendingDelete.id) : pendingDelete.table === 'finance_transactions' ? await call('delete_transaction', pendingDelete.id, pendingDelete.scope || 'one') : pendingDelete.table === 'workouts' ? await call('delete_workout', pendingDelete.id) : pendingDelete.table.startsWith('investment_') ? await call('delete_planning', pendingDelete.table, pendingDelete.id) : await call(financeTable ? 'delete_finance' : ['goals','notes'].includes(pendingDelete.table) ? 'delete_productivity' : 'delete', pendingDelete.table, pendingDelete.id);
        $('#confirmation').close();
        await afterMutation(result, ['tasks','projects'].includes(pendingDelete.table), 'Registro excluído.');
    } catch (err) {
        toast(err.message);
    } finally {
        b.disabled = false;
    }
};
$('#content').addEventListener('click', async e => {
    const b = e.target.closest('[data-action]');
    if (!b || b.disabled) return;
    const {
        action,
        table
    } = b.dataset, id = Number(b.dataset.id);
    if (action.startsWith('workout-')) {
        try { await handleWorkoutAction(b); } catch (error) { toast(error.message); }
        return;
    }
    if (action.startsWith('life-')) {
        try { await handleLifeAction(b); } catch (error) { toast(error.message); }
        return;
    }
    if (action.startsWith('plan-')) {
        try { await handlePlanAction(b); } catch (error) { toast(error.message); }
        return;
    }
    if (action.startsWith('prod-')) {
        try { await handleProductivityAction(b); } catch (error) { toast(error.message); }
        return;
    }
    if (action === 'create-task' || action === 'create-routine') {
        editor(action==='create-task'?'tasks':'routines');
        return;
    }
    if (action.startsWith('finance-')) {
        await handleFinanceAction(b);
        return;
    }
    if (action === 'day' || action === 'month' || action === 'calendar-today') {
        if (action === 'day') selectedDay = b.dataset.day;
        else if (action === 'calendar-today') {
            selectedDay = state.today;
            calendarMonth = state.today.slice(0, 7);
        } else {
            const [y, m] = calendarMonth.split('-').map(Number);
            const d = new Date(y, m - 1 + Number(b.dataset.step), 1, 12);
            if (d.getFullYear() < 1900 || d.getFullYear() > 2100) return;
            calendarMonth = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
            selectedDay = calendarMonth + '-01';
        }
        try {
            await refresh();
            if (action !== 'day') queueGoogleSync();
        } catch (err) {
            toast(err.message);
        }
        return;
    }
    if (action === 'edit') {
        b.closest('details')?.removeAttribute('open');
        editor(table, id);
        return;
    }
    if (action === 'delete') {
        b.closest('details')?.removeAttribute('open');
        pendingDelete = {
            table,
            id
        };
        const seriesRow = table === 'finance_transactions' && financeState?.transactions.find(r => r.id === id && r.series);
        $('#confirm-delete-series').hidden = !seriesRow;
        $('#confirm-delete').textContent = seriesRow ? 'Excluir só este' : 'Excluir';
        $('#confirm-detail').textContent = {
            projects: 'O projeto será excluído. As tarefas serão mantidas sem projeto.',
            tasks: 'A tarefa será excluída permanentemente.',
            routines: 'A rotina e todo seu histórico de conclusões serão excluídos.',
            goals: 'A meta e seu progresso serão excluídos.',
            notes: 'A nota será excluída permanentemente.',
            workouts: 'O treino, suas séries e atividades de cardio serão excluídos. Os gráficos serão recalculados.',
            finance_transactions: 'O lançamento será excluído permanentemente e os saldos serão recalculados.',
            finance_budgets: 'O limite será excluído. Seus lançamentos serão mantidos.',
            investment_scenarios: 'O cenário e seus eventos fictícios serão excluídos. Seus lançamentos e registros não mudam.',
            investment_snapshots: 'O valor registrado da carteira será excluído do histórico.',
            workout_templates: 'A ficha será excluída. Os treinos já registrados continuam no histórico.'
        } [table];
        if (['tasks', 'projects'].includes(table) && state.google?.connected) $('#confirm-detail').textContent += ' O evento vinculado também será removido do Google na próxima sincronização.';
        $('#confirmation').showModal();
        return;
    }
    b.disabled = true;
    try {
        const result = await call(action === 'task' ? 'toggle_task' : 'toggle_routine', ...(action === 'task' ? [id] : [id, state.day]));
        await afterMutation(result, action === 'task', 'Registro atualizado.');
    } catch (err) {
        toast(err.message);
        b.disabled = false;
    }
});
$('nav').addEventListener('click', async e => {
    const b = e.target.closest('[data-page]');
    if (!b || !state) return;
    page = b.dataset.page;
    document.body.classList.remove('menu-open');
    $('#menu-toggle').setAttribute('aria-expanded', 'false');
    if (page === 'calendar' && selectedDay) calendarMonth = selectedDay.slice(0, 7);
    query = '';
    try {
        await refresh();
        if (page === 'calendar') queueGoogleSync();
    } catch (err) {
        toast(err.message);
    }
});
$('#backup').onclick = async () => {
    const b = $('#backup');
    b.disabled = true;
    try {
        const r = await call('backup');
        toast(window.holyWeb ? 'Backup baixado para este dispositivo.' : 'Backup salvo em: ' + r.path);
    } catch (err) {
        toast(err.message);
    } finally {
        b.disabled = false;
    }
};
async function afterMutation(result, sync, message) {
    let warning = result.warning || '';
    try {
        await refresh();
    } catch (err) {
        pendingGoogleRefresh = true;
        warning += ' Alteração salva, mas a tela não pôde ser atualizada: ' + err.message;
    }
    if (sync) queueGoogleSync();
    toast(warning.trim() || message);
}

let ready = false,
    starting = false;
async function start() {
    if (ready || starting) return;
    starting = true;
    try {
        await refresh();
        ready = true;
        $('#retry-start').hidden = true;
        queueGoogleSync();
    } catch (err) {
        // No navegador, o pedido do código de conexão já explica o motivo.
        if ($('#pair-dialog').open) { $('#subtitle').textContent = 'Conecte este dispositivo para ver seus dados.'; return; }
        $('#retry-start').hidden = false;
        $('#subtitle').textContent = 'Não foi possível carregar os dados.';
        toast(err.message);
    } finally {
        starting = false;
    }
}
$('#retry-start').onclick = start;
window.addEventListener('pywebviewready', () => ready ? refresh().catch(err=>toast(err.message)) : start());
if (window.pywebview?.api) start();
setTimeout(() => {
    if (!ready && !window.pywebview?.api) $('#subtitle').textContent = 'Abra o aplicativo pelo iniciar_windows.bat para conectar ao Python.';
}, 4000);
setInterval(async () => {
    if (ready && !$('dialog[open]')) {
        try {
            const now = await call('snapshot');
            if (now.today !== state.today) {
                selectedDay = now.today;
                calendarMonth = now.today.slice(0, 7);
                await refresh();
            }
            else if (!document.activeElement?.matches('input,textarea,select') && page !== 'focus') await refresh();
        } catch (err) {
            /* Mantém a tela durante uma falha temporária. */
        }
    }
}, 30000);


function renderCalendar() {
    const [year, month] = calendarMonth.split('-').map(Number);
    const first = new Date(year, month - 1, 1, 12);
    const offset = (first.getDay() + 6) % 7;
    const total = new Date(year, month, 0, 12).getDate();
    const monthTitle = first.toLocaleDateString('pt-BR', {
        month: 'long',
        year: 'numeric'
    });
    let cells = Array.from({
        length: offset
    }, () => '<div class="calendar-blank" aria-hidden="true"></div>').join('');
    for (let n = 1; n <= total; n++) {
        const key = calendarMonth + '-' + String(n).padStart(2, '0');
        const item = calendarData[key] || {
            tasks: 0,
            routines: 0,
            tasks_done: 0,
            routines_done: 0,
            google: 0,
            projects: 0
        };
        cells += `<button class="calendar-day ${key===selectedDay?'selected':''} ${key===state.today?'is-today':''}" data-action="day" data-day="${key}" aria-pressed="${key===selectedDay}" aria-label="${fmt(key)}, ${item.tasks} tarefas, ${item.routines} rotinas, ${item.google||0} eventos Google, ${item.projects||0} prazos de projetos"><span class="day-number">${n}</span><span class="calendar-total" aria-hidden="true">${item.tasks+item.routines+(item.google||0)+(item.projects||0) || 0}<small>itens</small></span>${item.tasks?`<span class="calendar-count">${item.tasks}<span class="calendar-label"> tarefa${item.tasks===1?'':'s'}</span><span class="calendar-short" aria-hidden="true"> T</span> <small>${item.tasks_done} ✓</small></span>`:''}${item.projects?`<span class="calendar-count">${item.projects} P</span>`:''}${item.google?`<span class="calendar-count google-count">${item.google} G</span>`:''}${item.routines?`<span class="calendar-count routine-count">${item.routines}<span class="calendar-label"> rotina${item.routines===1?'':'s'}</span><span class="calendar-short" aria-hidden="true"> R</span> <small>${item.routines_done} ✓</small></span>`:''}</button>`;
    }
    const matches = item => item.title.toLocaleLowerCase().includes(query.toLocaleLowerCase());
    const tasks = state.tasks.filter(t => t.due === selectedDay && matches(t)),
        routines = state.routines.filter(r => r.scheduled && matches(r));
    return `<section class="panel calendar-panel"><div class="calendar-heading"><h2>${esc(monthTitle)}</h2><div><button class="secondary" data-action="calendar-today">Hoje</button><button class="icon" data-action="month" data-step="-1" aria-label="Mês anterior">‹</button><button class="icon" data-action="month" data-step="1" aria-label="Próximo mês">›</button></div></div><div class="calendar-week">${days.map(d=>`<span>${d}</span>`).join('')}</div><div class="calendar-grid">${cells}</div><p class="hint calendar-legend-full">Selecione um dia. T = tarefas, R = rotinas, P = projetos, G = Google; ✓ indica conclusões. Tarefas sem prazo ficam na aba Tarefas.</p><p class="hint calendar-legend-compact">O número indica quantos itens há no dia. Selecione uma data para ver os detalhes na agenda abaixo.</p></section><div class="section-title"><h2>Agenda de ${fmt(selectedDay)}</h2><span>${tasks.length} TAREFAS · ${routines.length} ROTINAS</span></div><div class="panel">${tasks.map(taskRow).join('')+routines.map(routineRow).join('')+(state.google_events||[]).filter(matches).map(googleEventRow).join('')+state.projects.filter(p=>p.due===selectedDay && matches(p)).map(projectDeadlineRow).join('')||empty('Dia sem itens programados.','Use Nova tarefa para adicionar um prazo nesta data.')}</div>`;
}


function googleEventRow(event) {
    return `<div class="routine-row google-event"><span class="google-mark" aria-hidden="true">G</span><div class="row-body"><div class="row-title">${esc(event.title)}</div><div class="row-meta">${esc(event.clock)} · ${esc(event.calendar_name)}</div></div><span class="badge google-badge">Google Agenda</span></div>`;
}

function projectDeadlineRow(project) {
    return `<div class="routine-row"><span class="google-mark" aria-hidden="true">P</span><div class="row-body"><div class="row-title">${esc(project.title)}</div><div class="row-meta">Prazo do projeto · ${fmt(project.due)}</div></div>${actions('projects',project.id)}</div>`;
}

function renderGoogle(status) {
    if (!status) return;
    if (state) state.google = status;
    $('#google-state').textContent = status.busy ? 'Sincronizando…' : status.connected ? 'Conectado' : 'Não conectado';
    $('#google-state').classList.toggle('connected',status.connected);
    $('#google-state').title = status.account || '';
    $('#google-detail').textContent = status.error || (status.connected ? 'Agenda principal · ' + status.timezone : 'Conecte sua agenda para ver seus eventos.');
    $('#google-detail').classList.toggle('error', Boolean(status.error));
    $('#google-connect').textContent = 'Conectar Google';
    $('#google-connect').hidden = status.connected;
    $('#google-connect').disabled = status.busy;
    $('#google-sync').hidden = !status.connected;
    $('#google-sync').disabled = status.busy;
    $('#google-sync').innerHTML = uiIcon('repeat') + 'Sincronizar';
    $('#google-disconnect').hidden = !status.connected;
    $('#google-disconnect').disabled = status.busy;
    $('#google-reconnect').hidden = !status.connected;
    $('#google-reconnect').disabled = status.busy;
}

async function queueGoogleSync() {
    if (!state?.google?.connected) return;
    const month = page === 'calendar' ? calendarMonth : state.today.slice(0, 7);
    const [year, number] = month.split('-').map(Number);
    try {
        await call('google_sync', year, number);
        renderGoogle(await call('google_status'));
    } catch (err) {
        toast(err.message);
    }
}

$('#google-help').onclick = () => $('#google-help-dialog').showModal();
$('#google-help-close').onclick = () => $('#google-help-dialog').close();
$('#google-sync').onclick = queueGoogleSync;
$('#google-connect').onclick = async () => {
    $('#google-connect').disabled = true;
    $('#google-state').textContent = 'Autorize a conexão no navegador…';
    try {
        await call('google_connect');
        await refresh();
        queueGoogleSync();
    } catch (err) {
        toast(err.message);
    } finally {
        try {
            renderGoogle(await call('google_status'));
        } catch (err) {
            $('#google-connect').disabled = false;
            toast(err.message);
        }
    }
};
$('#google-reconnect').onclick = () => $('#google-connect').click();
$('#google-disconnect').onclick = async () => {
    try {
        await call('google_disconnect');
        await refresh();
        toast('Desconectado. Seus eventos continuam no Google.');
    } catch (err) {
        toast(err.message);
    }
};
let googleWasBusy = false,
    googleRevision = -1;
let pollingGoogle = false,
    pendingGoogleRefresh = false;
setInterval(async () => {
    if (!ready || pollingGoogle) return;
    pollingGoogle = true;
    try {
        const status = await call('google_status');
        renderGoogle(status);
        if ((googleWasBusy && !status.busy) || status.revision !== googleRevision) pendingGoogleRefresh = true;
        googleWasBusy = status.busy;
        googleRevision = status.revision;
        const interacting = $('dialog[open]') || document.activeElement?.matches('input, textarea, select');
        if (pendingGoogleRefresh && !interacting) {
            const main = $('main'),
                top = main.scrollTop,
                windowTop = window.scrollY;
            await refresh();
            main.scrollTop = top;
            window.scrollTo(0, windowTop);
            pendingGoogleRefresh = false;
        }
    } catch (err) {
        /* Uma falha temporária não perde a atualização pendente. */
    } finally {
        pollingGoogle = false;
    }
}, 2000);
setInterval(() => {
    if (ready) queueGoogleSync();
}, 60000);
