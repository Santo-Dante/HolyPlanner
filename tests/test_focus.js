// Regressões de tempo decorrido, pausa e reenvio após falha de conexão.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const nodes = new Map();
const node = () => ({textContent:'',hidden:false,style:{setProperty(){}},classList:{},dataset:{}});
let now = Date.now(), writes = 0, fail = false;
const context = vm.createContext({
    Date: class extends Date { constructor(...args) { super(...(args.length?args:[now])); } static now(){return now;} },
    localStorage:{getItem(){return null;},setItem(){}},
    document:{documentElement:{dataset:{}},addEventListener(){},title:''},
    window:{addEventListener(){}},location:{protocol:'file:'},
    $: selector => {if(!nodes.has(selector))nodes.set(selector,node());return nodes.get(selector);},
    page:'today', state:{}, toast(){}, refresh:async()=>{}, render(){},
    call:async()=>{writes++;if(fail)throw new Error('offline');return {ok:true};},
});
vm.runInContext(fs.readFileSync('frontend/productivity.js','utf8'),context);
const run = code => vm.runInContext(code,context);
(async()=>{
    run("focusTimer={...freshTimer(),id:'test-session',remaining:60,minutes:1,end:Date.now()+60000};updateTimerDisplay()");
    assert.equal(nodes.get('#mini-timer-text').textContent,'01:00');
    now+=43000;run('updateTimerDisplay()');
    assert.equal(nodes.get('#mini-timer-text').textContent,'00:17');
    run('focusTimer.end=null;focusTimer.remaining=17;updateTimerDisplay()');
    now+=100000;run('updateTimerDisplay()');
    assert.equal(nodes.get('#mini-timer-text').textContent,'00:17 · pausado');
    fail=true;
    run("focusTimer={...freshTimer(),id:'test-completed',minutes:1,end:Date.now()-1000};updateTimerDisplay()");
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(run('focusTimer.pending.id'),'test-completed');
    assert.equal(writes,1);
    fail=false;await run('flushFocus()');
    assert.equal(run('focusTimer.pending'),null);
    assert.equal(writes,2);
    await run('flushFocus()');assert.equal(writes,2);
    run("focusTimer={...freshTimer(),mode:'short',id:'break-test',end:Date.now()-1};updateTimerDisplay()");
    assert.equal(writes,2);
    assert.equal(run('focusTimer.id'),null);
    console.log('Timer: elapsed time, pause, offline retry, deduplication and breaks OK.');
})().catch(error=>{console.error(error);process.exitCode=1;});
