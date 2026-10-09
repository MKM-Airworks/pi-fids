const assert=require('node:assert/strict');
const {active}=require('../pifids/static/signage-policy.js');
const cfg={start:'10:00',end:'12:00'};
function at(t,c=cfg){return active(c,Date.parse('2026-10-09T'+t+':00+09:00'),'Asia/Tokyo');}
assert.equal(at('09:59'),false);assert.equal(at('10:00'),true);assert.equal(at('11:59'),true);assert.equal(at('12:00'),false);
assert.equal(at('10:00',{...cfg,date:'2026-10-08'}),false);
assert.equal(at('10:00',{...cfg,date:'2026-10-09'}),true);
const night={start:'23:00',end:'01:00',date:'2026-10-08'};
assert.equal(at('00:00',night),true);assert.equal(at('01:00',night),false);assert.equal(at('23:00',night),false);
assert.equal(at('23:00',{...night,date:''}),true);
assert.equal(active(cfg,Date.parse('2026-10-09T10:00:00+09:00'),'Pacific/Palau'),true);
assert.equal(active({},Date.now(),'Asia/Tokyo'),true);
console.log('Signage boundaries, dates, overnight and timezone checks passed');
