'use strict';
let financeMonth = '', financeState, financeView = 'overview';
let financeQuery = '', financeKind = '', financeStatus = '', financeCategory = '';
const financeKinds = {income: 'Entrada', expense: 'Saída', investment: 'Aporte', redemption: 'Resgate', yield: 'Rendimento recebido'};
const money = cents => (cents / 100).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
const moneyInput = cents => (cents / 100).toFixed(2).replace('.', ',');
const monthLabel = month => new Date(month + '-01T12:00:00').toLocaleDateString('pt-BR', {month: 'long', year: 'numeric'});
const moneyField = (label, name, cents = 0) => `<label>${label}<input name="${name}" inputmode="decimal" type="text" required maxlength="20" placeholder="0,00" value="${esc(moneyInput(cents))}"></label>`;

function filteredFinanceRows() {
    const q = financeQuery.toLocaleLowerCase();
    return financeState.transactions.filter(r => (!financeKind || r.kind === financeKind) &&
        (!financeStatus || r.status === financeStatus) && (!financeCategory || r.category === financeCategory) &&
        [r.title, r.category, r.account, r.asset, r.notes].join(' ').toLocaleLowerCase().includes(q));
}

function financeRow(r) {
    const paid = r.status === 'paid', outgoing = ['expense', 'investment'].includes(r.kind);
    const overdue = !paid && r.day < state.today;
    return `<article class="finance-row"><button class="check ${paid ? 'done' : ''}" data-action="finance-toggle" data-id="${r.id}" aria-label="${paid ? 'Marcar como previsto' : 'Efetivar lançamento'}" title="${paid ? 'Marcar como previsto' : 'Efetivar lançamento'}">${paid ? '✓' : ''}</button><div class="row-body"><div class="row-title">${esc(r.title)}</div><div class="row-meta">${fmt(r.day)} · ${esc(r.category)}${r.account ? ' · '+esc(r.account) : ''}${r.asset ? ' · '+esc(r.asset) : ''}</div>${r.notes ? `<div class="finance-notes">${esc(r.notes)}</div>` : ''}</div><div class="finance-row-amount"><strong class="${outgoing ? 'cash-out' : 'cash-in'}">${outgoing ? '−' : '+'} ${money(r.amount_cents)}</strong><span>${financeKinds[r.kind]}</span></div><span class="badge ${overdue ? 'high' : paid ? 'finance-paid' : 'finance-pending'}">${overdue ? 'Previsto · vencido' : paid ? 'Efetivado' : 'Previsto'}</span><div class="finance-row-actions">${actions('finance_transactions', r.id)}</div></article>`;
}

function financeFilters() {
    return `<div class="toolbar finance-filters"><input id="finance-search" type="search" placeholder="Buscar descrição, conta, investimento…" aria-label="Buscar lançamentos" value="${esc(financeQuery)}"><select id="finance-kind" aria-label="Filtrar tipo"><option value="">Todos os tipos</option>${Object.entries(financeKinds).map(([v,t]) => `<option value="${v}" ${financeKind===v?'selected':''}>${t}</option>`).join('')}</select><select id="finance-status" aria-label="Filtrar situação"><option value="">Todas as situações</option><option value="paid" ${financeStatus==='paid'?'selected':''}>Efetivados</option><option value="pending" ${financeStatus==='pending'?'selected':''}>Previstos</option></select><select id="finance-category" aria-label="Filtrar categoria"><option value="">Todas as categorias</option>${financeState.categories.map(c => `<option ${financeCategory===c?'selected':''}>${esc(c)}</option>`).join('')}</select>${financeQuery||financeKind||financeStatus||financeCategory ? '<button class="secondary" data-action="finance-clear">Limpar filtros</button>' : ''}</div>`;
}

