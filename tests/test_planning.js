// Regressões da projeção dos cenários fictícios.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const context = vm.createContext({window: {innerWidth: 1200, addEventListener() {}}, document: {querySelector() { return null; }}});
vm.runInContext(fs.readFileSync('frontend/planning.js', 'utf8'), context);
const run = code => vm.runInContext(code, context);
const near = (a, b, tolerance = 1) => assert.ok(Math.abs(a - b) <= tolerance, `${a} ≠ ${b}`);
const base = {monthly_cents: 0, annual_rate_bp: 0, inflation_bp: 0, raise_bp: 0, years: 1, target_cents: 0, events: []};
context.sc = base;

// Sem rendimento: soma simples dos aportes.
let r = run(`planProject({...sc, monthly_cents: 10000}, 50000, '2026-11')`);
assert.equal(r.final, 50000 + 12 * 10000);
assert.equal(r.points.length, 13);
assert.equal(r.endMonth, '2027-11');

// 12% ao ano sem aportes equivale a 12% em 12 meses.
r = run(`planProject({...sc, annual_rate_bp: 1200, years: 2}, 100000, '2026-11')`);
near(r.points[12].nominal, 112000);
near(r.final, 125440);
near(r.interest, 25440);

// Inflação de 4% reduz o valor de hoje na mesma proporção.
r = run(`planProject({...sc, inflation_bp: 400}, 104000, '2026-11')`);
near(r.finalReal, 100000);

// Reajuste anual do aporte começa no 13º mês.
r = run(`planProject({...sc, monthly_cents: 1000, raise_bp: 1000, years: 2}, 0, '2026-11')`);
near(r.deposits, 12 * 1000 + 12 * 1100);

// Eventos: único, anual, passado e retirada maior que o saldo.
r = run(`planProject({...sc, years: 3, events: [
  {month: '2027-01', kind: 'deposit', amount_cents: 5000, yearly: false},
  {month: '2026-12', kind: 'deposit', amount_cents: 1000, yearly: true},
  {month: '2026-05', kind: 'deposit', amount_cents: 9999, yearly: false}]}, 0, '2026-11')`);
assert.equal(r.final, 5000 + 3 * 1000);
assert.equal(r.ignored, 1);
r = run(`planProject({...sc, events: [{month: '2027-03', kind: 'withdrawal', amount_cents: 80000, yearly: false}]}, 50000, '2026-11')`);
assert.equal(r.final, 0);
assert.equal(r.withdrawals, 50000);
assert.equal(r.shortfall, '2027-03');

// Meta atingida no mês certo.
r = run(`planProject({...sc, monthly_cents: 10000, target_cents: 30000}, 0, '2026-11')`);
assert.equal(r.reached, '2027-02');

// Conversões dos campos digitados.
assert.equal(run(`planParseMoney('1.234,56')`), 123456);
assert.equal(run(`planParseMoney('1234.5')`), 123450);
assert.ok(Number.isNaN(run(`planParseMoney('12,345')`)));
assert.equal(run(`planParsePercent('10,5')`), 1050);
assert.ok(Number.isNaN(run(`planParsePercent('1,234')`)));
assert.equal(run(`planAddMonths('2026-11', 14)`), '2028-01');
assert.equal(run(`planMonthShort('2028-01')`), 'jan/28');
// Calculadora de meta: aporte necessário e tempo até o valor.
let need = run(`planRequiredMonthly(sc, 0, '2026-11', 1200000, 12)`);
assert.ok(need >= 100000 && need <= 100001, String(need));
need = run(`planRequiredMonthly({...sc, annual_rate_bp: 1200}, 0, '2026-11', 10000000, 120)`);
r = run(`planProject({...sc, annual_rate_bp: 1200, months: 120, monthly_cents: ${need}}, 0, '2026-11')`);
assert.ok(r.final >= 10000000 && r.final < 10000000 + 200, String(r.final));
assert.equal(run(`planRequiredMonthly({...sc, annual_rate_bp: 1000}, 2000000, '2026-11', 2100000, 12)`), 0);
// Meta em dinheiro de hoje exige mais que a nominal.
assert.ok(run(`planRequiredMonthly({...sc, inflation_bp: 500}, 0, '2026-11', 1200000, 12, true)`) > 100000);
assert.equal(run(`planTimeToTarget({...sc, monthly_cents: 10000}, 0, '2026-11', 35000)`), 4);
assert.equal(run(`planTimeToTarget({...sc, monthly_cents: 0}, 0, '2026-11', 1)`), null);
assert.equal(run(`planTimeToTarget(sc, 5000, '2026-11', 5000)`), 0);

// Rentabilidade da carteira: 100 → 110 em 12 meses sem aportes ≈ 10% a.a.
let earned = run(`planPortfolioReturn([{day:'2025-10-28',amount_cents:10000},{day:'2026-10-28',amount_cents:11000}], () => 0)`);
assert.equal(earned.annual_bp, 1000);
// Aportes não contam como rendimento.
earned = run(`planPortfolioReturn([{day:'2025-10-28',amount_cents:10000},{day:'2026-10-28',amount_cents:20000}], m => m < '2026-01' ? 0 : 10000)`);
assert.ok(earned.annual_bp === 0, String(earned.annual_bp));
assert.equal(run(`planPortfolioReturn([{day:'2026-10-01',amount_cents:10000},{day:'2026-10-28',amount_cents:11000}], () => 0)`), null);
console.log('test_planning.js: ok');
