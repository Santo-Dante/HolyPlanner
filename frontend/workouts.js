'use strict';
let workoutState, workoutRange = '90', workoutView = 'history', workoutKind = 'strength';
let workoutSelection = '', workoutMetric = 'max_weight', workoutDraft = null, workoutSaving = false;
const wn = value => Number(value).toLocaleString('pt-BR', {maximumFractionDigits: 3});
const workoutStart = today => workoutRange === 'all' ? '' : shiftDay(today, 1 - Number(workoutRange));
const workoutMetrics = {
    strength: {max_weight: ['Maior carga', 'kg'], volume: ['Volume', 'kg × rep'], reps: ['Repetições', 'rep'], sets: ['Séries', 'séries']},
    cardio: {minutes: ['Duração', 'min'], distance_km: ['Distância', 'km'], pace: ['Ritmo médio', 'min/km']}
};
function workoutValue(value, metric) {
    if (value == null) return 'Não medido';
    if (metric === 'pace') { const seconds = Math.round(value * 60); return `${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`; }
    return wn(value);
}
function renderWorkouts() {
    if (!workoutState) return empty('Carregando treinos…', '');
    const s = workoutState.summary;
    return `<div class="workout-toolbar"><div class="segmented" aria-label="Visualização dos treinos"><button data-action="workout-view" data-view="history" aria-pressed="${workoutView==='history'}" class="${workoutView==='history'?'selected':''}">Histórico</button><button data-action="workout-view" data-view="evolution" aria-pressed="${workoutView==='evolution'}" class="${workoutView==='evolution'?'selected':''}">Minha evolução</button></div><label>Período<select id="workout-range">${[['30','Últimos 30 dias'],['90','Últimos 90 dias'],['365','Últimos 365 dias'],['all','Todo o histórico']].map(([v,t])=>`<option value="${v}" ${v===workoutRange?'selected':''}>${t}</option>`).join('')}</select></label></div>
    <div class="overview-stats workout-stats">${overviewStat('dumbbell','Treinos registrados',s.sessions,'No período selecionado','lavender')}${overviewStat('calendar','Dias de atividade',s.days,'Cada dia conta','mint')}${overviewStat('target','Volume de musculação',wn(s.volume), 'kg × repetições no período','blue')}${overviewStat('clock','Tempo de cardio',wn(s.cardio_minutes)+'<small> min</small>','No período selecionado','peach')}</div>
    ${workoutTemplatesStrip()}
    ${workoutView==='history'?workoutHistory():workoutEvolution()}`;
}
function workoutHistory() {
    const sessions = workoutState.sessions.filter(s => [s.title,s.notes,...s.exercises.map(e=>e.name),...s.cardio.map(c=>c.name)].join(' ').toLocaleLowerCase().includes(query.toLocaleLowerCase()));
    return `
    <div class="workout-history">${sessions.map(s=>`<article class="panel workout-session"><div class="workout-session-head"><div><span class="eyebrow">${fmt(s.day)}</span><h2>${esc(s.title)}</h2></div>${actions('workouts',s.id)}</div><div class="workout-tags"><span>${s.metrics.sets} séries</span><span>${wn(s.metrics.volume)} kg × rep</span>${s.metrics.cardio_minutes?`<span>${wn(s.metrics.cardio_minutes)} min de cardio</span>`:''}</div><div class="workout-exercise-list">${s.exercises.map(e=>`<div><strong>${esc(e.name)}</strong><p>${e.sets.map((set,i)=>`<span>${i+1}. ${wn(set.weight)} kg × ${set.reps}</span>`).join(' · ')}</p>${e.notes?`<small>${esc(e.notes)}</small>`:''}</div>`).join('')}${s.cardio.map(c=>`<div><strong>${esc(c.name)} <span class="badge">Cardio</span></strong><p>${wn(c.minutes)} min${c.distance_km==null?' · Distância não medida':` · ${wn(c.distance_km)} km · ${workoutValue(c.minutes/c.distance_km,'pace')} min/km`}</p>${c.notes?`<small>${esc(c.notes)}</small>`:''}</div>`).join('')}</div>${s.notes?`<p class="workout-notes">${esc(s.notes)}</p>`:''}<div class="workout-session-footer"><button class="secondary" data-action="edit" data-table="workouts" data-id="${s.id}">Editar registro</button><button class="text-button" data-action="workout-template-from" data-id="${s.id}">Salvar como ficha</button><button class="text-button" data-action="workout-repeat" data-id="${s.id}">Repetir treino ↗</button></div></article>`).join('')}</div>${sessions.length?'':`<section class="panel">${empty(query?'Nenhum treino encontrado.':'Seu primeiro treino começa aqui.',query?'Busque outro título, exercício ou modalidade.':'Registre musculação, cardio ou os dois. Depois, compare seus resultados na aba Minha evolução.')}<div class="workout-empty-action"><button class="primary" data-action="workout-new">${uiIcon('plus')}Registrar treino</button></div></section>`}`;
}
function workoutEvolution() {
    const groups = workoutState[workoutKind];
    if (!groups.some(g=>g.key===workoutSelection)) workoutSelection = groups[0]?.key || '';
    const metrics = workoutMetrics[workoutKind];
    if (!metrics[workoutMetric]) workoutMetric = Object.keys(metrics)[0];
    const selected = groups.find(g=>g.key===workoutSelection);
    const [label,unit] = metrics[workoutMetric];
    const points = selected?.points || [];
    const measured = points.filter(p=>p[workoutMetric]!=null);
    const first = measured[0], last = measured.at(-1);
    const delta = measured.length>1 ? last[workoutMetric]-first[workoutMetric] : null;
    return `<section class="panel workout-evolution"><div class="section-head"><div><h2>Minha evolução</h2></div><div class="segmented"><button data-action="workout-kind" data-kind="strength" class="${workoutKind==='strength'?'selected':''}">Musculação</button><button data-action="workout-kind" data-kind="cardio" class="${workoutKind==='cardio'?'selected':''}">Cardio</button></div></div><div class="workout-chart-controls"><label>${workoutKind==='strength'?'Exercício':'Modalidade'}<select id="workout-selection">${groups.map(g=>`<option value="${esc(g.key)}" ${g.key===workoutSelection?'selected':''}>${esc(g.name)}</option>`).join('')||'<option>Sem registros</option>'}</select></label><label>Comparar<select id="workout-metric">${Object.entries(metrics).map(([k,v])=>`<option value="${k}" ${k===workoutMetric?'selected':''}>${v[0]} (${v[1]})</option>`).join('')}</select></label></div>
    ${points.length?`<div class="workout-comparison"><div><small>Último valor medido</small><strong>${last?workoutValue(last[workoutMetric],workoutMetric):'—'} <small>${unit}</small></strong>${last?`<span>${fmt(last.day)}</span>`:''}</div><div><small>Variação entre primeiro e último</small><strong>${delta==null?'—':(delta>0?'+':delta<0?'−':'')+workoutValue(Math.abs(delta),workoutMetric)} <small>${delta==null?'':unit}</small></strong><span>${delta==null?'Registre mais sessões para comparar':first[workoutMetric] ? `${delta>0?'+':''}${wn(delta/first[workoutMetric]*100)}% · ${fmt(first.day)} a ${fmt(last.day)}`:'Valor inicial zero: percentual indisponível'}</span></div>${workoutKind==='strength'?`<div><small>Maior carga no período</small><strong>${wn(Math.max(...points.map(p=>p.max_weight)))} <small>kg</small></strong><span>${points.length} sessão(ões) com este exercício</span></div>`:''}</div>${workoutChart(points,workoutMetric,label,unit)}<p class="hint workout-chart-note">Cada ponto representa uma sessão, em ordem de data e registro. Intervalos no eixo horizontal são iguais. Valores ausentes ficam sem ponto.${workoutMetric==='pace'?' Um ritmo menor representa menos tempo por km; compare condições semelhantes.':''}</p><details class="workout-data"><summary>Ver valores de todas as sessões (${points.length})</summary><div class="workout-table-wrap"><table><caption>${esc(selected.name)} · ${label}</caption><thead><tr><th>Data</th><th>Treino</th><th>${label} (${unit})</th></tr></thead><tbody>${points.map(p=>`<tr><td>${fmt(p.day)}</td><td>${esc(p.title)}</td><td>${workoutValue(p[workoutMetric],workoutMetric)}</td></tr>`).join('')}</tbody></table></div></details>`:empty('Ainda não há registros para comparar.', 'Registre um treino ou amplie o período selecionado.')}</section>`;
}
function workoutChart(points, metric, label, unit) {
    const values = points.filter(p=>p[metric]!=null).map(p=>p[metric]);
    if (!values.length) return empty('Sem medidas para este gráfico.', 'Informe a distância no cardio para acompanhar distância e ritmo.');
    const max = Math.max(1,...values)*1.15, x = i=>60+(points.length===1?.5:i/(points.length-1))*680, y = v=>210-v/max*175;
    let previous = null, lines = '', dots = '';
    points.forEach((p,i)=>{
        if (p[metric]==null) { previous=null; return; }
        if (previous!=null) lines += `<line x1="${x(previous)}" y1="${y(points[previous][metric])}" x2="${x(i)}" y2="${y(p[metric])}" class="workout-chart-line"/>`;
        dots += `<circle cx="${x(i)}" cy="${y(p[metric])}" r="4"><title>${fmt(p.day)} · ${esc(p.title)}: ${workoutValue(p[metric],metric)} ${unit}</title></circle>`;
        previous=i;
    });
    return `<div class="workout-chart"><svg viewBox="0 0 780 250" role="img" aria-label="${esc(label)} em ${points.length} sessões. Valores disponíveis na tabela abaixo.">${[0,.5,1].map(f=>`<line x1="60" x2="740" y1="${y(max*f)}" y2="${y(max*f)}" class="workout-gridline"/><text x="52" y="${y(max*f)+4}" text-anchor="end">${workoutValue(max*f,metric)}</text>`).join('')}${lines}${dots}<text x="60" y="240">${fmt(points[0].day)}</text><text x="740" y="240" text-anchor="end">${points.length>1?fmt(points.at(-1).day):''}</text></svg></div>`;
}
function bindWorkoutEvents() {
    $('#workout-range').onchange = async e => { workoutRange=e.target.value; try { await refresh(); } catch (err) { toast(err.message); } };
    if ($('#workout-selection')) $('#workout-selection').onchange = e => { workoutSelection=e.target.value; render(); };
    if ($('#workout-metric')) $('#workout-metric').onchange = e => { workoutMetric=e.target.value; render(); };
}
async function handleWorkoutAction(button) {
    const action = button.dataset.action;
    if (action==='workout-view') { workoutView=button.dataset.view; render(); }
    if (action==='workout-kind') { workoutKind=button.dataset.kind; workoutSelection=''; render(); }
    if (action==='workout-new') workoutEditor();
    if (action==='workout-repeat') workoutEditor(Number(button.dataset.id), true);
    if (action==='workout-template-start') workoutEditor(null, false, workoutState.templates.find(t=>t.id===Number(button.dataset.id)));
    if (action==='workout-template-from') workoutTemplateEditor(null, workoutState.sessions.find(s=>s.id===Number(button.dataset.id)));
}
function workoutEditor(id=null, repeat=false, template=null) {
    const original = workoutState?.sessions.find(s=>s.id===id);
    if (id && !original) return;
    workoutDraft = original ? JSON.parse(JSON.stringify(original)) : {title:'',day:state.today,notes:'',exercises:[],cardio:[]};
    if (template) {
        // Começa a ficha com as cargas e repetições da última vez de cada exercício.
        workoutDraft.title = template.name;
        workoutDraft.exercises = template.exercises.map(e => {
            const last = workoutLast(e.name);
            return {name: e.name, notes: '', sets: Array.from({length: e.sets}, (_, i) => last ? {...(last.sets[i] || last.sets.at(-1))} : {weight: 0, reps: 10})};
        });
        workoutDraft.cardio = template.cardio.map(c => ({name: c.name, minutes: c.minutes, distance_km: '', notes: ''}));
    }
    if (!id || repeat) {
        delete workoutDraft.id;
        delete workoutDraft.revision;
        workoutDraft.day=state.today;
        // crypto.randomUUID is unavailable on HTTP LAN origins.
        workoutDraft.client_id=Array.from(crypto.getRandomValues(new Uint8Array(16)), n=>n.toString(16).padStart(2,'0')).join('');
    }
    if (!$('#workout-editor')) setupWorkoutDialog();
    $('#workout-editor-title').textContent = template?`Ficha: ${template.name}`:repeat?'Repetir treino':id?'Editar treino':'Registrar treino';
    $('#workout-editor-hint').textContent = repeat?'Confira a data, as cargas e as repetições realizadas antes de salvar a nova sessão.':'Registre o que você realizou. Você pode incluir musculação, cardio ou ambos.';
    $('#workout-error').textContent='';
    drawWorkoutForm();
    $('#workout-editor').showModal();
    $('#workout-fields [name="title"]').focus();
}
function drawWorkoutForm() {
    const d=workoutDraft;
    $('#workout-fields').innerHTML=`<div class="workout-basics"><label>Nome do treino *<input name="title" required maxlength="200" placeholder="Ex.: Treino A · Peito e tríceps" value="${esc(d.title)}"></label><label>Data *<input name="day" type="date" required max="${state.today}" value="${esc(d.day)}"></label></div><div class="workout-form-section"><h3>Musculação</h3><p class="hint">A carga e as repetições podem variar em cada série. Carga em kg; use 0 para peso corporal sem carga adicional.</p><div id="workout-exercises">${d.exercises.map((e,i)=>`<fieldset class="workout-exercise" data-index="${i}"><legend>Exercício ${i+1}</legend><div class="workout-row-heading"><label>Exercício *<input name="exercise-name" required maxlength="120" list="exercise-names" value="${esc(e.name)}" placeholder="Ex.: Supino reto"></label><button type="button" class="icon workout-remove" data-wedit="remove-exercise" data-index="${i}" aria-label="Remover exercício ${i+1}">×</button></div>${workoutHint(e,i)}<div class="workout-set-head"><span>Série</span><span>Carga (kg)</span><span>Repetições</span><span></span></div>${e.sets.map((s,j)=>`<div class="workout-set"><span>${j+1}</span><input aria-label="Carga da série ${j+1}, exercício ${i+1}" name="weight" type="number" inputmode="decimal" min="0" max="2000" step="0.01" required value="${esc(s.weight)}"><input aria-label="Repetições da série ${j+1}, exercício ${i+1}" name="reps" type="number" inputmode="numeric" min="1" max="1000" step="1" required value="${esc(s.reps)}"><button type="button" class="icon workout-remove" data-wedit="remove-set" data-index="${i}" data-set="${j}" ${e.sets.length===1?'disabled':''} aria-label="Remover série ${j+1}, exercício ${i+1}">×</button></div>`).join('')}<button type="button" class="text-button" data-wedit="add-set" data-index="${i}" ${e.sets.length>=50?'disabled':''}>+ Série (repete a anterior)</button><label class="workout-note-label">Observação do exercício<input name="exercise-notes" maxlength="2000" value="${esc(e.notes)}" placeholder="Ex.: carga total, técnica, dificuldade…"></label></fieldset>`).join('')}</div><button type="button" class="secondary" data-wedit="add-exercise" ${d.exercises.length>=30?'disabled':''}>+ Exercício</button></div><div class="workout-form-section"><h3>Cardio</h3><div id="workout-cardio">${d.cardio.map((c,i)=>`<fieldset class="workout-cardio-item"><legend>Cardio ${i+1}</legend><div class="workout-row-heading"><label>Modalidade *<input name="cardio-name" required maxlength="120" list="cardio-names" value="${esc(c.name)}" placeholder="Ex.: Corrida na esteira"></label><button type="button" class="icon workout-remove" data-wedit="remove-cardio" data-index="${i}" aria-label="Remover cardio ${i+1}">×</button></div><div class="workout-cardio-numbers"><label>Duração (min) *<input name="minutes" type="number" inputmode="decimal" min="0.05" max="1440" step="0.05" required value="${esc(c.minutes)}"></label><label>Distância (km)<input name="distance" type="number" inputmode="decimal" min="0.001" max="1000" step="0.001" value="${esc(c.distance_km)}" placeholder="Opcional"></label></div><label class="workout-note-label">Observação do cardio<input name="cardio-notes" maxlength="2000" value="${esc(c.notes)}" placeholder="Ex.: inclinação, terreno, intensidade…"></label></fieldset>`).join('')}</div><button type="button" class="secondary" data-wedit="add-cardio" ${d.cardio.length>=20?'disabled':''}>+ Cardio</button></div><label>Observações do treino<textarea name="notes" maxlength="10000" placeholder="Como foi o treino?">${esc(d.notes)}</textarea></label><datalist id="exercise-names">${(workoutState?.exercise_names||[]).map(n=>`<option value="${esc(n)}"></option>`).join('')}</datalist><datalist id="cardio-names">${[...new Set([...(workoutState?.cardio_names||[]),'Caminhada','Corrida','Bicicleta','Elíptico','Escada'])].map(n=>`<option value="${esc(n)}"></option>`).join('')}</datalist>`;
}
function readWorkoutForm() {
    const root=$('#workout-fields'), value=(node,name)=>node.querySelector(`[name="${name}"]`).value;
    Object.assign(workoutDraft,{title:value(root,'title'),day:value(root,'day'),notes:value(root,'notes'),
        exercises:[...root.querySelectorAll('.workout-exercise')].map(e=>({name:value(e,'exercise-name'),notes:value(e,'exercise-notes'),sets:[...e.querySelectorAll('.workout-set')].map(s=>({weight:value(s,'weight'),reps:value(s,'reps')}))})),
        cardio:[...root.querySelectorAll('.workout-cardio-item')].map(c=>({name:value(c,'cardio-name'),minutes:value(c,'minutes'),distance_km:value(c,'distance'),notes:value(c,'cardio-notes')}))});
}
function setupWorkoutDialog() {
    document.body.insertAdjacentHTML('beforeend',`<dialog id="workout-editor" aria-labelledby="workout-editor-title"><form id="workout-form"><div class="modal-head"><div><p class="eyebrow">UM REGISTRO, MAIS CLAREZA</p><h2 id="workout-editor-title"></h2></div><button type="button" class="icon" data-wclose aria-label="Fechar treino">×</button></div><p id="workout-editor-hint" class="hint"></p><div class="rest-timer" aria-live="polite"><span>Descanso</span>${[60,90,120,180].map(s=>`<button type="button" class="secondary" data-rest="${s}">${s<120?s+'s':s/60+' min'}</button>`).join('')}<strong id="rest-display"></strong></div><div id="workout-fields"></div><p class="error" id="workout-error" role="alert"></p><div class="modal-actions"><button type="button" class="secondary" data-wclose>Cancelar</button><button type="submit" class="primary" id="workout-save">Salvar treino</button></div></form></dialog>`);
    const dialog=$('#workout-editor');
    dialog.addEventListener('cancel', e=>{if(workoutSaving)e.preventDefault();});
    dialog.addEventListener('click',e=>{
        if (workoutSaving) return;
        const rest=e.target.closest('[data-rest]');
        if(rest){startRestTimer(Number(rest.dataset.rest));return;}
        if(e.target.closest('[data-wclose]')) { stopRestTimer(); dialog.close(); refresh().catch(err=>toast(err.message)); return; }
        const b=e.target.closest('[data-wedit]');
        if(!b) return;
        readWorkoutForm();
        const i=Number(b.dataset.index), d=workoutDraft, action=b.dataset.wedit;
        if(action==='add-exercise' && d.exercises.length<30) d.exercises.push({name:'',notes:'',sets:[{weight:0,reps:10}]});
        if(action==='remove-exercise') d.exercises.splice(i,1);
        if(action==='add-set' && d.exercises[i].sets.length<50) d.exercises[i].sets.push({...d.exercises[i].sets.at(-1)});
        if(action==='remove-set' && d.exercises[i].sets.length>1) d.exercises[i].sets.splice(Number(b.dataset.set),1);
        if(action==='add-cardio' && d.cardio.length<20) d.cardio.push({name:'',minutes:20,distance_km:'',notes:''});
        if(action==='remove-cardio') d.cardio.splice(i,1);
        if(action==='suggest') { const last=workoutLast(d.exercises[i].name); if(last) d.exercises[i].sets=d.exercises[i].sets.map(s=>({...s,weight:last.suggested})); }
        drawWorkoutForm();
        const target=action==='add-exercise'?$('#workout-exercises').lastElementChild?.querySelector('input'):action==='add-cardio'?$('#workout-cardio').lastElementChild?.querySelector('input'):action==='add-set'?$('#workout-exercises').children[i]?.querySelector('.workout-set:last-of-type input'):null;
        (target || $('#workout-fields [name="title"]')).focus();
    });
    $('#workout-form').onsubmit=async e=>{
        e.preventDefault();
        if(workoutSaving)return;
        readWorkoutForm();
        workoutSaving=true;
        dialog.querySelectorAll('button,input,textarea').forEach(el=>el.disabled=true);
        try {
            await call('save_workout',workoutDraft,workoutDraft.id||null);
            stopRestTimer();
            dialog.close();
            toast('Treino salvo. Seu histórico e sua evolução foram atualizados.');
            await refresh();
        } catch(err) { if(dialog.open)$('#workout-error').textContent=err.message; else toast(err.message); }
        finally { workoutSaving=false; dialog.querySelectorAll('button,input,textarea').forEach(el=>el.disabled=false); if(dialog.open)drawWorkoutForm(); }
    };
}