function renderFinance() {
    const f = financeState, t = f.totals;
    const tabs = [['overview','Visão geral'],['transactions','Lançamentos'],['investments','Investimentos'],['budgets','Limites do mês']];
    let html = `<div class="finance-controls"><div class="finance-month"><button class="icon" data-action="finance-month" data-step="-1" aria-label="Mês financeiro anterior">‹</button><label>Mês de referência<input id="finance-month" type="month" min="1900-01" max="2100-12" value="${financeMonth}"></label><button class="icon" data-action="finance-month" data-step="1" aria-label="Próximo mês financeiro">›</button><button class="secondary" data-action="finance-current">Mês atual</button></div><div class="finance-tools"><button class="secondary" data-action="finance-import">⇩ Importar extrato</button><button class="secondary" data-action="finance-settings">Saldos iniciais</button><button class="secondary" data-action="finance-export">↗ Exportar CSV</button></div></div><div class="finance-tabs" role="group" aria-label="Seções das finanças">${tabs.map(([v,label]) => `<button data-action="finance-view" data-view="${v}" class="${financeView===v?'selected':''}" aria-pressed="${financeView===v}">${label}</button>`).join('')}</div>`;
    if (financeView === 'overview') {
        html += `<section class="finance-balance"><div><p class="eyebrow">SALDO DISPONÍVEL REGISTRADO</p><div class="balance-value ${f.cash_cents<0?'cash-out':''}">${money(f.cash_cents)}</div><p>Acumulado até o fim de ${esc(monthLabel(financeMonth))}</p></div><div class="balance-projection"><span>Após os previstos deste mês</span><strong class="${f.projected_cash_cents<0?'cash-out':''}">${money(f.projected_cash_cents)}</strong><small>A receber ${money(f.pending_in_cents)} · A pagar / aportar ${money(f.pending_out_cents)}</small>${f.daily_allowance_cents!=null?`<span class="daily-allowance ${f.daily_allowance_cents<0?'cash-out':''}">Para gastar por dia até o fim do mês: <b>${money(f.daily_allowance_cents)}</b> · ${f.days_left} dia(s)</span>`:''}</div></section><div class="stats finance-stats">${[
            ['ENTRADAS NO MÊS', t.income+t.yield, `Inclui ${money(t.yield)} de rendimentos`, 'cash-in'],
            ['SAÍDAS NO MÊS', t.expense, 'Despesas efetivadas, sem aportes', 'cash-out'],
            ['APORTES NO MÊS', t.investment, `Resgates: ${money(t.redemption)}`, 'investment-color'],
            ['FLUXO DO MÊS', f.net_month_cents, 'Variação do disponível após investimentos', f.net_month_cents<0?'cash-out':'cash-in']
        ].map(([label,value,note,cls])=>`<div class="stat"><div class="stat-label">${label}</div><div class="stat-number ${cls}">${money(value)}</div><div class="stat-note">${note}</div></div>`).join('')}</div>`;
        if (f.overdue_count) html += `<p class="finance-alert">${f.overdue_count} lançamento(s) previsto(s) com data vencida no histórico. Consulte os meses anteriores ou este mês e atualize a situação.</p>`;
        html += `<div class="finance-grid"><section class="panel finance-card"><h2>Entradas e saídas</h2><p class="hint">Últimos seis meses · valores efetivados</p>${financeTrend()}</section><section class="panel finance-card"><h2>Para onde foi seu dinheiro</h2><p class="hint">Despesas por categoria no mês</p>${financeExpenses()}</section></div><div class="section-title"><h2>Últimos lançamentos do mês</h2><button class="secondary" data-action="finance-view" data-view="transactions">Ver todos (${f.transactions.length})</button></div><div class="panel">${f.transactions.slice(0,5).map(financeRow).join('') || empty('Comece com o seu primeiro lançamento.', 'Informe seus saldos iniciais e registre uma entrada, saída ou investimento.')}</div><p class="hint">Os resumos usam todos os lançamentos efetivados do mês. Previstos só entram na projeção; limites e gráficos de despesas não incluem aportes.</p>`;
    } else if (financeView === 'transactions') {
        const rows = filteredFinanceRows();
        const net = rows.reduce((sum,r) => sum + (['expense','investment'].includes(r.kind)?-1:1)*r.amount_cents, 0);
        html += financeFilters()+`<div class="section-title"><h2>Lançamentos de ${esc(monthLabel(financeMonth))}</h2><span>${rows.length} REGISTRO(S) · FLUXO DA LISTA: ${money(net)}</span></div><p class="hint">O fluxo da lista inclui os previstos visíveis. Exportar CSV usa estes mesmos filtros.</p><div class="panel">${rows.map(financeRow).join('') || empty('Nenhum lançamento encontrado.', 'Adicione um lançamento ou ajuste o mês e os filtros.')}</div>`;
    } else if (financeView === 'investments') {
        const source = f.investment_source;
        html += `<section class="finance-plan-link"><p><strong>Quer ver seus investimentos ao longo do tempo?</strong>Registre o valor da carteira e simule cenários com aportes, taxas e eventos fictícios.</p><button class="secondary" data-action="plan-goto">${uiIcon('trend')}Planejar investimentos ↗</button></section>`;
        html += renderInvestmentSource(source);
        if (source.enabled) html += '<details class="local-investment-details"><summary>Movimentos de investimentos no saldo local</summary><p class="hint">Registre aqui os aportes que saíram da sua conta, os resgates e os rendimentos recebidos. O saldo local só considera estes lançamentos. Os ativos e as cotações ficam no Investidor10.</p>';
        html += `<div class="stats finance-stats investment-stats">${[
            ['CAPITAL REGISTRADO', f.invested_cents, 'Saldo inicial + aportes − resgates até este mês'],
            ['APORTES DO MÊS', t.investment, 'Valor retirado do saldo disponível'],
            ['RENDIMENTOS DO MÊS', t.yield, 'Recebidos no saldo disponível']
        ].map(([label,value,note])=>`<div class="stat"><div class="stat-label">${label}</div><div class="stat-number investment-color">${money(value)}</div><div class="stat-note">${note}</div></div>`).join('')}</div><p class="hint">Controle manual de movimentos, sem cotações. No resgate, registre o principal devolvido; ganhos recebidos entram em Rendimento. Rendimentos reinvestidos pedem um rendimento e um novo aporte. O capital registrado não representa o valor de mercado.</p>`;
        if (f.invested_cents < 0 || f.assets.some(a=>a.net_cents<0)) html += '<p class="finance-alert">Há resgates acima dos aportes registrados. Confira o histórico e os saldos iniciais.</p>';
        html += `<div class="section-title"><h2>Por investimento</h2><button class="secondary" data-action="finance-add-investment">+ Registrar aporte</button></div><div class="project-grid">${f.settings.opening_invested_cents ? `<article class="project"><h2>Capital anterior ao controle</h2><p>Saldo inicial total, sem distribuição por ativo.</p><strong class="investment-color">${money(f.settings.opening_invested_cents)}</strong></article>` : ''}${f.assets.map(a=>`<article class="project"><h2>${esc(a.asset)}</h2><p>Aportes líquidos acumulados</p><strong class="investment-color asset-value">${money(a.net_cents)}</strong><p class="hint">Rendimentos recebidos: ${money(a.yield_cents)}</p></article>`).join('')}</div>${f.assets.length||f.settings.opening_invested_cents?'':empty('Seu futuro começa com o primeiro aporte.', 'Identifique o ativo no lançamento: CDB, Tesouro, ações, fundos ou outro.')}<div class="section-title"><h2>Movimentos de investimentos no mês</h2></div><div class="panel">${f.transactions.filter(r=>['investment','redemption','yield'].includes(r.kind)).map(financeRow).join('') || empty('Sem movimentos neste mês.', 'Aportes, resgates e rendimentos aparecerão aqui.')}</div>`;
        if (source.enabled) html += '</details>';
    } else {
        html += `<div class="section-title"><h2>Limites de ${esc(monthLabel(financeMonth))}</h2><div class="finance-tools"><button class="secondary" data-action="finance-copy-budgets">Copiar do mês anterior</button><button class="secondary" data-action="finance-add-budget">+ Definir limite</button></div></div><p class="hint">Defina quanto pretende gastar em cada categoria. Cada limite vale somente para o mês selecionado. Os previstos aparecem separados.</p><div class="project-grid">${f.budgets.map(b=>{
            const percent = Math.round(b.spent_cents / b.amount_cents * 100), over = b.spent_cents>b.amount_cents;
            return `<article class="project budget-card"><div class="project-head"><h2>${esc(b.category)}</h2><div>${actions('finance_budgets',b.id)}</div></div><div class="progress-label"><span>${money(b.spent_cents)} de ${money(b.amount_cents)}</span><span class="${over?'cash-out':''}">${percent}%</span></div><div class="track ${over?'over-budget':''}"><span style="width:${Math.min(100,percent)}%"></span></div><p class="${over?'cash-out':'hint'}">${over?'Acima do limite: '+money(b.spent_cents-b.amount_cents):'Restante: '+money(b.amount_cents-b.spent_cents)}</p><p class="hint">Previstos: ${money(b.pending_cents)}${b.spent_cents+b.pending_cents>b.amount_cents?' · Projeção acima do limite':''}</p></article>`;
        }).join('')}</div>${f.budgets.length?'':empty('Dê um destino ao seu dinheiro.', 'Defina um limite para alimentação, lazer ou qualquer categoria que você usa.')}`;
    }
    return html;
}

