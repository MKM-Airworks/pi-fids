const test=require('node:test');const assert=require('node:assert/strict');
const p=require('../pifids/static/board-policy.js');
const t=(value)=>Date.parse(value+'+09:00');
const flight=(patch={})=>({serviceDate:'2026-10-05',direction:'departure',time:'10:00',flightNumber:'BC101',...patch});
test('ETD replaces STD for sorting, actual time does not change ordering or input',()=>{
 const rows=[flight({flightNumber:'A',time:'09:00',estimatedTime:'11:00',actualTime:'11:20'}),flight({flightNumber:'B',time:'10:00'}),flight({flightNumber:'C',time:'12:00',estimatedTime:'09:30'})];
 assert.deepEqual(p.visible(rows,'departure',{},t('2026-10-05T08:00:00')).map(x=>x.flightNumber),['C','B','A']);
 assert.deepEqual(rows.map(x=>x.flightNumber),['A','B','C']);
});
test('departure disappears exactly 10 minutes after estimated or actual time',()=>{
 const row=flight({estimatedTime:'10:30'});
 assert.equal(p.visible([row],'departure',{},t('2026-10-05T10:39:59')).length,1);
 assert.equal(p.visible([row],'departure',{},t('2026-10-05T10:40:00')).length,0);
 row.actualTime='10:35';assert.equal(p.visible([row],'departure',{},t('2026-10-05T10:44:59')).length,1);
 assert.equal(p.visible([row],'departure',{},t('2026-10-05T10:45:00')).length,0);
 row.actualTime='10:05';assert.equal(p.visible([row],'departure',{},t('2026-10-05T10:15:00')).length,0);
});
test('arrival uses ETA for sort and ATA for the 120 minute deadline',()=>{
 const rows=[flight({direction:'arrival',flightNumber:'A',estimatedTime:'11:00',actualTime:'11:15'}),flight({direction:'arrival',flightNumber:'B',time:'10:30'})];
 assert.deepEqual(p.visible(rows,'arrival',{},t('2026-10-05T10:00:00')).map(x=>x.flightNumber),['B','A']);
 assert.equal(p.visible([rows[0]],'arrival',{},t('2026-10-05T13:14:59')).length,1);
 assert.equal(p.visible([rows[0]],'arrival',{},t('2026-10-05T13:15:00')).length,0);
});
test('configured retention works including zero and separate directions',()=>{
 const row=flight();const control={departureHideMinutes:30,arrivalHideMinutes:60};
 assert.equal(p.visible([row],'departure',control,t('2026-10-05T10:29:59')).length,1);
 assert.equal(p.visible([row],'departure',control,t('2026-10-05T10:30:00')).length,0);
 assert.equal(p.visible([row],'departure',{departureHideMinutes:0},t('2026-10-05T10:00:00')).length,0);
 assert.equal(p.visible([flight({direction:'arrival'})],'arrival',control,t('2026-10-05T11:00:00')).length,0);
});
test('midnight, future services and offline stale data retain their actual date',()=>{
 const row=flight({time:'23:55',estimatedTime:'00:15',estimatedDate:'2026-10-06',actualTime:'00:20',actualDate:'2026-10-06'});
 assert.equal(p.visible([row],'departure',{},t('2026-10-06T00:29:59')).length,1);
 assert.equal(p.visible([row],'departure',{},t('2026-10-06T00:30:00')).length,0);
 assert.equal(p.visible([row],'departure',{},t('2026-10-07T00:00:00')).length,0);
 assert.equal(p.visible([flight({serviceDate:'2026-10-06'})],'departure',{},t('2026-10-05T10:30:00')).length,0);
 assert.equal(p.today(Date.parse('2026-10-05T15:01:00Z')),'2026-10-06');
});
test('column choices are independent for departures and arrivals',()=>{
 const config={departureColumns:['scheduled','flight'],arrivalColumns:['destination','flight','remark']};
 assert.deepEqual(p.selectedColumns(config,'departure'),['scheduled','flight']);
 assert.deepEqual(p.selectedColumns(config,'arrival'),['destination','flight','remark']);
 assert.equal(p.selectedColumns(null,'arrival').length,7);
});
test('synchronized clock advances on monotonic time despite host clock difference',()=>{
 const clock=p.synchronizedClock('2026-10-05T03:00:00Z',1000,500);
 assert.equal(clock.now(1500),Date.parse('2026-10-05T03:00:01Z'));
 assert.equal(p.visible([flight()],'departure',{},clock.now(500)).length,0);
});
test('installation timezone handles overseas dates and seasonal offsets',()=>{
 try{
  p.configureTimezone('America/New_York');
  assert.equal(p.timestamp('2026-07-01','10:00'),Date.parse('2026-07-01T14:00:00Z'));
  assert.equal(p.timestamp('2026-01-01','10:00'),Date.parse('2026-01-01T15:00:00Z'));
  assert.equal(p.today(Date.parse('2026-07-01T02:00:00Z')),'2026-06-30');
  assert.ok(Number.isNaN(p.timestamp('2026-03-08','02:30')));
  p.configureTimezone('Asia/Bangkok');
  assert.equal(p.timestamp('2026-10-08','10:00'),Date.parse('2026-10-08T03:00:00Z'));
 }finally{p.configureTimezone('Asia/Tokyo');}
});