/* ---------- Fichas, sugestão de carga e descanso (5.0) ---------- */
const workoutKey = name => String(name || '').trim().split(/\s+/).join(' ').toLocaleLowerCase();
const workoutLast = name => workoutState?.last_exercises?.[workoutKey(name)];
function workoutTemplatesStrip() {
    const templates = workoutState.templates || [];
    return `<section class="workout-templates"><div><span class="eyebrow">SUAS FICHAS</span><p>${templates.length ? 'Comece um treino já com os exercícios e as cargas da última vez.' : 'Em qualquer treino do histórico, use <strong>Salvar como ficha</strong> para criar Treino A, B, C…'}</p></div><div class="workout-template-list">${templates.map(t => `<article class="workout-template"><div><strong>${esc(t.name)}</strong><small>${t.exercises.length} exercício(s)${t.cardio.length ? ` · ${t.cardio.length} cardio` : ''}</small></div><button class="primary" data-action="workout-template-start" data-id="${t.id}">Começar</button>${actions('workout_templates', t.id)}</article>`).join('')}</div></section>`;
}
function workoutHint(exercise, index) {
    const last = workoutLast(exercise.name);
    if (!last) return '';
    const sets = last.sets.map(s => `${wn(s.weight)}×${s.reps}`).join(' · ');
    const top = Math.max(...last.sets.map(s => s.weight));
    return `<div class="workout-last"><span>Última vez (${fmt(last.day)}): ${sets}</span>${top > 0 ? `<button type="button" class="text-button" data-wedit="suggest" data-index="${index}">Tentar ${wn(last.suggested)} kg (+${wn(last.suggested - top)})</button>` : '<span>Peso corporal: tente uma repetição a mais.</span>'}</div>`;
}
function workoutTemplateEditor(id = null, session = null) {
    const template = id ? workoutState.templates.find(t => t.id === id) : null;
    if (id && !template) return;
    const body = template ? {exercises: template.exercises, cardio: template.cardio}
        : {exercises: session.exercises.map(e => ({name: e.name, sets: e.sets.length})), cardio: session.cardio.map(c => ({name: c.name, minutes: Math.max(1, Math.round(c.minutes))}))};
    editing = {table: 'workout_templates', id, body};
    $('#editor-title').textContent = template ? 'Renomear ficha' : 'Salvar como ficha';
    $('#fields').innerHTML = `<label>Nome da ficha *<input name="name" required maxlength="120" value="${esc(template?.name || session.title)}" placeholder="Ex.: Treino A · Peito e tríceps"></label><div class="template-preview">${body.exercises.map(e => `<span>${esc(e.name)} · ${e.sets} série(s)</span>`).join('')}${body.cardio.map(c => `<span>${esc(c.name)} · ${c.minutes} min</span>`).join('')}</div><p class="hint">Ao começar a ficha, as cargas e repetições vêm do último treino de cada exercício.</p>`;
    $('#form-error').textContent = '';
    $('#editor').showModal();
    $('#fields input').focus();
}
let restTimer = null, restEnd = 0;
function startRestTimer(seconds) {
    stopRestTimer();
    restEnd = Date.now() + seconds * 1000;
    const tick = () => {
        const left = Math.max(0, Math.ceil((restEnd - Date.now()) / 1000));
        const display = $('#rest-display');
        if (display) display.textContent = left ? `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}` : 'Bora! Próxima série';
        if (!left) { stopRestTimer(false); restAlert(); }
    };
    tick();
    restTimer = setInterval(tick, 250);
}
function stopRestTimer(clear = true) {
    clearInterval(restTimer);
    restTimer = null;
    if (clear && $('#rest-display')) $('#rest-display').textContent = '';
}
function restAlert() {
    try { navigator.vibrate?.([200, 100, 200]); } catch { /* sem vibração */ }
    try {
        const audio = new (window.AudioContext || window.webkitAudioContext)();
        [0, 0.25].forEach(delay => { const osc = audio.createOscillator(), gain = audio.createGain(); osc.frequency.value = 880; gain.gain.value = 0.15; osc.connect(gain).connect(audio.destination); osc.start(audio.currentTime + delay); osc.stop(audio.currentTime + delay + 0.15); });
    } catch { /* sem áudio */ }
}