function renderInvestmentSource(source) {
    if (!source.enabled) return `<section class="panel investment-source-off"><div><h2>Investimentos no controle local</h2><p class="hint">${source.configured?'O Investidor10 está desativado. Seus lançamentos locais continuam abaixo.':'Usa o Investidor10? Ative o compartilhamento público da sua carteira lá e cole o link aqui (formato https://investidor10.com.br/wallet/public/NÚMERO). Nenhuma senha é pedida.'}</p></div><button class="secondary" data-action="finance-wallet-settings">${source.configured?'Configurar carteira':'Vincular minha carteira'}</button></section>`;
    const shortcuts = [['positions','Posições','folder','Acompanhe seus ativos'],['earnings','Proventos','dollar','Consulte dividendos e rendimentos'],['patrimony','Patrimônio','target','Veja a evolução da carteira'],['return','Rentabilidade','repeat','Consulte o desempenho'],['entries','Lançamentos','list','Veja as operações registradas']];
    return `<section class="panel investment-source-card" aria-label="Carteira do Investidor10"><div class="investment-source-head"><div class="investment-provider"><span class="investment-provider-mark" aria-hidden="true">i10</span><div><p class="eyebrow">INVESTIDOR10</p><h2>${esc(source.label)}</h2></div></div><span class="badge finance-paid">Carteira vinculada</span></div><p class="investment-source-description">Sua carteira na página oficial do Investidor10, com os valores e gráficos exibidos pela plataforma.</p><div class="investment-open-actions"><button class="primary" data-action="finance-wallet-open" data-section="summary">${uiIcon('folder')} Abrir carteira no aplicativo</button><button class="secondary" data-action="finance-wallet-open" data-section="summary" data-external="true">Abrir no navegador ↗</button><button class="secondary" data-action="finance-wallet-settings">${uiIcon('settings')} Configurar carteira</button></div><div class="investment-shortcuts">${shortcuts.map(([section,label,icon,description])=>`<button class="investment-shortcut" data-action="finance-wallet-open" data-section="${section}"><span class="stat-icon">${uiIcon(icon)}</span><span><strong>${label}</strong><small>${description}</small></span>${uiIcon('chevron')}</button>`).join('')}</div><div class="investment-source-foot"><span class="investment-wallet-url">${esc(source.wallet_url)}</span><p class="hint">Abre em uma janela do aplicativo. Precisa de internet. Para editar a carteira, abra no navegador e entre na sua conta do Investidor10.</p><p class="hint">Entradas e saídas continuam no Holy Planner. O patrimônio e os proventos do Investidor10 não são importados nem somados automaticamente ao saldo local. A carteira mostra os dados atuais; o mês acima vale para seus lançamentos locais.</p></div></section>`;
}