test('terminal languages rotate in order, independently on each screen',()=>{
 const first={languages:['en','ja'],languageInterval:8};
 const second={languages:['en','ja','zh-Hans'],languageInterval:10};
 assert.equal(p.language(first,0),'en');assert.equal(p.language(first,8000),'ja');assert.equal(p.language(first,16000),'en');
 assert.equal(p.language(second,10000),'ja');assert.equal(p.language(second,20000),'zh-Hans');assert.equal(p.language(second,30000),'en');
 assert.equal(p.language({languages:['ja'],languageInterval:8},24000),'ja');
});

test('ROR next-day departure opens exactly STD minus six hours regardless of delay',()=>{
 try{
  p.configureTimezone('Pacific/Palau');
  const row=flight({serviceDate:'2026-10-06',time:'02:05',estimatedTime:'04:00'});
  const now=Date.parse('2026-10-05T20:05:00+09:00');
  assert.equal(p.visible([row],'departure',{board:{departureShowMinutes:360}},now-1).length,0);
  assert.equal(p.visible([row],'departure',{board:{departureShowMinutes:360}},now).length,1);
  assert.equal(p.visible([row],'departure',{board:{departureShowMinutes:120}},now).length,0);
  assert.equal(p.visible([row],'departure',{},now).length,0);
  assert.equal(p.visible([{...row,direction:'arrival'}],'arrival',{board:{arrivalShowMinutes:360}},now).length,1);
 }finally{p.configureTimezone('Asia/Tokyo');}
});

test('domestic/international filters preserve direction and time rules and exclude unclassified rows',()=>{
 const rows=[flight({geo:'DOM',flightNumber:'DOM'}),flight({geo:'INTL',flightNumber:'INTL'}),flight({flightNumber:'UNKNOWN'}),flight({geo:'INTL',direction:'arrival',flightNumber:'ARR'})];
 const now=t('2026-10-05T08:00:00');
 assert.deepEqual(p.visible(rows,'departure',{board:{traffic:'domestic'}},now).map(r=>r.flightNumber),['DOM']);
 assert.deepEqual(p.visible(rows,'departure',{board:{traffic:'international'}},now).map(r=>r.flightNumber),['INTL']);
 assert.equal(p.visible(rows,'departure',{},now).length,3);
 assert.deepEqual(p.visible(rows,'arrival',{board:{traffic:'international'}},now).map(r=>r.flightNumber),['ARR']);
});

test('codeshares rotate as one identity at exact interval boundaries without changing the operation',()=>{
 const f={flightNumber:'UA142',codeshareFlights:['NH6467','PR999','NH6467'],time:'20:00',gate:'3'};
 const before=JSON.stringify(f);
 assert.equal(p.codeshareNumber(f,{},0),'UA142');assert.equal(p.codeshareNumber(f,{},4999),'UA142');assert.equal(p.codeshareNumber(f,{},5000),'NH6467');assert.equal(p.codeshareNumber(f,{},10000),'PR999');assert.equal(p.codeshareNumber(f,{},15000),'UA142');
 assert.equal(p.codeshareNumber(f,{codeshareEnabled:false},5000),'UA142');assert.equal(p.codeshareNumber(f,{codeshareInterval:7},7000),'NH6467');assert.equal(p.codeshareNumber({flightNumber:'BC101'},{},10000),'BC101');assert.equal(JSON.stringify(f),before);
});
