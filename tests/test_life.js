// Captura rápida: interpretação de frases em português.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const context = vm.createContext({document: {addEventListener() {}, querySelector() { return null; }}, window: {}, crypto: globalThis.crypto});
vm.runInContext(fs.readFileSync('frontend/life.js', 'utf8'), context);
const parse = (text, today = '2026-11-11') => JSON.parse(JSON.stringify(vm.runInContext(`quickParse(${JSON.stringify(text)}, ${JSON.stringify(today)})`, context)));

let r = parse('pagar luz 180 dia 15');
assert.deepEqual([r.type, r.title, r.amount, r.day, r.kind, r.status], ['finance', 'Pagar luz', '180', '2026-11-15', 'expense', 'pending']);
r = parse('pagar aluguel 1.500,00 dia 5');
assert.deepEqual([r.amount, r.day], ['1.500,00', '2026-12-05']); // dia já passou: próximo mês
r = parse('gastei 45,90 no mercado');
assert.deepEqual([r.type, r.amount, r.status, r.day, r.title], ['finance', '45,90', 'paid', '2026-11-11', 'Gastei no mercado']);
r = parse('recebi salário 5000');
assert.deepEqual([r.kind, r.status], ['income', 'paid']);
r = parse('aporte 1000 no tesouro');
assert.equal(r.kind, 'investment');
r = parse('ligar para o dentista amanhã às 9h');
assert.deepEqual([r.type, r.title, r.day, r.time], ['task', 'Ligar para o dentista', '2026-11-12', '09:00']);
r = parse('reunião com a equipe sexta 14:30 urgente');
assert.deepEqual([r.type, r.day, r.time, r.priority, r.title], ['task', '2026-11-13', '14:30', 'Alta', 'Reunião com a equipe']);
r = parse('entregar relatório 20/12');
assert.deepEqual([r.day, r.title], ['2026-12-20', 'Entregar relatório']);
r = parse('comprar presente');
assert.deepEqual([r.type, r.day], ['task', '']);
r = parse('supino 4x10 60kg, agachamento 3x12 80kg, flexão 3x15');
assert.equal(r.type, 'workout');
assert.deepEqual(r.exercises, [{name: 'Supino', sets: 4, reps: 10, weight: 60}, {name: 'Agachamento', sets: 3, reps: 12, weight: 80}, {name: 'Flexão', sets: 3, reps: 15, weight: 0}]);
r = parse('corrida 30min 5,2km');
assert.deepEqual(r.cardio, [{name: 'Corrida', minutes: 30, distance_km: 5.2}]);
r = parse('Nota: ideia para o fim de semana');
assert.deepEqual([r.type, r.title, r.body], ['note', 'ideia para o fim de semana', 'ideia para o fim de semana']);
r = parse('boleto da escola R$ 890 amanhã');
assert.deepEqual([r.type, r.amount, r.day, r.status], ['finance', '890', '2026-11-12', 'pending']);
assert.equal(parse('').type, '');
console.log('test_life.js: ok');