function financeTrend() {
    const maximum = Math.max(1,...financeState.trend.flatMap(r=>[r.income_cents,r.expense_cents]));
    return '<div class="finance-chart">'+financeState.trend.map(r=>`<div class="chart-month"><span>${r.month.slice(5)}/${r.month.slice(2,4)}</span><div><div class="chart-line"><i class="income-bar" style="width:${r.income_cents/maximum*100}%"></i><small>Entradas ${money(r.income_cents)}</small></div><div class="chart-line"><i class="expense-bar" style="width:${r.expense_cents/maximum*100}%"></i><small>Saídas ${money(r.expense_cents)}</small></div></div></div>`).join('')+'</div>';
}

function financeExpenses() {
    const total = financeState.totals.expense;
    return financeState.expenses.map(c=>`<div class="expense-category"><div><span>${esc(c.category)}</span><strong>${money(c.total)}</strong></div><div class="track"><span style="width:${total?c.total/total*100:0}%"></span></div></div>`).join('') || empty('Nenhuma despesa efetivada.', 'As categorias aparecem conforme você registra suas saídas.');
}

function bindFinanceEvents() {
    $('#finance-month').onchange = async e => {
        if (!e.target.value) return;
        const previous = financeMonth;
        financeMonth = e.target.value;
        try { await refresh(); } catch (err) { financeMonth = previous; render(); toast(err.message); }
    };
    $('#finance-search')?.addEventListener('input', e=>{
        const position = e.target.selectionStart;
        financeQuery = e.target.value;
        render();
        $('#finance-search').focus();
        $('#finance-search').setSelectionRange(position,position);
    });
    for (const [id,setter] of [['kind',v=>financeKind=v],['status',v=>financeStatus=v],['category',v=>financeCategory=v]]) {
        $('#finance-'+id)?.addEventListener('change', e=>{setter(e.target.value);render();});
    }
}

