/* Operational times use the installation IANA timezone, including DST. */
(function(root){
 'use strict';
 const minute=60000;
 let zone='Asia/Tokyo';
 function configureTimezone(value){new Intl.DateTimeFormat('en-GB',{timeZone:value}).format(0);zone=value;}
 function localParts(now){const parts=new Intl.DateTimeFormat('en-GB',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(now);return Object.fromEntries(parts.filter(p=>p.type!=='literal').map(p=>[p.type,p.value]));}
 function today(now=Date.now()){const p=localParts(now);return p.year+'-'+p.month+'-'+p.day;}
 function timestamp(date,time){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(date||'')||!/^([01]\d|2[0-3]):[0-5]\d$/.test(time||''))return NaN;
  const target=Date.parse(date+'T'+time+':00Z');let guess=target;
  for(let i=0;i<4;i++){const p=localParts(guess);const local=Date.parse(p.year+'-'+p.month+'-'+p.day+'T'+p.hour+':'+p.minute+':'+p.second+'Z');const next=guess+target-local;if(next===guess)break;guess=next;}
  const p=localParts(guess);return p.year+'-'+p.month+'-'+p.day===date&&p.hour+':'+p.minute===time?guess:NaN;
 }
 function effective(flight){return flight.estimatedTime?timestamp(flight.estimatedDate||flight.serviceDate,flight.estimatedTime):timestamp(flight.serviceDate,flight.time);}
 function deadline(flight,minutes){
  const base=flight.actualTime?timestamp(flight.actualDate||flight.serviceDate,flight.actualTime):effective(flight);
  return base+minutes*minute;
 }
 function visible(flights,direction,control={},now=Date.now()){
  const key=direction==='arrival'?'arrivalHideMinutes':'departureHideMinutes';
  const value=control[key];const minutes=Number.isInteger(value)&&value>=0&&value<=10080?value:(direction==='arrival'?120:10);
  return flights.filter(flight=>(flight.direction||'departure')===direction&&Number.isFinite(effective(flight))&&now<deadline(flight,minutes))
   .sort((a,b)=>effective(a)-effective(b)||a.flightNumber.localeCompare(b.flightNumber));
 }
 const columns=['scheduled','estimated','destination','airline','flight','gate','remark'];
 function selectedColumns(config,direction){const chosen=config?.[direction+'Columns'];return Array.isArray(chosen)&&chosen.length?columns.filter(x=>chosen.includes(x)):[...columns];}
 function synchronizedClock(utcNow,wallNow=Date.now(),monotonicNow=0){const epoch=Date.parse(utcNow);if(!Number.isFinite(epoch))throw Error('Invalid clock');return {now:mono=>epoch+mono-monotonicNow,offset:epoch-wallNow};}
 function language(config,now=Date.now()){const languages=config?.languages?.length?config.languages:['en','ja'];const interval=config?.languageInterval||8;return languages[Math.floor(now/1000/interval)%languages.length];}
 const api={language,configureTimezone,synchronizedClock,today,timestamp,effective,deadline,visible,columns,selectedColumns};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
 else root.BoardPolicy=api;
})(typeof globalThis!=='undefined'?globalThis:this);
