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
 assert.equal(p.visible([flight({serviceDate:'2026-10-06'})],'departure',{},t('2026-10-05T10:30:00')).length,1);
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