async function handleFinanceAction(b) {
    const action = b.dataset.action;
    const previousMonth = financeMonth;
    try {
        if (action === 'finance-view') { financeView=b.dataset.view; render(); return; }
        if (action === 'finance-clear') { financeQuery=financeKind=financeStatus=financeCategory=''; render(); return; }
        if (action === 'finance-settings') { financeEditor('finance_settings'); return; }
        if (action === 'finance-wallet-settings') { financeEditor('finance_investment_source'); return; }
        if (action === 'finance-add-budget') { financeEditor('finance_budgets'); return; }
        if (action === 'finance-import') { openFinanceImport(); return; }
        if (action === 'finance-add-investment') { financeEditor('finance_transactions',null,'investment'); return; }
        b.disabled = true;
        if (action === 'finance-wallet-open') {
            if (window.holyWeb) {
                const config = financeState.investment_source;
                const suffix = {summary:'',positions:'/positions',earnings:'/earnings',patrimony:'/patrimony',return:'/return',entries:'/entries'}[b.dataset.section] ?? '';
                if (!config.enabled) throw new Error('Ative a carteira nas configurações.');
                // O endereço foi validado no backend; abre no próprio dispositivo.
                const link = document.createElement('a');
                link.href = config.wallet_url + suffix; link.target = '_blank'; link.rel = 'noopener noreferrer';
                link.click();
                toast('Carteira aberta no navegador.');
                return;
            }
            const result = await call('open_investidor10', b.dataset.section, b.dataset.external === 'true');
            toast(result.mode === 'browser' ? 'Carteira aberta no navegador.' : 'Carteira aberta na janela do Investidor10.');
        } else if (action === 'finance-export') {
            const r = await call('export_finances',financeMonth,financeView==='transactions'?{query:financeQuery,kind:financeKind,status:financeStatus,category:financeCategory}:{});
            toast(window.holyWeb ? `${r.count} lançamento(s) baixados neste dispositivo.` : `${r.count} lançamento(s) exportado(s). Arquivo: ${r.path}`);
        } else if (action === 'finance-copy-budgets') {
            const r = await call('copy_budgets', financeMonth);
            await afterMutation({}, false, r.count ? `${r.count} limite(s) copiado(s) de ${monthLabel(r.from)}.` : `Nenhum limite novo para copiar de ${monthLabel(r.from)}.`);
        } else if (action === 'finance-toggle') {
            await afterMutation(await call('toggle_transaction',Number(b.dataset.id)),false,'Situação atualizada.');
        } else {
            if (action === 'finance-current') financeMonth=state.today.slice(0,7);
            else {
                const [y,m]=financeMonth.split('-').map(Number), d=new Date(y,m-1+Number(b.dataset.step),1,12);
                if(d.getFullYear()<1900||d.getFullYear()>2100) return;
                financeMonth=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
            }
            await refresh();
        }
    } catch(err) { financeMonth=previousMonth; render(); toast(err.message); }
    finally { b.disabled=false; }
}

