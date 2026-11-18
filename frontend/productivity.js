'use strict';
let taskView = 'board', priorityFilter = '', projectFilter = '', weekOffset = 0;
let installPrompt, focusSaving = false;
const localRead = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };
const localWrite = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* Timer remains usable in memory. */ } };
const freshTimer = () => ({mode: 'focus', minutes: 25, remaining: 1500, end: null, task: '', title: 'Foco livre', id: null, pending: null});
let focusTimer = {...freshTimer(), ...localRead('holy-focus-v4', {})};
document.documentElement.dataset.theme = localRead('holy-theme', 'light');
const isoDay = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
const shiftDay = (day, n) => { const d = new Date(day + 'T12:00:00'); d.setDate(d.getDate() + n); return isoDay(d); };
const smallDate = day => new Date(day + 'T12:00:00').toLocaleDateString('pt-BR', {day:'numeric',month:'short'});
const minuteLabel = n => n >= 60 ? `${Math.floor(n/60)}h${n%60 ? ` ${n%60}min` : ''}` : `${n} min`;
const pageButton = (target, label) => `<button class="text-button" data-action="prod-page" data-page="${target}">${label} <span>↗</span></button>`;

function renderToday() {
    const due = state.tasks.filter(t => t.due && t.due <= state.today && t.status !== 'Concluído');
    const completed = state.tasks.filter(t => t.due === state.today && t.status === 'Concluído').length;
    const routines = state.routines.filter(r => r.scheduled);
    const done = routines.filter(r => r.done).length;
    const hour = new Date().getHours();
    $('#page-title').textContent = `${hour < 12 ? 'Bom dia' : hour < 18 ? 'Boa tarde' : 'Boa noite'}. Vamos com calma?`;
    $('#subtitle').textContent = 'Um pouco de clareza para fazer espaço para o que importa.';
    const match = row => row.title.toLocaleLowerCase().includes(query.toLocaleLowerCase());
    const sorted = [...due].sort((a,b) => ({Alta:0,Média:1,Baixa:2}[a.priority] - {Alta:0,Média:1,Baixa:2}[b.priority]) || a.due.localeCompare(b.due));
    return `<section class="intention-banner"><div><span class="eyebrow">MENOS PRESSA. MAIS PRESENÇA.</span><h2>Seu próximo passo começa aqui.</h2><p>Escolha uma prioridade, encontre seu foco e celebre o progresso.</p><button class="banner-button" data-action="prod-page" data-page="focus">${uiIcon('clock')} Reservar um tempo para focar <span>↗</span></button></div><div class="orbit-art" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><div class="orbit-core">✦</div><span class="orbit-star">✧</span><span class="orbit-dot"></span><span class="orbit-caption">UM PASSO DE CADA VEZ</span></div></section>
    <div class="overview-stats">
      ${overviewStat('checkSquare','No seu radar',due.length, `${completed} concluída${completed===1?'':'s'} com prazo hoje`, 'lavender')}
      ${overviewStat('target','Rotinas de hoje',`${done}<small> / ${routines.length}</small>`,routines.length ? `${Math.round(done/routines.length*100)}% do seu cuidado diário` : 'Crie seu primeiro hábito', 'mint')}
      ${overviewStat('clock','Tempo de foco',minuteLabel(state.focus_today),`${minuteLabel(state.focus_week)} nesta semana`, 'peach')}
      ${overviewStat('folder','Projetos ativos',state.projects.filter(p=>!p.total||p.done<p.total).length,`${state.goals.filter(g=>g.current>=g.target).length} metas alcançadas`, 'blue')}
    </div>
    ${typeof renderTodayExtras==='function'?renderTodayExtras():''}
    <div class="dashboard-grid"><section class="panel dashboard-tasks"><div class="section-head"><div><span class="eyebrow">UMA COISA DE CADA VEZ</span><h2>Prioridades do dia <span class="count-pill">${due.length}</span></h2></div>${pageButton('tasks','Ver todas')}</div><div class="day-task-items">${sorted.filter(match).slice(0,5).map(taskRow).join('') || `<div class="empty"><span class="empty-glyph">✧</span><strong>${query?'Nada por aqui para essa busca.':'Uma página em branco para o seu dia.'}</strong><p>Escolha algo importante e comece com um pequeno passo.</p><button class="secondary" data-action="create-task">${uiIcon('plus')}Adicionar tarefa</button></div>`}</div><div class="panel-bottom">${due.some(t=>t.due<state.today)?`${due.filter(t=>t.due<state.today).length} tarefa(s) com prazo vencido. Você pode replanejá-las.`:'Cada tarefa concluída é um pouco mais de espaço na mente.'}</div></section>
    <section class="panel dashboard-routines"><div class="section-head"><div><span class="eyebrow">CUIDE DA SUA CONSTÂNCIA</span><h2>Pequenos hábitos</h2></div>${pageButton('routines','Ver todos')}</div><div class="today-routines">${routines.filter(match).slice(0,4).map(routineRow).join('') || `<div class="empty"><span class="empty-glyph mint-text">♧</span><strong>Seu ritmo começa pequeno.</strong><p>Leitura, movimento, uma pausa para você.</p><button class="secondary" data-action="create-routine">${uiIcon('plus')}Criar rotina</button></div>`}</div>${renderRoutineWeek()}</section>
    <section class="panel weekly-focus"><div class="section-head"><div><span class="eyebrow">PROGRESSO REAL</span><h2>Seu foco nesta semana</h2></div><span class="subtle-pill">${minuteLabel(state.focus_week)}</span></div>${focusChart()}<p class="chart-caption">Cada minuto investido em você conta.</p></section>
    <section class="panel next-goals"><div class="section-head"><div><span class="eyebrow">OLHE PARA A FRENTE</span><h2>Na direção dos seus objetivos</h2></div>${pageButton('goals','Ver metas')}</div>${state.goals.filter(match).filter(g=>g.current<g.target).slice(0,2).map(g=>`<div class="compact-goal"><div><strong>${esc(g.title)}</strong><span>${Math.min(100,Math.round(g.current/g.target*100))}%</span></div><div class="track"><span style="width:${Math.min(100,g.current/g.target*100)}%"></span></div><small>${g.current} de ${g.target} ${esc(g.unit)}</small></div>`).join('')||`<div class="empty compact-empty"><strong>O que você quer construir?</strong><p>Crie uma meta e acompanhe cada avanço.</p><button class="text-button" data-action="prod-new" data-table="goals">Criar minha primeira meta →</button></div>`}</section></div><div id="google-slot"></div>`;
}
function overviewStat(icon, label, value, detail, color) {
    return `<article class="overview-stat"><div class="stat-top"><span>${label}</span><span class="stat-icon ${color}">${uiIcon(icon)}</span></div><strong class="overview-number">${value}</strong><small>${detail}</small></article>`;
}
function focusChart() {
    const max = Math.max(60,...state.focus_days.map(d=>d.minutes));
    return `<div class="focus-chart">${state.focus_days.map((d,i)=>`<div class="chart-column ${d.day===state.today?'current':''}"><span>${d.minutes ? minuteLabel(d.minutes) : '—'}</span><div class="chart-track"><div style="height:${Math.max(3,d.minutes/max*100)}%" title="${fmt(d.day)}: ${d.minutes} minutos"></div></div><small>${days[i]}</small></div>`).join('')}</div>`;
}
function renderTaskBoard() {
    const tasks = state.tasks.filter(t => `${t.title} ${t.notes} ${t.project}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()))
        .filter(t=>(filter==='Todos'||t.status===filter)&&(!priorityFilter||t.priority===priorityFilter)&&(!projectFilter||String(t.project_id || 'none')===projectFilter));
    const controls = `<div class="task-controls">${toolbar(`<select id="status-filter" aria-label="Filtrar status">${['Todos','A fazer','Em andamento','Concluído'].map(s=>`<option ${filter===s?'selected':''}>${s}</option>`).join('')}</select><select id="priority-filter" aria-label="Filtrar prioridade"><option value="">Todas as prioridades</option>${['Alta','Média','Baixa'].map(p=>`<option ${p===priorityFilter?'selected':''}>${p}</option>`).join('')}</select><select id="project-filter" aria-label="Filtrar projeto"><option value="">Todos os projetos</option><option value="none" ${projectFilter==='none'?'selected':''}>Sem projeto</option>${state.projects.map(p=>`<option value="${p.id}" ${String(p.id)===projectFilter?'selected':''}>${esc(p.title)}</option>`).join('')}</select>`)}<div class="segmented"><button data-action="prod-view" data-view="board" class="${taskView==='board'?'selected':''}">Quadro</button><button data-action="prod-view" data-view="list" class="${taskView==='list'?'selected':''}">Lista</button></div></div>`;
    if (taskView==='list') return controls+`<div class="panel">${tasks.map(taskRow).join('')||empty('Nenhuma tarefa encontrada.','Ajuste os filtros ou crie uma tarefa.')}</div>`;
    return controls+`<div class="kanban">${['A fazer','Em andamento','Concluído'].map((status,i)=>`<section class="kanban-column"><h2><i class="status-dot status-${i}"></i>${status}<span class="count-pill">${tasks.filter(t=>t.status===status).length}</span></h2>${tasks.filter(t=>t.status===status).map(t=>`<article class="kanban-card"><div class="card-top"><span class="badge ${t.priority==='Alta'?'high':''}">${esc(t.priority)}</span>${actions('tasks',t.id)}</div><button class="card-title ${status==='Concluído'?'done-title':''}" data-action="edit" data-table="tasks" data-id="${t.id}">${esc(t.title)}</button><p class="card-project">${uiIcon('folder')}${esc(t.project)}</p>${t.notes?`<p class="card-excerpt">${esc(t.notes.slice(0,110))}</p>`:''}<div class="card-bottom"><span class="${t.due&&t.due<state.today&&status!=='Concluído'?'late':''}">${uiIcon('calendar')}${t.due?smallDate(t.due):'Sem prazo'}</span>${t.estimate_minutes?`<span>${uiIcon('clock')}${minuteLabel(t.estimate_minutes)}</span>`:''}</div><label class="card-status-label">Mover para<select class="task-status-select" data-id="${t.id}" aria-label="Status: ${esc(t.title)}">${['A fazer','Em andamento','Concluído'].map(s=>`<option ${s===status?'selected':''}>${s}</option>`).join('')}</select></label></article>`).join('')||`<div class="column-empty">${i===2?'Seu progresso vai aparecer aqui.':'Espaço para o próximo passo.'}</div>`}<button class="add-card" data-action="prod-add-status" data-status="${status}">${uiIcon('plus')}Adicionar tarefa</button></section>`).join('')}</div><p class="hint">Use “Mover para” em cada cartão para atualizar o status, inclusive no celular.</p>`;
}
function renderProductivity(view) {
    const match = row => `${row.title} ${row.body||row.description||''}`.toLocaleLowerCase().includes(query.toLocaleLowerCase());
    if (view==='week') {
        const d = new Date(state.today+'T12:00:00');
        const monday = shiftDay(state.today,-((d.getDay()+6)%7)+weekOffset*7);
        const weekDays = Array.from({length:7},(_,i)=>shiftDay(monday,i));
        const tasks = state.tasks.filter(t=>weekDays.includes(t.due));
        const totalMinutes = tasks.filter(t=>t.status!=='Concluído').reduce((n,t)=>n+t.estimate_minutes,0);
        return `<div class="week-heading"><div><h2>${smallDate(monday)} — ${smallDate(weekDays[6])}</h2><p>${tasks.filter(t=>t.status!=='Concluído').length} tarefas pendentes · ${minuteLabel(totalMinutes)} planejados</p></div><div class="week-controls"><button class="secondary" data-action="prod-week" data-step="0">Esta semana</button><button class="secondary" data-action="prod-week" data-step="-1" aria-label="Semana anterior">←</button><button class="secondary" data-action="prod-week" data-step="1" aria-label="Próxima semana">→</button></div></div><div class="week-board">${weekDays.map((day,i)=>`<section class="week-column ${day===state.today?'is-today':''}"><div class="week-column-head"><span>${days[i]}</span><strong>${Number(day.slice(-2))}</strong>${day===state.today?'<small>Hoje</small>':''}</div>${tasks.filter(t=>t.due===day&&match(t)).sort((a,b)=>a.scheduled_time.localeCompare(b.scheduled_time)).map(t=>`<button class="week-task ${t.status==='Concluído'?'done-title':''}" data-action="edit" data-table="tasks" data-id="${t.id}"><span class="week-task-time">${t.scheduled_time||'Sem horário'} ${t.status==='Concluído'?'· ✓':''}</span><strong>${esc(t.title)}</strong><small>${esc(t.project)}</small>${t.estimate_minutes?`<span class="week-task-time">${minuteLabel(t.estimate_minutes)}</span>`:''}</button>`).join('')}<button class="week-add" data-action="prod-add-day" data-day="${day}" aria-label="Adicionar tarefa em ${fmt(day)}">${uiIcon('plus')}</button></section>`).join('')}</div><section class="panel unscheduled"><div class="section-head"><h2>Sem data, com possibilidades</h2><span class="count-pill">${state.tasks.filter(t=>!t.due&&t.status!=='Concluído').length}</span></div>${state.tasks.filter(t=>!t.due&&t.status!=='Concluído'&&match(t)).map(taskRow).join('')||empty('Tudo tem seu tempo.','Tarefas sem prazo aparecerão aqui para você planejar.')}</section>`;
    }
    if (view==='goals') return `<div class="goal-summary"><span>✦</span><div><strong>${state.goals.filter(g=>g.current>=g.target).length} de ${state.goals.length} metas alcançadas</strong><p>Valorize o caminho, além da chegada.</p></div></div><div class="project-grid goals-grid">${state.goals.filter(match).map(g=>{const percent=Math.min(100,Math.round(g.current/g.target*100));return `<article class="project goal-card"><div class="project-head"><span class="goal-icon">${uiIcon(g.current>=g.target?'checkSquare':'target')}</span>${actions('goals',g.id)}</div><span class="eyebrow">${g.current>=g.target?'META ALCANÇADA':'EM CONSTRUÇÃO'}</span><h2>${esc(g.title)}</h2><p>${esc(g.description||'Cada pequeno avanço faz diferença.')}</p><div class="progress-label"><strong>${g.current.toLocaleString('pt-BR')} <small>/ ${g.target.toLocaleString('pt-BR')} ${esc(g.unit)}</small></strong><span>${percent}%</span></div><div class="track"><span style="width:${percent}%"></span></div><div class="goal-footer"><span>${fmt(g.due)}</span>${g.auto?`<span class="badge goal-auto">${uiIcon('repeat')}Automática · ${{workouts:'treinos',focus:'foco',routine:'rotina',wealth:'carteira'}[g.source]}${g.source!=='wealth'?` · ${{week:'semana',month:'mês',total:'total'}[g.period]}`:''}</span>`:`<button class="secondary" data-action="edit" data-table="goals" data-id="${g.id}">Atualizar progresso</button>`}</div></article>`;}).join('')}</div>${state.goals.filter(match).length?'':empty('Uma intenção pode virar uma conquista.','Clique em Nova meta e defina seu primeiro objetivo.')}`;
    if (view==='notes') return `<div class="notes-grid">${state.notes.filter(match).map(n=>`<article class="note-card"><div class="card-top"><span class="eyebrow">${n.pinned?'✦ FIXADA':'IDEIAS & LEMBRETES'}</span>${actions('notes',n.id)}</div><button class="note-title" data-action="edit" data-table="notes" data-id="${n.id}">${esc(n.title)}</button><p>${esc(n.body||'Uma ideia esperando para ganhar forma.')}</p><small>Atualizada em ${new Date(n.updated).toLocaleDateString('pt-BR')}</small></article>`).join('')}</div>${state.notes.filter(match).length?'':empty('Sua mente merece um pouco de espaço.','Crie uma nota para guardar ideias, reflexões e planos.')}`;
    return renderFocus();
}
function productivityEditor(table,id) {
    const r=id?state[table].find(r=>r.id===id):{};
    if(!r)return;
    editing={table,id};
    $('#editor-title').textContent=(id?'Editar ':'Criar ')+(table==='goals'?'meta':'nota');
    let html=input('Título *','title',r.title);
    if(table==='goals') {
        const sources=[['manual','Atualizo à mão'],['workouts','Treinos registrados'],['focus','Minutos de foco'],['routine','Conclusões de uma rotina'],['wealth','Valor da carteira (R$)']];
        html+=`<label>Por que essa meta importa?<textarea name="description" maxlength="10000">${esc(r.description)}</textarea></label><div class="form-grid">${select('Como acompanhar o progresso','source',sources,r.source||'manual')}${select('Contar','period',[['week','Nesta semana'],['month','Neste mês'],['total','Desde o início']],r.period||'month')}</div><label id="goal-routine-field">Rotina<select name="source_ref">${state.routines.map(x=>`<option value="${x.id}" ${x.id===r.source_ref?'selected':''}>${esc(x.title)}</option>`).join('')||'<option value="">Crie uma rotina primeiro</option>'}</select></label><div class="form-grid"><label>Objetivo<input type="number" name="target" min="1" max="1000000000" step="1" required value="${r.target||10}"></label><label id="goal-current-field">Progresso atual<input type="number" name="current" min="0" max="1000000000" step="1" required value="${r.current||0}"></label></div>${input('Unidade (ex.: livros, aulas, treinos)','unit',r.unit||'etapas')}${input('Prazo (opcional)','due',r.due,'date')}<p class="hint" id="goal-source-help"></p>`;
    }
    else html+=`<label>Sua nota<textarea class="note-editor" name="body" maxlength="30000" placeholder="Ideias, planos, o que estiver na sua mente…">${esc(r.body)}</textarea></label>${select('Posição','pinned',[[0,'Normal'],[1,'Fixar no topo']],r.pinned||0)}`;
    $('#fields').innerHTML=html;$('#form-error').textContent='';
    if(table==='goals') {
        const source=$('#fields [name="source"]'),unit=$('#fields [name="unit"]');
        const update=()=>{
            const auto=source.value!=='manual';
            $('#goal-current-field').hidden=auto;$('#goal-routine-field').hidden=source.value!=='routine';
            $('#fields [name="period"]').closest('label').hidden=['manual','wealth'].includes(source.value);
            const units={workouts:'treinos',focus:'minutos',routine:'vezes',wealth:'reais'};
            if(auto&&(!unit.value||unit.value==='etapas'||Object.values(units).includes(unit.value)))unit.value=units[source.value];
            $('#goal-source-help').textContent={manual:'Você atualiza o progresso quando quiser.',workouts:'Conta os treinos registrados em Meus treinos no período.',focus:'Soma os minutos das sessões completas do Modo foco no período.',routine:'Conta os dias em que a rotina foi concluída no período.',wealth:'Usa o último valor da carteira registrado em Planejar investimentos.'}[source.value];
        };
        source.onchange=update;update();
    }
    $('#editor').showModal();$('#fields input').focus();
}
function renderFocus() {
    return `<div class="focus-layout"><section class="panel focus-clock-panel"><span class="eyebrow">DESACELERE PARA IR MAIS LONGE</span><div class="focus-modes segmented">${[['focus','Foco',25],['short','Pausa curta',5],['long','Pausa longa',15]].map(([mode,label,min])=>`<button data-action="prod-mode" data-mode="${mode}" data-minutes="${min}" class="${focusTimer.mode===mode?'selected':''}" ${focusTimer.id||focusTimer.pending?'disabled':''}>${label}</button>`).join('')}</div><div class="timer-ring" id="timer-ring"><div><span id="focus-time">25:00</span><small id="focus-caption">Um momento para o que importa</small></div></div><div class="focus-settings"><label>Vou dedicar este tempo a<select id="focus-task" ${focusTimer.id||focusTimer.pending?'disabled':''}><option value="">Foco livre</option>${state.tasks.filter(t=>t.status!=='Concluído'||String(t.id)===String(focusTimer.task)).map(t=>`<option value="${t.id}" ${String(t.id)===String(focusTimer.task)?'selected':''}>${esc(t.title)}</option>`).join('')}</select></label><label>Minutos<input id="focus-duration" type="number" min="1" max="180" step="1" value="${focusTimer.minutes}" ${focusTimer.id||focusTimer.pending?'disabled':''}></label></div><div class="timer-actions"><button class="primary" data-action="prod-timer" id="timer-toggle">${focusTimer.end?'Pausar':focusTimer.id?'Continuar':'Começar foco'}</button><button class="secondary" data-action="prod-reset">Reiniciar</button></div><p class="hint">${focusTimer.pending?'Sessão concluída. Tentando salvar no computador…':'A contagem continua ao trocar de tela. Apenas sessões completas de foco entram no histórico.'}</p></section><div class="focus-side"><section class="focus-tip"><span>✦</span><h2>Você não precisa fazer tudo agora.</h2><p>Escolha uma tarefa. Silencie as distrações. Dê a ela alguns minutos da sua atenção.</p></section><section class="panel session-panel"><div class="section-head"><h2>Seu tempo bem investido</h2></div><div class="focus-totals"><div><strong>${minuteLabel(state.focus_today)}</strong><span>hoje</span></div><div><strong>${minuteLabel(state.focus_week)}</strong><span>nesta semana</span></div></div><h3>Últimas sessões</h3>${state.sessions.slice(0,6).map(s=>`<div class="session-row"><span class="session-check">${uiIcon('check')}</span><div><strong>${esc(s.title)}</strong><small>${smallDate(s.day)}</small></div><span>${s.minutes} min</span></div>`).join('')||'<p class="hint">Seu histórico começa com a primeira sessão completa.</p>'}</section></div></div>`;
}
function bindProductivityEvents() {
    $('#priority-filter')?.addEventListener('change',e=>{priorityFilter=e.target.value;render();});
    $('#project-filter')?.addEventListener('change',e=>{projectFilter=e.target.value;render();});
    document.querySelectorAll('.task-status-select').forEach(el=>el.addEventListener('change',async()=>{
        el.disabled=true;
        try {const result=await call('set_task_status',Number(el.dataset.id),el.value);await afterMutation(result,true,'Tarefa movida.');}
        catch(error){toast(error.message);await refresh().catch(()=>{});}
    }));
    updateTimerDisplay();
}
async function handleProductivityAction(button) {
    const d=button.dataset;
    if(d.action==='prod-page')return navigatePage(d.page);
    if(d.action==='prod-view'){taskView=d.view;render();}
    if(d.action==='prod-week'){weekOffset=Number(d.step)===0?0:weekOffset+Number(d.step);render();}
    if(d.action==='prod-new')editor(d.table);
    if(d.action==='prod-add-day'){selectedDay=d.day;editor('tasks');}
    if(d.action==='prod-add-status'){editor('tasks');$('#fields [name="status"]').value=d.status;}
    if(d.action==='prod-mode'){
        if(focusTimer.id||focusTimer.pending)return;
        focusTimer={...freshTimer(),mode:d.mode,minutes:Number(d.minutes),remaining:Number(d.minutes)*60};
        localWrite('holy-focus-v4',focusTimer);render();
    }
    if(d.action==='prod-timer') {
        if(focusTimer.pending){await flushFocus();return;}
        if(focusTimer.end){focusTimer.remaining=Math.max(0,Math.ceil((focusTimer.end-Date.now())/1000));focusTimer.end=null;}
        else {
            if(!focusTimer.id){
                const minutes=Number($('#focus-duration').value);
                if(!Number.isInteger(minutes)||minutes<1||minutes>180)throw new Error('Escolha de 1 a 180 minutos.');
                focusTimer.minutes=minutes;focusTimer.remaining=minutes*60;
                focusTimer.task=$('#focus-task').value;
                focusTimer.title=state.tasks.find(t=>String(t.id)===focusTimer.task)?.title||'Foco livre';
                focusTimer.id=globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random().toString(36).slice(2)}`;
            }
            focusTimer.end=Date.now()+focusTimer.remaining*1000;
        }
        localWrite('holy-focus-v4',focusTimer);render();
    }
    if(d.action==='prod-reset'){
        if(focusTimer.pending){await flushFocus();return;}
        if(focusTimer.id && !window.confirm('Reiniciar este ciclo? O tempo parcial não será registrado.'))return;
        focusTimer={...freshTimer(),mode:focusTimer.mode,minutes:focusTimer.minutes,remaining:focusTimer.minutes*60};
        localWrite('holy-focus-v4',focusTimer);render();
    }
}
async function navigatePage(target) { const button=document.querySelector(`nav [data-page="${target}"]`);button?.click(); }
function updateTimerDisplay() {
    const seconds=focusTimer.end?Math.max(0,Math.ceil((focusTimer.end-Date.now())/1000)):focusTimer.remaining;
    const display=`${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
    if($('#focus-time'))$('#focus-time').textContent=display;
    if($('#timer-ring'))$('#timer-ring').style.setProperty('--timer-progress',`${(1-seconds/(focusTimer.minutes*60))*360}deg`);
    $('#mini-timer').hidden=!focusTimer.id||page==='focus';
    $('#mini-timer-text').textContent=display+(focusTimer.end?'':' · pausado');
    if(focusTimer.end)document.title=`${display} · Holy Planner`;
    else document.title='Holy Planner';
    if(focusTimer.end&&seconds===0) {
        const completionDay=isoDay(new Date(focusTimer.end));
        focusTimer.end=null;focusTimer.remaining=0;
        if(focusTimer.mode==='focus')focusTimer.pending={id:focusTimer.id,minutes:focusTimer.minutes,task_id:focusTimer.task,title:focusTimer.title,day:completionDay};
        else {focusTimer.id=null;focusTimer.remaining=focusTimer.minutes*60;toast('Pausa concluída. Pronto para um novo passo?');}
        localWrite('holy-focus-v4',focusTimer);
        if(focusTimer.pending)flushFocus();else if(page==='focus')render();
    }
}
async function flushFocus() {
    if(!focusTimer.pending||focusSaving||!state)return;
    focusSaving=true;
    try {
        await call('save_focus_session',focusTimer.pending);
        focusTimer={...freshTimer(),task:focusTimer.task,title:focusTimer.title};
        localWrite('holy-focus-v4',focusTimer);
        await refresh();toast('Foco concluído e registrado. Hora de uma pausa!');
    } catch { if($('#focus-caption'))$('#focus-caption').textContent='Concluído · aguardando conexão'; }
    finally {focusSaving=false;}
}
function showInstallHelp() {
    $('#settings-dialog').close();
    $('#install-instructions').innerHTML=window.holyWeb?`<p><strong>No computador:</strong> no Chrome ou Edge, use “Instalar Holy Planner” no menu do navegador.</p><p><strong>No celular:</strong> abra o endereço exibido ao executar <code>iniciar_web.bat</code>, na mesma rede Wi-Fi, e digite o código de conexão.</p><p>${window.isSecureContext?'No Android, use “Instalar app”. No iPhone, abra no Safari e use Compartilhar → Adicionar à Tela de Início.':'Você está em uma conexão HTTP. Para instalar como PWA no celular, é necessário HTTPS com certificado confiável. O acesso pelo navegador já funciona na rede local.'}</p><p class="hint">Mantenha o computador ligado e o servidor aberto para acessar e salvar seus dados. O timer guarda uma sessão concluída neste navegador até a conexão voltar. Leia APP.md para configurar HTTPS.</p>`:`<p><strong>Windows:</strong> use esta janela ou o executável Holy Planner.</p><p><strong>Celular e navegador:</strong> execute <code>iniciar_web.bat</code> na pasta do programa. Abra o endereço exibido no celular e digite o código de conexão.</p><p>O computador deve estar ligado e na mesma rede Wi-Fi. A instalação como PWA no celular requer HTTPS. Consulte APP.md para os detalhes.</p>`;
    $('#install-dialog').showModal();
}
window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installPrompt=event;document.querySelector('#install-app').hidden=false;});
document.addEventListener('DOMContentLoaded',()=>{
    $('#theme-toggle').onclick=()=>{const theme=document.documentElement.dataset.theme==='dark'?'light':'dark';document.documentElement.dataset.theme=theme;localWrite('holy-theme',theme);};
    $('#menu-toggle').onclick=()=>{const open=document.body.classList.toggle('menu-open');$('#menu-toggle').setAttribute('aria-expanded',String(open));};
    $('#sidebar-focus').onclick=$('#mini-timer-open').onclick=()=>navigatePage('focus');
    $('#install-help').onclick=showInstallHelp;
    $('#install-close').onclick=()=>$('#install-dialog').close();
    $('#install-app').onclick=async()=>{if(installPrompt){await installPrompt.prompt();installPrompt=null;$('#install-app').hidden=true;}else showInstallHelp();};
    $('#pair-dialog').addEventListener('cancel',event=>event.preventDefault());
    document.addEventListener('keydown',event=>{
        if(!state||$('dialog[open]')||event.target.matches('input,textarea,select')||event.ctrlKey||event.metaKey)return;
        if(event.key==='/'&&!event.altKey){event.preventDefault();$('#global-search').focus();}
        if(event.key.toLowerCase()==='n'&&!event.altKey){event.preventDefault();editor('tasks');}
        if(event.altKey&&['1','2'].includes(event.key)){event.preventDefault();navigatePage(event.key==='1'?'today':'focus');}
    });
    setInterval(()=>{if(typeof state!=='undefined'&&state)updateTimerDisplay();},500);
    setInterval(flushFocus,15000);
    window.addEventListener('online',()=>{flushFocus();if(state)refresh().catch(()=>{});});
    window.addEventListener('storage',event=>{if(event.key==='holy-focus-v4'){focusTimer={...freshTimer(),...localRead('holy-focus-v4',{})};if(state&&page==='focus')render();}});
    if(window.holyWeb&&window.isSecureContext&&'serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(()=>{});
    }
});
