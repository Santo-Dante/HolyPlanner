'use strict';
// Planejar investimentos: histórico registrado + cenários fictícios do usuário.
let planState, planReal = false, planTableScenario = '', planDraft = null, planSaving = false, planChartMeta = null;
const PLAN_COLORS = 6;
const planEventKinds = {deposit: 'Aporte extra', withdrawal: 'Retirada'};

/* ---------- Cálculos puros (testados em test_planning.js) ---------- */
function planAddMonths(key, count) {
    const [y, m] = key.split('-').map(Number), index = y * 12 + m - 1 + count;
    return `${String(Math.floor(index / 12)).padStart(4, '0')}-${String(index % 12 + 1).padStart(2, '0')}`;
}
function planMonthIndex(key) { const [y, m] = key.split('-').map(Number); return y * 12 + m - 1; }
function planMonthsBetween(a, b) { return planMonthIndex(b) - planMonthIndex(a); }
function planMonthShort(key) {
    const names = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];
    return `${names[Number(key.slice(5)) - 1]}/${key.slice(2, 4)}`;
}
function planParseMoney(value) {
    const raw = String(value ?? '').trim();
    if (!raw) return 0;
    let clean = raw;
    if (raw.includes(',')) {
        if (!/^(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?$/.test(raw)) return NaN;
        clean = raw.replace(/\./g, '').replace(',', '.');
    } else if (!/^\d+(?:\.\d{1,2})?$/.test(raw)) return NaN;
    return Math.round(Number(clean) * 100);
}
function planParsePercent(value) {
    const raw = String(value ?? '').trim().replace(',', '.') || '0';
    return /^-?\d{1,3}(?:\.\d{1,2})?$/.test(raw) ? Math.round(Number(raw) * 100) : NaN;
}
const planPercent = bp => (bp / 100).toLocaleString('pt-BR', {maximumFractionDigits: 2}) + '%';
const planPercentInput = bp => String(bp / 100).replace('.', ',');

/** Projeta mês a mês: rendimento composto sobre o saldo, aportes no fim do mês. */
function planProject(scenario, startCents, startMonth) {
    const months = scenario.months || scenario.years * 12;
    const rate = Math.pow(1 + scenario.annual_rate_bp / 10000, 1 / 12) - 1;
    const inflation = Math.pow(1 + scenario.inflation_bp / 10000, 1 / 12) - 1;
    const raise = 1 + scenario.raise_bp / 10000;
    let balance = startCents, deposits = 0, withdrawals = 0, interest = 0, reached = null, shortfall = null;
    const ignored = (scenario.events || []).filter(e => !e.yearly && e.month <= startMonth).length;
    const points = [{i: 0, month: startMonth, nominal: balance, real: balance, deposits: 0, withdrawals: 0, interest: 0}];
    if (scenario.target_cents && balance >= scenario.target_cents) reached = startMonth;
    for (let i = 1; i <= months; i++) {
        const month = planAddMonths(startMonth, i);
        const gain = balance > 0 ? balance * rate : 0;
        balance += gain; interest += gain;
        let monthIn = scenario.monthly_cents * Math.pow(raise, Math.floor((i - 1) / 12)), monthOut = 0;
        for (const e of scenario.events || []) {
            const applies = e.month === month || (e.yearly && e.month < month && e.month.slice(5) === month.slice(5));
            if (!applies) continue;
            if (e.kind === 'withdrawal') monthOut += e.amount_cents; else monthIn += e.amount_cents;
        }
        balance += monthIn; deposits += monthIn;
        const taken = Math.min(monthOut, Math.max(0, balance));
        if (taken < monthOut && !shortfall) shortfall = month;
        balance -= taken; withdrawals += taken;
        if (!reached && scenario.target_cents && balance >= scenario.target_cents) reached = month;
        points.push({i, month, nominal: balance, real: balance / Math.pow(1 + inflation, i), deposits, withdrawals, interest});
    }
    const last = points.at(-1);
    return {points, start: startCents, final: last.nominal, finalReal: last.real, deposits, withdrawals, interest,
        monthlyIncome: last.nominal * rate, monthlyIncomeReal: last.real * rate, reached, shortfall, ignored,
        endMonth: last.month};
}

/** Menor aporte mensal (centavos) que atinge o alvo no fim do prazo; 0 se já atinge sem aportes. */
function planRequiredMonthly(scenario, startCents, startMonth, targetCents, months, targetReal = false) {
    const value = monthly => { const r = planProject({...scenario, months, monthly_cents: monthly}, startCents, startMonth); return targetReal ? r.finalReal : r.final; };
    if (value(0) >= targetCents) return 0;
    let low = 0, high = Math.max(100, targetCents);
    while (value(high) < targetCents && high < 1e15) high *= 2;
    for (let step = 0; step < 60 && high - low > 1; step++) {
        const middle = (low + high) / 2;
        if (value(middle) >= targetCents) high = middle; else low = middle;
    }
    return Math.ceil(high);
}

/** Meses até o saldo atingir o alvo, ou null se não atingir em maxMonths. */
function planTimeToTarget(scenario, startCents, startMonth, targetCents, targetReal = false, maxMonths = 1200) {
    const r = planProject({...scenario, months: maxMonths}, startCents, startMonth);
    const hit = r.points.find(p => (targetReal ? p.real : p.nominal) >= targetCents);
    return hit ? hit.i : null;
}

/** Rentabilidade anualizada aproximada (Dietz modificado) entre dois registros da carteira. */
function planPortfolioReturn(snapshots, capitalAt) {
    if (snapshots.length < 2) return null;
    const last = snapshots.at(-1), limit = new Date(last.day + 'T12:00:00');
    limit.setFullYear(limit.getFullYear() - 1);
    const minimum = limit.toISOString().slice(0, 10);
    const first = snapshots.find(s => s.day >= minimum && s.day < last.day) || snapshots.at(-2);
    const months = planMonthsBetween(first.day.slice(0, 7), last.day.slice(0, 7));
    if (months < 2 || !first.amount_cents) return null;
    const startCapital = capitalAt(first.day.slice(0, 7)), endCapital = capitalAt(last.day.slice(0, 7));
    const flows = startCapital == null || endCapital == null ? 0 : endCapital - startCapital;
    const base = first.amount_cents + flows / 2;
    if (base <= 0) return null;
    const period = (last.amount_cents - first.amount_cents - flows) / base;
    if (period <= -1) return null;
    return {annual_bp: Math.round((Math.pow(1 + period, 12 / months) - 1) * 10000), from: first.day, to: last.day, months};
}

/* ---------- Estado e formatação ---------- */
function planCompact(cents) {
    const value = cents / 100, abs = Math.abs(value);
    if (abs >= 1e6) return 'R$ ' + (value / 1e6).toLocaleString('pt-BR', {maximumFractionDigits: abs >= 1e8 ? 0 : 1}) + ' mi';
    if (abs >= 1e4) return 'R$ ' + Math.round(value / 1e3).toLocaleString('pt-BR') + ' mil';
    return 'R$ ' + Math.round(value).toLocaleString('pt-BR');
}
const planMoney = cents => money(Math.round(cents));
function planStart(scenario) {
    const p = planState;
    if (scenario.start_mode === 'custom') return {cents: scenario.start_cents, label: 'Valor informado no cenário'};
    if (scenario.start_mode === 'snapshot' && p.latest_snapshot) return {cents: p.latest_snapshot.amount_cents, label: `Valor da carteira em ${fmt(p.latest_snapshot.day)}`};
    return {cents: p.capital_cents, label: scenario.start_mode === 'snapshot' ? 'Capital registrado (nenhum valor da carteira informado)' : 'Capital registrado nas finanças'};
}
const planCurrentMonth = () => planState.today.slice(0, 7);
function planResults() {
    return planState.scenarios.map((s, index) => ({scenario: s, color: index % PLAN_COLORS, result: planProject(s, planStart(s).cents, planCurrentMonth())}));
}
function planCapitalAt(month) {
    const series = planState.series;
    if (!series.length || month < series[0].month) return null;
    let found = null;
    for (const row of series) { if (row.month <= month) found = row; else break; }
    return found?.capital_cents ?? null;
}

/* ---------- Renderização ---------- */
function renderPlanning() {
    if (!planState) return empty('Carregando seu planejamento…', '');
    const p = planState, latest = p.latest_snapshot;
    const capitalAtLatest = latest ? planCapitalAt(latest.day.slice(0, 7)) : null;
    const gain = latest && capitalAtLatest != null ? latest.amount_cents - capitalAtLatest : null;
    const results = planResults();
    const earned = planPortfolioReturn(p.snapshots, planCapitalAt);
    const matches = text => text.toLocaleLowerCase().includes(query.toLocaleLowerCase());
    const shown = results.filter(r => matches(r.scenario.name + ' ' + r.scenario.notes));
    return `<div class="plan-intro"><div><span class="eyebrow">O CAMINHO ATÉ AQUI E O QUE VEM DEPOIS</span><h2>Seu patrimônio ao longo do tempo.</h2><p>Compare o que você já registrou com cenários que você mesmo imagina: aportes, taxas, prazos, aportes extras e retiradas.</p></div><div class="plan-intro-actions"><button class="secondary" data-action="plan-record-new">${uiIcon('plus')}Registrar valor da carteira</button></div></div>
    <div class="overview-stats plan-stats">${overviewStat('trend', 'Valor informado da carteira', latest ? planCompact(latest.amount_cents) : '—', latest ? `${fmt(latest.day)}${gain == null ? '' : ` · <span class="${gain < 0 ? 'cash-out' : 'cash-in'}">${gain < 0 ? '−' : '+'}${planCompact(Math.abs(gain))}</span> sobre o aportado`}` : 'Informe o patrimônio do Investidor10', 'lavender')}${overviewStat('dollar', 'Capital aportado registrado', planCompact(p.capital_cents), 'Saldo inicial + aportes − resgates', 'mint')}${overviewStat('target', 'Rentabilidade da carteira', earned ? `≈ ${planPercent(earned.annual_bp)}<small> a.a.</small>` : '—', earned ? `Estimada de ${fmt(earned.from)} a ${fmt(earned.to)}` : 'Registre 2 valores com 2+ meses de distância', 'blue')}${overviewStat('repeat', 'Aporte médio mensal', planCompact(p.average_monthly_cents), 'Líquido dos últimos 6 meses completos', 'peach')}</div>
    ${planNudge()}
    ${planGoalPanel()}
    ${planChartPanel(results)}
    <div class="section-title plan-section-title"><h2>Seus cenários</h2><span>${results.length} CENÁRIO(S) · VALORES FICTÍCIOS</span></div>
    ${results.length ? `<div class="plan-scenarios">${shown.map(planScenarioCard).join('')}</div>${shown.length ? '' : empty('Nenhum cenário encontrado.', 'Busque por outro nome.')}` : `<section class="panel">${empty('Imagine o seu futuro com números.', 'Crie um cenário com aporte mensal, rentabilidade e prazo. Você pode incluir aportes extras e retiradas fictícias.')}<div class="plan-empty-actions"><button class="primary" data-action="plan-scenario-new">${uiIcon('plus')}Criar cenário</button><button class="secondary" data-action="plan-examples">Começar com 3 cenários de exemplo</button></div></section>`}
    ${results.length ? planYearTable(results) : ''}
    ${planRecordsPanel()}
    <p class="hint plan-disclaimer">As projeções usam taxas constantes informadas por você e servem para comparar possibilidades, não para prever resultados. Rentabilidade passada não garante rentabilidade futura. Impostos e taxas não são descontados: use uma taxa líquida se quiser considerá-los. "Valores de hoje" descontam a inflação estimada de cada cenário. Os cenários não alteram seus lançamentos nem o Investidor10.</p>`;
}

function planChartPanel(results) {
    const visible = results.filter(r => r.scenario.visible);
    const hasHistory = planState.series.length || planState.snapshots.length;
    const legend = [
        planState.series.length ? `<span class="plan-legend-item"><i class="plan-swatch history-capital"></i>Capital aportado registrado</span>` : '',
        planState.snapshots.length ? `<span class="plan-legend-item"><i class="plan-swatch history-wallet"></i>Valor informado da carteira</span>` : '',
        ...results.map(r => `<label class="plan-legend-item plan-toggle"><input type="checkbox" data-plan-visible="${r.scenario.id}" ${r.scenario.visible ? 'checked' : ''}><i class="plan-swatch dashed plan-c${r.color}"></i>${esc(r.scenario.name)}</label>`)
    ].join('');
    const body = hasHistory || visible.length ? planChart(visible) : empty('Seu gráfico aparece aqui.', 'Registre o valor da sua carteira ou crie um cenário para ver a linha do tempo.');
    return `<section class="panel plan-chart-panel"><div class="section-head"><div><span class="eyebrow">LINHA DO TEMPO</span><h2>Histórico e projeções</h2></div><div class="segmented" aria-label="Forma de exibir as projeções"><button data-action="plan-real" data-real="0" class="${planReal ? '' : 'selected'}" aria-pressed="${!planReal}">Valores nominais</button><button data-action="plan-real" data-real="1" class="${planReal ? 'selected' : ''}" aria-pressed="${planReal}">Valores de hoje</button></div></div>${body}<div class="plan-legend">${legend}</div><p class="hint plan-chart-hint">Linhas contínuas mostram seus registros; linhas tracejadas, os cenários a partir deste mês. Marque ou desmarque um cenário para compará-lo. ${planReal ? 'As projeções estão descontadas pela inflação estimada; o histórico continua em valores da época.' : 'Passe o mouse ou toque no gráfico para ver os valores de cada mês.'}</p></section>`;
}

function planChart(visible) {
    const p = planState, now = planCurrentMonth();
    const firstHistory = [p.series[0]?.month, p.snapshots[0]?.day.slice(0, 7)].filter(Boolean).sort()[0];
    const start = firstHistory && firstHistory < now ? firstHistory : now;
    const end = visible.reduce((a, r) => r.result.endMonth > a ? r.result.endMonth : a, planAddMonths(now, visible.length ? 0 : 3));
    const span = Math.max(1, planMonthsBetween(start, end));
    const values = [...p.series.map(r => r.capital_cents), ...p.snapshots.map(s => s.amount_cents),
        ...visible.flatMap(r => r.result.points.map(pt => planReal ? pt.real : pt.nominal))];
    const bottom = Math.min(0, ...values), rawTop = Math.max(100, ...values) * 1.04;
    // Marcas redondas no eixo (ex.: 250 mil, 500 mil, 750 mil).
    const magnitude = Math.pow(10, Math.floor(Math.log10((rawTop - bottom) / 4)));
    const top = bottom + 4 * [1, 2, 2.5, 5, 10].map(f => f * magnitude).find(v => bottom + v * 4 >= rawTop);
    const narrow = window.innerWidth < 720, W = narrow ? 440 : 820, H = narrow ? 300 : 320, L = narrow ? 66 : 74, R = 12, T = 16, B = 34;
    const x = month => L + (planMonthsBetween(start, month) / span) * (W - L - R);
    const xDay = day => x(day.slice(0, 7)) + ((Number(day.slice(8)) - 1) / 30) * ((W - L - R) / span);
    const y = v => T + (1 - (v - bottom) / (top - bottom)) * (H - T - B);
    const path = pts => pts.map(([px, py], i) => `${i ? 'L' : 'M'}${px.toFixed(1)},${py.toFixed(1)}`).join('');
    let svg = '';
    for (let k = 0; k <= 4; k++) {
        const v = bottom + (top - bottom) * k / 4;
        svg += `<line class="plan-grid" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${planCompact(v)}</text>`;
    }
    const years = Math.ceil(span / 12), step = Math.max(1, Math.ceil(years / (narrow ? 4 : 8)));
    for (let year = Number(start.slice(0, 4)) + 1; year <= Number(end.slice(0, 4)); year += step) {
        const key = `${year}-01`;
        svg += `<line class="plan-grid vertical" x1="${x(key)}" x2="${x(key)}" y1="${T}" y2="${H - B}"/><text x="${x(key)}" y="${H - 12}" text-anchor="middle">${year}</text>`;
    }
    if (span < 12) svg += `<text x="${L}" y="${H - 12}">${planMonthShort(start)}</text><text x="${W - R}" y="${H - 12}" text-anchor="end">${planMonthShort(end)}</text>`;
    if (start < now) svg += `<line class="plan-now" x1="${x(now)}" x2="${x(now)}" y1="${T}" y2="${H - B}"/><text class="plan-now-label" x="${x(now) + 6}" y="${T + 12}">Hoje</text>`;
    if (p.series.length) svg += `<path class="plan-line history-capital" d="${path(p.series.map(r => [x(r.month), y(r.capital_cents)]))}"/>`;
    if (p.snapshots.length) {
        svg += `<path class="plan-line history-wallet" d="${path(p.snapshots.map(s => [xDay(s.day), y(s.amount_cents)]))}"/>`;
        svg += p.snapshots.map(s => `<circle class="plan-dot history-wallet" cx="${xDay(s.day)}" cy="${y(s.amount_cents)}" r="4"/>`).join('');
    }
    for (const r of visible) {
        if (r.scenario.target_cents && r.scenario.target_cents <= top) svg += `<line class="plan-target plan-c${r.color}" x1="${x(now)}" x2="${W - R}" y1="${y(r.scenario.target_cents)}" y2="${y(r.scenario.target_cents)}"/>`;
        svg += `<path class="plan-line projection plan-c${r.color}" d="${path(r.result.points.map(pt => [x(pt.month), y(planReal ? pt.real : pt.nominal)]))}"/>`;
        const last = r.result.points.at(-1);
        svg += `<circle class="plan-dot plan-c${r.color}" cx="${x(last.month)}" cy="${y(planReal ? last.real : last.nominal)}" r="4"/>`;
    }
    planChartMeta = {start, span, L, R, W, visible};
    svg += `<line class="plan-cursor" id="plan-cursor" x1="0" x2="0" y1="${T}" y2="${H - B}" visibility="hidden"/><rect class="plan-hit" id="plan-hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}"/>`;
    return `<div class="plan-chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Gráfico de ${planMonthShort(start)} a ${planMonthShort(end)}. Os valores dos cenários estão nos cartões e na tabela ano a ano.">${svg}</svg><div class="plan-tooltip" id="plan-tooltip" hidden></div></div>`;
}

function planTooltip(event) {
    const meta = planChartMeta, svg = event.currentTarget.ownerSVGElement, tip = $('#plan-tooltip');
    if (!meta || !svg || !tip) return;
    const box = svg.getBoundingClientRect(), scale = box.width / meta.W;
    const offset = Math.round(((event.clientX - box.left) / scale - meta.L) / (meta.W - meta.L - meta.R) * meta.span);
    const month = planAddMonths(meta.start, Math.max(0, Math.min(meta.span, offset)));
    const rows = [], current = planCurrentMonth();
    const capital = month <= current ? planCapitalAt(month) : null;
    if (capital != null) rows.push(['history-capital', 'Capital registrado', capital]);
    const wallet = planState.snapshots.filter(s => s.day.slice(0, 7) <= month).at(-1);
    if (wallet && month <= current) rows.push(['history-wallet', `Carteira em ${fmt(wallet.day)}`, wallet.amount_cents]);
    for (const r of meta.visible) {
        const pt = month >= current ? r.result.points[planMonthsBetween(current, month)] : null;
        if (pt) rows.push([`plan-c${r.color}`, r.scenario.name, planReal ? pt.real : pt.nominal]);
    }
    const px = meta.L + (planMonthsBetween(meta.start, month) / meta.span) * (meta.W - meta.L - meta.R);
    const cursor = $('#plan-cursor');
    cursor.setAttribute('x1', px); cursor.setAttribute('x2', px); cursor.setAttribute('visibility', 'visible');
    tip.innerHTML = `<strong>${planMonthShort(month)}</strong>${rows.map(([cls, label, value]) => `<span><i class="plan-swatch ${cls}"></i>${esc(label)}<b>${planMoney(value)}</b></span>`).join('') || '<span>Sem valores neste mês</span>'}`;
    tip.hidden = false;
    const left = px * scale;
    tip.style.left = Math.min(Math.max(0, left - tip.offsetWidth / 2), box.width - tip.offsetWidth) + 'px';
}

function planScenarioCard(r) {
    const s = r.scenario, x = r.result, start = planStart(s);
    const params = [`${planMoney(s.monthly_cents)}/mês`, `${planPercent(s.annual_rate_bp)} ao ano`, `${s.years} ano${s.years === 1 ? '' : 's'}`];
    if (s.raise_bp) params.push(`aporte +${planPercent(s.raise_bp)} ao ano`);
    const target = s.target_cents ? (x.reached ? `<p class="plan-goal reached">${uiIcon('check')}Meta de ${planCompact(s.target_cents)} atingida em ${planMonthShort(x.reached)}</p>` : `<p class="plan-goal">${uiIcon('target')}<span>Meta de ${planCompact(s.target_cents)}: faltariam ${planMoney(s.target_cents - x.final)} no fim do prazo. Para chegar lá, o aporte precisaria ser de <strong>${planMoney(planRequiredMonthly(s, start.cents, planCurrentMonth(), s.target_cents, s.years * 12))}/mês</strong>.</span></p>`) : '';
    return `<article class="panel plan-card plan-c${r.color} ${s.visible ? '' : 'plan-hidden'}"><div class="plan-card-head"><div><span class="plan-card-dot"></span><h2>${esc(s.name)}</h2></div>${actions('investment_scenarios', s.id)}</div><p class="plan-params">${params.map(esc).join(' · ')}</p><div class="plan-final"><small>Em ${planMonthShort(x.endMonth)}</small><strong>${planMoney(x.final)}</strong><span>${planMoney(x.finalReal)} em valores de hoje · inflação ${planPercent(s.inflation_bp)} a.a.</span></div><dl class="plan-breakdown"><div><dt>Ponto de partida</dt><dd>${planMoney(start.cents)}<small>${esc(start.label)}</small></dd></div><div><dt>Aportes no período</dt><dd>${planMoney(x.deposits)}</dd></div>${x.withdrawals ? `<div><dt>Retiradas</dt><dd class="cash-out">−${planMoney(x.withdrawals)}</dd></div>` : ''}<div><dt>Rendimentos estimados</dt><dd>${planMoney(x.interest)}</dd></div><div><dt>Rendimento mensal no fim</dt><dd>≈ ${planMoney(x.monthlyIncome)}<small>${planMoney(x.monthlyIncomeReal)} em valores de hoje</small></dd></div></dl>${target}${s.events.length ? `<div class="plan-events"><small>Eventos fictícios</small>${s.events.map(e => `<span class="${e.kind}">${e.kind === 'withdrawal' ? '−' : '+'}${planCompact(e.amount_cents)} · ${esc(e.title)} · ${planMonthShort(e.month)}${e.yearly ? ' · todo ano' : ''}</span>`).join('')}</div>` : ''}${x.shortfall ? `<p class="finance-alert">O saldo não cobre todas as retiradas a partir de ${planMonthShort(x.shortfall)}. A projeção retira apenas o disponível.</p>` : ''}${x.ignored ? `<p class="hint">${x.ignored} evento(s) no mês atual ou no passado não entram na projeção.</p>` : ''}${s.notes ? `<p class="plan-notes">${esc(s.notes)}</p>` : ''}<div class="plan-card-footer"><button class="secondary" data-action="edit" data-table="investment_scenarios" data-id="${s.id}">${uiIcon('edit')}Editar valores</button><button class="text-button" data-action="plan-duplicate" data-id="${s.id}">Duplicar e testar ↗</button></div></article>`;
}

function planYearTable(results) {
    if (!results.some(r => String(r.scenario.id) === planTableScenario)) planTableScenario = String(results[0].scenario.id);
    const r = results.find(r => String(r.scenario.id) === planTableScenario), pts = r.result.points, rows = [];
    for (let i = 12; i < pts.length; i += 12) {
        const a = pts[i - 12], b = pts[i];
        rows.push(`<tr><td>Ano ${i / 12}<small>${planMonthShort(b.month)}</small></td><td>${planMoney(b.deposits - a.deposits)}</td><td>${b.withdrawals - a.withdrawals ? '−' + planMoney(b.withdrawals - a.withdrawals) : '—'}</td><td>${planMoney(b.interest - a.interest)}</td><td><strong>${planMoney(b.nominal)}</strong></td><td>${planMoney(b.real)}</td></tr>`);
    }
    return `<details class="panel plan-table" ${planTableOpen ? 'open' : ''}><summary><span><span class="eyebrow">DETALHES</span><strong>Ano a ano</strong></span><span class="hint">Aportes, retiradas e rendimentos de cada ano de um cenário</span></summary><label class="plan-table-select">Cenário<select id="plan-table-scenario">${results.map(x => `<option value="${x.scenario.id}" ${String(x.scenario.id) === planTableScenario ? 'selected' : ''}>${esc(x.scenario.name)}</option>`).join('')}</select></label><div class="workout-table-wrap"><table><thead><tr><th>Período</th><th>Aportes</th><th>Retiradas</th><th>Rendimentos</th><th>Saldo</th><th>Em valores de hoje</th></tr></thead><tbody>${rows.join('')}</tbody></table></div></details>`;
}
let planTableOpen = false, planRecordsAll = false;

function planRecordsPanel() {
    const all = [...planState.snapshots].reverse(), source = planState.investment_source;
    const records = planRecordsAll ? all : all.slice(0, 6);
    return `<section class="panel plan-records"><div class="section-head"><div><span class="eyebrow">SEU HISTÓRICO REAL</span><h2>Valor da carteira ao longo do tempo</h2></div><div class="plan-record-actions">${source?.enabled ? `<button class="secondary" data-action="plan-wallet">Ver patrimônio no Investidor10 ↗</button>` : ''}<button class="primary" data-action="plan-record-new">${uiIcon('plus')}Registrar valor</button></div></div><p class="hint plan-records-hint">Uma vez por mês, copie o patrimônio total mostrado no Investidor10 (ou no seu banco/corretora) e registre aqui. Assim o gráfico mostra a evolução real ao lado do capital aportado nas Finanças. Registrar a mesma data atualiza o valor.</p>${records.map((r, i) => {
        const previous = all[i + 1], delta = previous ? r.amount_cents - previous.amount_cents : null;
        return `<div class="plan-record-row"><div class="row-body"><div class="row-title">${money(r.amount_cents)}</div><div class="row-meta">${fmt(r.day)}${r.notes ? ' · ' + esc(r.notes) : ''}</div></div>${delta == null ? '<span class="badge">Primeiro registro</span>' : `<span class="badge ${delta < 0 ? 'high' : 'finance-paid'}">${delta < 0 ? '−' : '+'}${money(Math.abs(delta))} desde ${fmt(previous.day)}</span>`}${actions('investment_snapshots', r.id)}</div>`;
    }).join('') || empty('Nenhum valor registrado ainda.', 'Registre o patrimônio de hoje para começar sua linha do tempo.')}${all.length > 6 ? `<div class="plan-records-more"><button class="text-button" data-action="plan-records-all">${planRecordsAll ? 'Mostrar só os 6 mais recentes' : `Ver todos os registros (${all.length})`}</button></div>` : ''}</section>`;
}

/* ---------- Lembrete mensal ---------- */
function planNudge() {
    const latest = planState.latest_snapshot, now = planCurrentMonth();
    if (latest && latest.day.slice(0, 7) >= now) return '';
    if (!latest && !planState.capital_cents) return '';
    const month = new Date(now + '-15T12:00:00').toLocaleDateString('pt-BR', {month: 'long'});
    return `<div class="plan-nudge"><span>${uiIcon('calendar')}</span><p><strong>Registre o valor da carteira de ${month}.</strong> ${latest ? `O último é de ${fmt(latest.day)}.` : 'Assim o gráfico mostra a sua evolução real.'} Leva menos de um minuto.</p><button class="secondary" data-action="plan-record-new">Registrar agora</button></div>`;
}

/* ---------- Calculadora de meta: valor desejado + prazo ---------- */
let planGoal = null;
function planGoalState() {
    if (!planGoal) {
        planGoal = {mode: 'monthly', target: '500.000,00', until: '', monthly: '', start_mode: planState.latest_snapshot ? 'snapshot' : 'capital', start: '',
            rate: '10', inflation: '4', raise: '0', today: true, ...localRead('holy-plan-goal', {})};
        if (!/^\d{4}-\d{2}$/.test(planGoal.until) || planGoal.until <= planCurrentMonth()) planGoal.until = planAddMonths(planCurrentMonth(), 120);
        if (!planGoal.monthly) planGoal.monthly = moneyInput(planState.average_monthly_cents || 50000);
    }
    return planGoal;
}
function planDuration(months) {
    const years = Math.floor(months / 12), rest = months % 12;
    return [years ? `${years} ano${years === 1 ? '' : 's'}` : '', rest ? `${rest} ${rest === 1 ? 'mês' : 'meses'}` : ''].filter(Boolean).join(' e ') || 'menos de 1 mês';
}
function planGoalCompute(g) {
    const now = planCurrentMonth();
    const base = {annual_rate_bp: planParsePercent(g.rate), inflation_bp: planParsePercent(g.inflation), raise_bp: planParsePercent(g.raise), events: [], target_cents: 0, monthly_cents: 0};
    const target = planParseMoney(g.target), startCustom = planParseMoney(g.start), monthly = planParseMoney(g.monthly);
    if ([base.annual_rate_bp, base.inflation_bp, base.raise_bp, target, startCustom].some(Number.isNaN) || (g.mode === 'time' && Number.isNaN(monthly)))
        return {error: 'Confira os valores. Use números como 1.234,56 e percentuais como 10,5.'};
    if (!target) return {error: 'Informe o valor que você quer ter.'};
    if (base.annual_rate_bp < -5000 || base.annual_rate_bp > 10000 || base.inflation_bp < -2000 || base.inflation_bp > 10000 || base.raise_bp < -5000 || base.raise_bp > 10000)
        return {error: 'Use taxas entre −50% e 100% ao ano.'};
    const start = planStart({start_mode: g.start_mode, start_cents: startCustom}).cents;
    if (g.mode === 'monthly') {
        const months = /^\d{4}-\d{2}$/.test(g.until) ? planMonthsBetween(now, g.until) : 0;
        if (months < 1) return {error: 'Escolha um mês depois do atual em "Quero ter até".'};
        if (months > 720) return {error: 'Escolha um prazo de até 60 anos.'};
        const need = planRequiredMonthly(base, start, now, target, months, g.today);
        const result = planProject({...base, months, monthly_cents: need}, start, now);
        const average = planState.average_monthly_cents;
        const averageMonths = average ? planTimeToTarget({...base, monthly_cents: average}, start, now, target, g.today) : null;
        return {mode: 'monthly', months, need, result, target, start, base, average, averageMonths};
    }
    const months = planTimeToTarget({...base, monthly_cents: monthly}, start, now, target, g.today);
    const result = months == null ? null : planProject({...base, months: Math.max(1, months), monthly_cents: monthly}, start, now);
    return {mode: 'time', months, monthly, result, target, start, base};
}

function planGoalPanel() {
    const g = planGoalState(), p = planState, earned = planPortfolioReturn(p.snapshots, planCapitalAt);
    const options = [['snapshot', p.latest_snapshot ? `Valor atual da carteira · ${money(p.latest_snapshot.amount_cents)}` : 'Valor atual da carteira (nenhum registrado)'], ['capital', `Capital registrado · ${money(p.capital_cents)}`], ['custom', 'Outro valor']];
    return `<section class="panel plan-goal-panel" id="plan-goal"><div class="section-head"><div><span class="eyebrow">CALCULADORA DE META</span><h2>Quanto preciso para chegar lá?</h2></div><div class="segmented" aria-label="O que calcular"><button data-action="plan-goal-mode" data-mode="monthly" class="${g.mode === 'monthly' ? 'selected' : ''}" aria-pressed="${g.mode === 'monthly'}">Quanto investir por mês</button><button data-action="plan-goal-mode" data-mode="time" class="${g.mode === 'time' ? 'selected' : ''}" aria-pressed="${g.mode === 'time'}">Em quanto tempo chego lá</button></div></div>
    <div class="plan-goal-body"><div class="plan-goal-form">
      <div class="plan-goal-main"><label>Valor que quero ter (R$)<input name="target" inputmode="decimal" maxlength="20" value="${esc(g.target)}" placeholder="Ex.: 500.000,00"></label>${g.mode === 'monthly'
        ? `<label>Quero ter até<input name="until" type="month" min="${planAddMonths(planCurrentMonth(), 1)}" max="${planAddMonths(planCurrentMonth(), 720)}" value="${esc(g.until)}"><small class="plan-goal-span" id="plan-goal-span"></small></label>`
        : `<label>Posso investir por mês (R$)<input name="monthly" inputmode="decimal" maxlength="20" value="${esc(g.monthly)}" placeholder="0,00"></label>`}</div>
      <div class="plan-goal-grid"><label>Começar com<select name="start_mode">${options.map(([v, t]) => `<option value="${v}" ${g.start_mode === v ? 'selected' : ''}>${esc(t)}</option>`).join('')}</select></label><label id="plan-goal-start" ${g.start_mode === 'custom' ? '' : 'hidden'}>Valor inicial (R$)<input name="start" inputmode="decimal" maxlength="20" value="${esc(g.start)}" placeholder="0,00"></label></div>
      <div class="plan-goal-grid three"><label>Rentabilidade (% a.a.)<input name="rate" inputmode="decimal" maxlength="7" value="${esc(g.rate)}">${earned ? `<button type="button" class="text-button plan-use-rate" data-action="plan-goal-rate" data-rate="${planPercentInput(earned.annual_bp)}">Usar a da carteira (≈ ${planPercent(earned.annual_bp)})</button>` : ''}</label><label>Inflação (% a.a.)<input name="inflation" inputmode="decimal" maxlength="7" value="${esc(g.inflation)}"></label><label>Reajuste do aporte (% a.a.)<input name="raise" inputmode="decimal" maxlength="7" value="${esc(g.raise)}"></label></div>
      <label class="plan-check"><input type="checkbox" name="today" ${g.today ? 'checked' : ''}>O valor desejado é em dinheiro de hoje (corrigir pela inflação)</label>
    </div><div class="plan-goal-result" id="plan-goal-result" aria-live="polite"></div></div></section>`;
}

function updatePlanGoal() {
    const root = $('#plan-goal');
    if (!root) return;
    const g = planGoalState(), field = name => root.querySelector(`[name="${name}"]`);
    for (const name of ['target', 'until', 'monthly', 'start_mode', 'start', 'rate', 'inflation', 'raise']) if (field(name)) g[name] = field(name).value;
    g.today = field('today').checked;
    localWrite('holy-plan-goal', g);
    $('#plan-goal-start').hidden = g.start_mode !== 'custom';
    const c = planGoalCompute(g), box = $('#plan-goal-result');
    if ($('#plan-goal-span')) $('#plan-goal-span').textContent = c.months > 0 && g.mode === 'monthly' ? `Daqui a ${planDuration(c.months)}` : '';
    if (c.error) { box.innerHTML = `<p class="hint">${esc(c.error)}</p>`; return; }
    const r = c.result, real = g.today ? ' em dinheiro de hoje' : '';
    const nominalNote = r && g.today && c.base.inflation_bp ? `<div><dt>Valor na época (com inflação)</dt><dd>${planMoney(r.final)}</dd></div>` : '';
    let html;
    if (c.mode === 'monthly') {
        const compare = !c.average ? '' : c.average >= c.need
            ? `<p class="plan-goal-note good">${uiIcon('check')}<span>Seu aporte médio atual (${planMoney(c.average)}) já é suficiente${c.averageMonths != null ? `: nesse ritmo, chegaria em ${planMonthShort(planAddMonths(planCurrentMonth(), c.averageMonths))}` : ''}.</span></p>`
            : `<p class="plan-goal-note"><span>Seu aporte médio atual é ${planMoney(c.average)}: faltariam <strong>${planMoney(c.need - c.average)}/mês</strong>. Nesse ritmo, ${c.averageMonths != null ? `chegaria lá em ${planMonthShort(planAddMonths(planCurrentMonth(), c.averageMonths))} (${planDuration(c.averageMonths)})` : 'levaria mais de 100 anos'}.</span></p>`;
        html = `<small>PARA TER ${planCompact(c.target).toUpperCase()}${real.toUpperCase()} EM ${planMonthShort(planAddMonths(planCurrentMonth(), c.months)).toUpperCase()}</small>${c.need === 0
            ? `<strong class="plan-goal-value">R$ 0<small>/mês</small></strong><span>Você chega lá sem novos aportes, só com o rendimento de ${planMoney(c.start)}.</span>`
            : `<strong class="plan-goal-value">${planMoney(c.need)}<small>/mês</small></strong><span>durante ${planDuration(c.months)}${c.base.raise_bp ? `, com reajuste de ${planPercent(c.base.raise_bp)} ao ano` : ''}</span>`}
            <dl><div><dt>Começa com</dt><dd>${planMoney(c.start)}</dd></div><div><dt>Total aportado</dt><dd>${planMoney(r.deposits)}</dd></div><div><dt>Rendimentos</dt><dd>${planMoney(r.interest)}</dd></div>${nominalNote}</dl>${compare}`;
    } else if (c.months == null) {
        html = `<small>PARA TER ${planCompact(c.target).toUpperCase()}${real.toUpperCase()} INVESTINDO ${planMoney(c.monthly).toUpperCase()}/MÊS</small><strong class="plan-goal-value">Mais de 100 anos</strong><span>Aumente o aporte, a rentabilidade ou ajuste o valor desejado.</span>`;
    } else {
        html = `<small>PARA TER ${planCompact(c.target).toUpperCase()}${real.toUpperCase()} INVESTINDO ${planMoney(c.monthly).toUpperCase()}/MÊS</small><strong class="plan-goal-value">${c.months === 0 ? 'Você já chegou lá' : planDuration(c.months)}</strong><span>${c.months === 0 ? 'O ponto de partida já alcança o valor desejado.' : `em ${planMonthShort(r.endMonth)}`}</span>${c.months ? `<dl><div><dt>Começa com</dt><dd>${planMoney(c.start)}</dd></div><div><dt>Total aportado</dt><dd>${planMoney(r.deposits)}</dd></div><div><dt>Rendimentos</dt><dd>${planMoney(r.interest)}</dd></div>${nominalNote}</dl>` : ''}`;
    }
    const canSave = c.months != null && c.months > 0;
    box.innerHTML = html + (canSave ? `<button class="primary" data-action="plan-goal-save">${uiIcon('plus')}Salvar como cenário</button><p class="hint">O cenário aparece no gráfico com esta meta e pode ser ajustado depois.</p>` : '');
}

async function savePlanGoal(button) {
    const g = planGoalState(), c = planGoalCompute(g);
    if (c.error || c.months == null || c.months < 1) return;
    const monthly = c.mode === 'monthly' ? c.need : c.monthly;
    const target = g.today ? Math.round(c.target * Math.pow(1 + c.base.inflation_bp / 10000, c.months / 12)) : c.target;
    const end = planAddMonths(planCurrentMonth(), c.months);
    button.disabled = true;
    try {
        await call('save_scenario', {name: `Meta de ${planCompact(c.target)} em ${planMonthShort(end)}`, start_mode: g.start_mode, start: moneyInput(planParseMoney(g.start)),
            monthly: moneyInput(monthly), annual_rate: g.rate, inflation: g.inflation, raise: g.raise, years: Math.min(60, Math.max(1, Math.ceil(c.months / 12))),
            target: moneyInput(target), notes: `Criado pela calculadora de meta: ${money(c.target)}${g.today ? ' em dinheiro de hoje' : ''} até ${planMonthShort(end)}.`, events: []});
        await afterMutation({}, false, 'Cenário criado a partir da sua meta.');
    } catch (err) { toast(err.message); button.disabled = false; }
}

/* ---------- Eventos ---------- */
function bindPlanningEvents() {
    const goal = $('#plan-goal');
    if (goal) {
        goal.addEventListener('input', updatePlanGoal);
        goal.addEventListener('change', updatePlanGoal);
        updatePlanGoal();
    }
    const hit = $('#plan-hit');
    if (hit) {
        hit.addEventListener('pointermove', planTooltip);
        hit.addEventListener('pointerdown', planTooltip);
        hit.addEventListener('pointerleave', () => { $('#plan-tooltip').hidden = true; $('#plan-cursor')?.setAttribute('visibility', 'hidden'); });
    }
    $('.plan-table')?.addEventListener('toggle', e => { planTableOpen = e.target.open; });
    $('#plan-table-scenario')?.addEventListener('change', e => { planTableScenario = e.target.value; render(); });
    document.querySelectorAll('[data-plan-visible]').forEach(box => box.addEventListener('change', async () => {
        box.disabled = true;
        try { await call('set_scenario_visible', Number(box.dataset.planVisible), box.checked); await refresh(); }
        catch (err) { toast(err.message); box.disabled = false; }
    }));
}

async function handlePlanAction(b) {
    const action = b.dataset.action;
    if (action === 'plan-goto') { $('nav [data-page="planning"]').click(); return; }
    if (action === 'plan-goal-mode') { planGoalState().mode = b.dataset.mode; localWrite('holy-plan-goal', planGoal); render(); return; }
    if (action === 'plan-goal-rate') { $('#plan-goal [name="rate"]').value = b.dataset.rate; updatePlanGoal(); return; }
    if (action === 'plan-goal-save') { await savePlanGoal(b); return; }
    if (action === 'plan-records-all') { planRecordsAll = !planRecordsAll; render(); return; }
    if (action === 'plan-real') { planReal = b.dataset.real === '1'; render(); return; }
    if (action === 'plan-scenario-new') { planScenarioEditor(); return; }
    if (action === 'plan-record-new') { planRecordEditor(); return; }
    if (action === 'plan-duplicate') { planScenarioEditor(Number(b.dataset.id), true); return; }
    if (action === 'plan-wallet') {
        const source = planState.investment_source;
        if (window.holyWeb) {
            const link = document.createElement('a');
            link.href = source.wallet_url + '/patrimony'; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.click();
            return;
        }
        await call('open_investidor10', 'patrimony', false);
        toast('Patrimônio aberto na janela do Investidor10.');
        return;
    }
    if (action === 'plan-examples') {
        b.disabled = true;
        const monthly = moneyInput(planState.average_monthly_cents || 50000);
        try {
            for (const [name, rate, notes] of [['Conservador', '8', 'Exemplo editável: taxa mais baixa e previsível.'], ['Moderado', '10', 'Exemplo editável: carteira equilibrada.'], ['Arrojado', '12', 'Exemplo editável: mais risco; retorno esperado maior e incerto.']])
                await call('save_scenario', {name, start_mode: 'snapshot', monthly, annual_rate: rate, inflation: '4', raise: '0', years: 10, target: '', notes, events: []});
            await afterMutation({}, false, 'Três cenários de exemplo criados. Ajuste os valores para a sua realidade.');
        } catch (err) { toast(err.message); b.disabled = false; }
    }
}

/* ---------- Valor da carteira (usa o editor padrão) ---------- */
function planRecordEditor(id = null) {
    const r = id ? planState.snapshots.find(s => s.id === id) : {day: planState.today, amount_cents: planState.latest_snapshot?.amount_cents || 0, notes: ''};
    if (!r) return;
    editing = {table: 'investment_snapshots', id};
    $('#editor-title').textContent = id ? 'Editar valor da carteira' : 'Registrar valor da carteira';
    $('#fields').innerHTML = `<div class="form-grid"><label>Data *<input name="day" type="date" required min="1900-01-01" max="${planState.today}" value="${esc(r.day)}"></label>${moneyField('Patrimônio total (R$) *', 'amount', r.amount_cents)}</div><label>Notas<input name="notes" maxlength="2000" value="${esc(r.notes)}" placeholder="Ex.: valor do Investidor10, inclui previdência…"></label><p class="hint">Informe o valor de mercado de todos os seus investimentos nesta data. Ele não altera o saldo disponível nem os lançamentos.</p>`;
    $('#form-error').textContent = '';
    $('#editor').showModal();
    $('#fields [name="amount"]').focus();
}

/* ---------- Editor de cenário com prévia ao vivo ---------- */
function planScenarioEditor(id = null, duplicate = false) {
    const original = id ? planState.scenarios.find(s => s.id === id) : null;
    if (id && !original) return;
    const s = original || {name: planState.scenarios.length ? `Cenário ${planState.scenarios.length + 1}` : 'Meu plano', start_mode: planState.latest_snapshot ? 'snapshot' : 'capital', start_cents: 0,
        monthly_cents: planState.average_monthly_cents || 50000, annual_rate_bp: 1000, inflation_bp: 400, raise_bp: 0, years: 10, target_cents: 0, notes: '', events: [], visible: 1};
    planDraft = {id: duplicate ? null : id, name: duplicate ? `${s.name} (cópia)` : s.name, start_mode: s.start_mode, start: moneyInput(s.start_cents), monthly: moneyInput(s.monthly_cents),
        annual_rate: planPercentInput(s.annual_rate_bp), inflation: planPercentInput(s.inflation_bp), raise: planPercentInput(s.raise_bp), years: s.years,
        target: s.target_cents ? moneyInput(s.target_cents) : '', notes: s.notes, visible: s.visible,
        events: s.events.map(e => ({title: e.title, month: e.month, kind: e.kind, amount: moneyInput(e.amount_cents), yearly: Boolean(e.yearly)}))};
    if (!$('#plan-editor')) setupPlanDialog();
    $('#plan-editor-title').textContent = duplicate ? 'Duplicar e testar' : id ? 'Editar cenário' : 'Novo cenário';
    $('#plan-error').textContent = '';
    drawPlanForm();
    $('#plan-editor').showModal();
    $('#plan-fields [name="name"]').focus();
}

function drawPlanForm() {
    const d = planDraft, p = planState, next = planAddMonths(planCurrentMonth(), 1);
    const options = [['snapshot', p.latest_snapshot ? `Último valor da carteira · ${money(p.latest_snapshot.amount_cents)}` : 'Último valor da carteira (nenhum registrado)'], ['capital', `Capital registrado nas finanças · ${money(p.capital_cents)}`], ['custom', 'Outro valor (fictício)']];
    $('#plan-fields').innerHTML = `<label>Nome do cenário *<input name="name" required maxlength="80" value="${esc(d.name)}" placeholder="Ex.: Aposentadoria, Viagem, Pessimista"></label>
    <div class="plan-form-section"><h3>Ponto de partida</h3><div class="plan-form-grid"><label>Começar com<select name="start_mode">${options.map(([v, t]) => `<option value="${v}" ${d.start_mode === v ? 'selected' : ''}>${esc(t)}</option>`).join('')}</select></label><label ${d.start_mode === 'custom' ? '' : 'hidden'} id="plan-start-field">Valor inicial (R$)<input name="start" inputmode="decimal" maxlength="20" value="${esc(d.start)}" placeholder="0,00"></label></div></div>
    <div class="plan-form-section"><h3>Premissas</h3><div class="plan-form-grid three"><label>Aporte mensal (R$)<input name="monthly" inputmode="decimal" maxlength="20" value="${esc(d.monthly)}" placeholder="0,00"></label><label>Rentabilidade (% ao ano)<input name="annual_rate" inputmode="decimal" maxlength="7" value="${esc(d.annual_rate)}"></label><label>Prazo (anos)<input name="years" type="number" min="1" max="60" step="1" required value="${esc(d.years)}"></label><label>Reajuste do aporte (% ao ano)<input name="raise" inputmode="decimal" maxlength="7" value="${esc(d.raise)}"></label><label>Inflação estimada (% ao ano)<input name="inflation" inputmode="decimal" maxlength="7" value="${esc(d.inflation)}"></label><label>Meta de patrimônio (R$)<input name="target" inputmode="decimal" maxlength="20" value="${esc(d.target)}" placeholder="Opcional"></label></div><p class="hint">Use valores fictícios à vontade. A rentabilidade é aplicada todo mês sobre o saldo; o aporte entra no fim de cada mês e é reajustado a cada 12 meses.</p></div>
    <div class="plan-form-section"><h3>Eventos fictícios</h3><p class="hint">Aportes extras (13º, bônus, venda de um bem) ou retiradas (carro, viagem, entrada de um imóvel) em um mês específico, a partir de ${planMonthShort(next)}.</p><div id="plan-events">${d.events.map((e, i) => `<fieldset class="plan-event" data-index="${i}"><legend>Evento ${i + 1}</legend><div class="plan-event-grid"><label>Descrição *<input name="event-title" required maxlength="120" value="${esc(e.title)}" placeholder="Ex.: 13º salário"></label><label>Tipo<select name="event-kind">${Object.entries(planEventKinds).map(([v, t]) => `<option value="${v}" ${e.kind === v ? 'selected' : ''}>${t}</option>`).join('')}</select></label><label>Mês *<input name="event-month" type="month" required min="1900-01" max="2100-12" value="${esc(e.month)}"></label><label>Valor (R$) *<input name="event-amount" inputmode="decimal" required maxlength="20" value="${esc(e.amount)}" placeholder="0,00"></label></div><div class="plan-event-foot"><label class="plan-check"><input type="checkbox" name="event-yearly" ${e.yearly ? 'checked' : ''}>Repetir todo ano neste mês</label><button type="button" class="text-button" data-pedit="remove-event" data-index="${i}">Remover evento</button></div></fieldset>`).join('')}</div><button type="button" class="secondary" data-pedit="add-event" ${d.events.length >= 60 ? 'disabled' : ''}>+ Evento</button></div>
    <label>Notas<textarea name="notes" maxlength="2000" placeholder="O que você quer testar neste cenário?">${esc(d.notes)}</textarea></label>
    <div class="plan-preview" id="plan-preview" aria-live="polite"></div>`;
    updatePlanPreview();
}

function readPlanForm() {
    const root = $('#plan-fields'), v = name => root.querySelector(`[name="${name}"]`).value;
    Object.assign(planDraft, {name: v('name'), start_mode: v('start_mode'), start: v('start'), monthly: v('monthly'), annual_rate: v('annual_rate'), inflation: v('inflation'),
        raise: v('raise'), years: v('years'), target: v('target'), notes: v('notes'),
        events: [...root.querySelectorAll('.plan-event')].map(f => ({title: f.querySelector('[name="event-title"]').value, kind: f.querySelector('[name="event-kind"]').value,
            month: f.querySelector('[name="event-month"]').value, amount: f.querySelector('[name="event-amount"]').value, yearly: f.querySelector('[name="event-yearly"]').checked}))});
}

function planDraftScenario(d) {
    const years = Number(d.years);
    const sc = {start_mode: d.start_mode, start_cents: planParseMoney(d.start), monthly_cents: planParseMoney(d.monthly), annual_rate_bp: planParsePercent(d.annual_rate),
        inflation_bp: planParsePercent(d.inflation), raise_bp: planParsePercent(d.raise), years, target_cents: planParseMoney(d.target),
        events: d.events.filter(e => /^\d{4}-\d{2}$/.test(e.month)).map(e => ({...e, amount_cents: planParseMoney(e.amount)}))};
    const invalid = [sc.start_cents, sc.monthly_cents, sc.annual_rate_bp, sc.inflation_bp, sc.raise_bp, sc.target_cents, ...sc.events.map(e => e.amount_cents)].some(Number.isNaN)
        || !Number.isInteger(years) || years < 1 || years > 60;
    return invalid ? null : sc;
}

function updatePlanPreview() {
    readPlanForm();
    $('#plan-start-field').hidden = planDraft.start_mode !== 'custom';
    const sc = planDraftScenario(planDraft), box = $('#plan-preview');
    if (!sc) { box.innerHTML = '<p class="hint">Confira os valores para ver a prévia. Use números como 1.234,56 e percentuais como 10,5.</p>'; return; }
    const r = planProject(sc, planStart(sc).cents, planCurrentMonth());
    const W = 300, H = 60, max = Math.max(1, ...r.points.map(p => p.nominal));
    const line = key => r.points.map((p, i) => `${i ? 'L' : 'M'}${(i / (r.points.length - 1) * W).toFixed(1)},${(H - Math.max(0, p[key]) / max * (H - 4) - 2).toFixed(1)}`).join('');
    box.innerHTML = `<div class="plan-preview-head"><div><small>PRÉVIA · EM ${planMonthShort(r.endMonth).toUpperCase()}</small><strong>${planMoney(r.final)}</strong><span>${planMoney(r.finalReal)} em valores de hoje</span></div><svg viewBox="0 0 ${W} ${H}" aria-hidden="true" preserveAspectRatio="none"><path class="plan-preview-real" d="${line('real')}"/><path class="plan-preview-line" d="${line('nominal')}"/></svg></div><dl><div><dt>Começa com</dt><dd>${planMoney(r.start)}</dd></div><div><dt>Você aporta</dt><dd>${planMoney(r.deposits)}</dd></div>${r.withdrawals ? `<div><dt>Retira</dt><dd>−${planMoney(r.withdrawals)}</dd></div>` : ''}<div><dt>Rendimentos</dt><dd>${planMoney(r.interest)}</dd></div></dl>${sc.target_cents ? `<p>${r.reached ? `Meta atingida em ${planMonthShort(r.reached)}.` : 'Meta não atingida no prazo.'}</p>` : ''}${r.shortfall ? `<p class="cash-out">O saldo não cobre as retiradas a partir de ${planMonthShort(r.shortfall)}.</p>` : ''}${r.ignored ? `<p>${r.ignored} evento(s) no mês atual ou no passado não entram na projeção.</p>` : ''}`;
}

function setupPlanDialog() {
    document.body.insertAdjacentHTML('beforeend', `<dialog id="plan-editor" aria-labelledby="plan-editor-title"><form id="plan-form"><div class="modal-head"><div><p class="eyebrow">E SE…?</p><h2 id="plan-editor-title"></h2></div><button type="button" class="icon" data-pclose aria-label="Fechar cenário">×</button></div><div id="plan-fields"></div><p class="error" id="plan-error" role="alert"></p><div class="modal-actions"><button type="button" class="secondary" data-pclose>Cancelar</button><button type="submit" class="primary">Salvar cenário</button></div></form></dialog>`);
    const dialog = $('#plan-editor');
    dialog.addEventListener('cancel', e => { if (planSaving) e.preventDefault(); });
    dialog.addEventListener('input', () => { if (!planSaving) updatePlanPreview(); });
    dialog.addEventListener('change', () => { if (!planSaving) updatePlanPreview(); });
    dialog.addEventListener('click', e => {
        if (planSaving) return;
        if (e.target.closest('[data-pclose]')) { dialog.close(); return; }
        const b = e.target.closest('[data-pedit]');
        if (!b) return;
        readPlanForm();
        if (b.dataset.pedit === 'add-event' && planDraft.events.length < 60) planDraft.events.push({title: '', kind: 'deposit', month: planAddMonths(planCurrentMonth(), 1), amount: '', yearly: false});
        if (b.dataset.pedit === 'remove-event') planDraft.events.splice(Number(b.dataset.index), 1);
        drawPlanForm();
        (b.dataset.pedit === 'add-event' ? $('#plan-events').lastElementChild?.querySelector('input') : $('#plan-fields [name="name"]'))?.focus();
    });
    $('#plan-form').onsubmit = async e => {
        e.preventDefault();
        if (planSaving) return;
        readPlanForm();
        planSaving = true;
        dialog.querySelectorAll('button,input,select,textarea').forEach(el => el.disabled = true);
        try {
            const {id, ...payload} = planDraft;
            await call('save_scenario', payload, id || null);
            dialog.close();
            toast('Cenário salvo. O gráfico foi atualizado.');
            await refresh();
        } catch (err) { if (dialog.open) $('#plan-error').textContent = err.message; else toast(err.message); }
        finally { planSaving = false; dialog.querySelectorAll('button,input,select,textarea').forEach(el => el.disabled = false); if (dialog.open) drawPlanForm(); }
    };
}

// O gráfico tem uma versão compacta para telas estreitas.
let planResizeTimer, planWasNarrow = window.innerWidth < 720;
window.addEventListener('resize', () => {
    clearTimeout(planResizeTimer);
    planResizeTimer = setTimeout(() => {
        const narrow = window.innerWidth < 720;
        if (narrow !== planWasNarrow && typeof page !== 'undefined' && page === 'planning' && planState && !document.querySelector('dialog[open]')) render();
        planWasNarrow = narrow;
    }, 200);
});