function financeEditor(table, id=null, preset='income') {
    const f = financeState;
    const r = id ? (table==='finance_budgets'?f.budgets:f.transactions).find(r=>r.id===id) : {};
    if(!r) return;
    editing={table,id};
    let html='';
    if(table==='finance_investment_source') {
        const source = f.investment_source;
        $('#editor-title').textContent='Carteira de investimentos';
        html=select('Como acompanhar os investimentos','enabled',[['1','Usar Investidor10'],['0','Usar controle local']],source.enabled||!source.configured?'1':'0')+`<label>Nome da carteira<input name="label" maxlength="80" value="${esc(source.label)}" placeholder="Minha carteira"></label><label>Link público do Investidor10<input name="wallet_url" type="url" maxlength="512" value="${esc(source.wallet_url)}" placeholder="https://investidor10.com.br/wallet/public/123456"></label><p class="hint">No Investidor10, deixe a carteira pública e copie o link dela (ou só o número). Nenhuma senha é solicitada pelo Holy Planner. Mudar esta opção mantém todos os seus lançamentos locais.</p>`;
    } else if(table==='finance_settings') {
        $('#editor-title').textContent='Saldos iniciais';
        html='<p class="hint">Informe o que você já tinha antes do primeiro lançamento registrado. Estes saldos valem para todo o histórico. Evite contar novamente valores que já estão nos lançamentos.</p>'+moneyField('Saldo disponível inicial (R$)','opening_cash',f.settings.opening_cash_cents)+moneyField('Capital investido inicial (R$)','opening_invested',f.settings.opening_invested_cents);
    } else if(table==='finance_budgets') {
        $('#editor-title').textContent=id?'Editar limite':'Definir limite';
        html=`<label>Mês<input name="month" type="month" required min="1900-01" max="2100-12" value="${r.month||financeMonth}"></label><label>Categoria *<input name="category" list="finance-categories" required maxlength="80" value="${esc(r.category||'Alimentação')}"></label>`+moneyField('Limite de gastos (R$) *','amount',r.amount_cents||0)+'<p class="hint">Salvar a mesma categoria e mês atualiza o limite já existente.</p>';
    } else {
        $('#editor-title').textContent=id?'Editar lançamento':'Novo lançamento';
        const kind=r.kind||preset, selectedDate=r.day||(financeMonth===state.today.slice(0,7)?state.today:financeMonth+'-01');
        html=input('Descrição *','title',r.title)+`<div class="form-grid">${select('Tipo *','kind',Object.entries(financeKinds),kind)}${moneyField('Valor (R$) *','amount',r.amount_cents||0)}</div><div class="form-grid">${input('Data *','day',selectedDate,'date')}${select('Situação','status',[['paid','Efetivado'],['pending','Previsto']],r.status||(selectedDate>state.today?'pending':'paid'))}</div>${id&&r.series?`<label>Aplicar a alteração a<select name="scope"><option value="one">Só este lançamento</option><option value="future">Este e os próximos da série</option></select></label><p class="hint">Nos próximos, valor, descrição, tipo, categoria, conta e notas são atualizados; datas e situações continuam as mesmas.</p>`:''}${id?'':`<label>Repetir todo mês<select name="repeat_months"><option value="1">Não repetir</option>${[2,3,6,10,12,18,24,36,48,60].map(n=>`<option value="${n}">Por ${n} meses</option>`).join('')}</select></label><p class="hint" id="finance-repeat-help" hidden>Cria um lançamento por mês, no mesmo dia. Datas futuras ficam como Previsto, para aparecer nas projeções de cada mês.</p>`}<label>Categoria *<input name="category" list="finance-categories" required maxlength="80" value="${esc(r.category||(['investment','redemption','yield'].includes(kind)?'Investimentos':'Outros'))}"></label><label>Conta / instituição (opcional)<input name="account" maxlength="80" placeholder="Ex.: conta corrente, carteira, corretora" value="${esc(r.account)}"></label><label id="asset-field">Investimento *<input name="asset" list="finance-assets" maxlength="120" placeholder="Ex.: CDB Banco, Tesouro Selic, fundo…" value="${esc(r.asset)}"></label><p id="finance-kind-help" class="hint"></p><label>Notas<textarea name="notes" maxlength="10000">${esc(r.notes)}</textarea></label>`;
    }
    html+=`<datalist id="finance-categories">${f.categories.map(c=>`<option value="${esc(c)}"></option>`).join('')}</datalist><datalist id="finance-assets">${f.assets.map(a=>`<option value="${esc(a.asset)}"></option>`).join('')}</datalist>`;
    $('#fields').innerHTML=html;
    if(table==='finance_investment_source') {
        const mode=$('#fields [name="enabled"]'),url=$('#fields [name="wallet_url"]');
        const sync=()=>{url.required=mode.value==='1';};
        mode.onchange=sync;sync();
    }
    if(table==='finance_transactions') {
        const kindSelect=$('#fields [name="kind"]'), asset=$('#fields [name="asset"]');
        const update=()=>{
            const needsAsset=['investment','redemption','yield'].includes(kindSelect.value);
            $('#asset-field').hidden=!needsAsset; asset.required=needsAsset;
            $('#finance-kind-help').textContent={income:'Entrada aumenta o saldo disponível.',expense:'Saída reduz o saldo disponível e entra nos limites da categoria.',investment:'Aporte transfere dinheiro do disponível para o capital investido.',redemption:'Registre o principal resgatado. Ganhos recebidos entram separadamente como Rendimento.',yield:'Rendimento recebido aumenta o disponível. Para reinvestir, registre também um aporte.'}[kindSelect.value];
        };
        kindSelect.onchange=update; update();
        const repeat=$('#fields [name="repeat_months"]');
        if(repeat) repeat.onchange=()=>{$('#finance-repeat-help').hidden=repeat.value==='1';};
        const day=$('#fields [name="day"]'); day.required=true; day.min='1900-01-01'; day.max='2100-12-31';
        day.onchange=()=>{if(day.value>state.today) $('#fields [name="status"]').value='pending';};
    }
    $('#form-error').textContent='';
    $('#editor').showModal();
    $('#fields input').focus();
}

/* ---------- Importar extrato (OFX/CSV) ---------- */
let financeImportRows = [];
function openFinanceImport() {
    if (!$('#import-dialog')) {
        document.body.insertAdjacentHTML('beforeend', `<dialog id="import-dialog" aria-labelledby="import-title"><div class="modal-head"><div><p class="eyebrow">MENOS DIGITAÇÃO</p><h2 id="import-title">Importar extrato</h2></div><button class="icon" data-iclose aria-label="Fechar">×</button></div><p class="hint">Baixe o extrato do banco ou a fatura do cartão em <strong>OFX</strong> ou <strong>CSV</strong> e escolha o arquivo. Nada é enviado para fora do seu computador.</p><div class="import-controls"><label>Arquivo<input type="file" id="import-file" accept=".ofx,.qfx,.csv,.txt"></label><label>Conta / cartão<input id="import-account" maxlength="80" placeholder="Ex.: Nubank, Itaú"></label><label class="plan-check"><input type="checkbox" id="import-invert">É fatura de cartão (valores positivos são gastos)</label></div><div id="import-preview"></div><p class="error" id="import-error" role="alert"></p><div class="modal-actions"><button class="secondary" data-iclose>Cancelar</button><button class="primary" id="import-save" disabled>Importar selecionados</button></div></dialog>`);
        const dialog = $('#import-dialog');
        dialog.addEventListener('click', e => { if (e.target.closest('[data-iclose]')) dialog.close(); if (e.target.id === 'import-all') { const on = e.target.dataset.on !== '1'; financeImportRows.forEach(r => { r.include = on; }); drawFinanceImport(); } });
        $('#import-file').onchange = readFinanceImport;
        $('#import-invert').onchange = readFinanceImport;
        dialog.addEventListener('change', e => {
            const row = financeImportRows[Number(e.target.closest('[data-irow]')?.dataset.irow)];
            if (!row) return;
            if (e.target.matches('[data-ifield="include"]')) row.include = e.target.checked;
            else if (e.target.matches('[data-ifield]')) row[e.target.dataset.ifield] = e.target.value;
            updateFinanceImportButton();
        });
        $('#import-save').onclick = async () => {
            const chosen = financeImportRows.filter(r => r.include);
            $('#import-save').disabled = true;
            try {
                const result = await call('import_commit', chosen.map(({include, duplicate, future, ...r}) => r), $('#import-account').value);
                dialog.close();
                await afterMutation({}, false, `${result.count} lançamento(s) importado(s)${result.skipped ? `; ${result.skipped} já existiam` : ''}.`);
            } catch (err) { $('#import-error').textContent = err.message; updateFinanceImportButton(); }
        };
    }
    financeImportRows = [];
    $('#import-file').value = '';
    $('#import-error').textContent = '';
    $('#import-preview').innerHTML = '';
    updateFinanceImportButton();
    $('#import-dialog').showModal();
}
async function readFinanceImport() {
    const file = $('#import-file').files[0];
    if (!file) return;
    $('#import-error').textContent = '';
    $('#import-preview').innerHTML = '<p class="hint">Lendo o arquivo…</p>';
    try {
        if (file.size > 1500000) throw new Error('Arquivo muito grande. Exporte um período menor.');
        const bytes = await file.arrayBuffer();
        let text;
        try { text = new TextDecoder('utf-8', {fatal: true}).decode(bytes); } catch { text = new TextDecoder('windows-1252').decode(bytes); }
        const result = await call('import_preview', text, file.name, $('#import-invert').checked);
        financeImportRows = result.rows.map(r => ({...r, include: !r.duplicate}));
        drawFinanceImport();
    } catch (err) { financeImportRows = []; $('#import-preview').innerHTML = ''; $('#import-error').textContent = err.message; updateFinanceImportButton(); }
}
function drawFinanceImport() {
    const rows = financeImportRows, duplicates = rows.filter(r => r.duplicate).length, all = rows.every(r => r.include);
    $('#import-preview').innerHTML = `<div class="import-summary"><span>${rows.length} lançamento(s) encontrados${duplicates ? ` · <b>${duplicates} parecem já registrados</b> (desmarcados)` : ''}</span><button type="button" class="text-button" id="import-all" data-on="${all ? '1' : '0'}">${all ? 'Desmarcar todos' : 'Marcar todos'}</button></div><div class="import-table"><table><thead><tr><th></th><th>Data</th><th>Descrição</th><th>Tipo</th><th>Categoria</th><th>Valor</th></tr></thead><tbody>${rows.map((r, i) => `<tr data-irow="${i}" class="${r.duplicate ? 'import-duplicate' : ''}"><td><input type="checkbox" data-ifield="include" ${r.include ? 'checked' : ''} aria-label="Importar ${esc(r.title)}"></td><td>${fmt(r.day)}${r.future ? '<small>futuro → previsto</small>' : ''}</td><td>${esc(r.title)}${r.duplicate ? '<small>possível duplicado</small>' : ''}</td><td><select data-ifield="kind"><option value="expense" ${r.kind === 'expense' ? 'selected' : ''}>Saída</option><option value="income" ${r.kind === 'income' ? 'selected' : ''}>Entrada</option></select></td><td><input data-ifield="category" list="import-categories" maxlength="80" value="${esc(r.category)}"></td><td class="${r.kind === 'expense' ? 'cash-out' : 'cash-in'}">${money(r.amount_cents)}</td></tr>`).join('')}</tbody></table></div><datalist id="import-categories">${(financeState?.categories || []).map(c => `<option value="${esc(c)}"></option>`).join('')}</datalist><p class="hint">Categorias sugeridas pelo que você já registrou e por palavras como mercado, uber, farmácia. Importar o mesmo arquivo de novo não duplica os lançamentos.</p>`;
    updateFinanceImportButton();
}
function updateFinanceImportButton() {
    const count = financeImportRows.filter(r => r.include).length;
    $('#import-save').disabled = !count;
    $('#import-save').textContent = count ? `Importar ${count} lançamento(s)` : 'Importar selecionados';
}
