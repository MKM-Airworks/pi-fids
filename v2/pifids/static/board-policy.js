/* The supported airports SHI and ROR both use UTC+09:00. */
(function(root){
 'use strict';
 const minute=60000;
 function today(now=Date.now()){return new Date(now+9*60*minute).toISOString().slice(0,10);}
 function timestamp(date,time){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(date||'')||!/^([01]\d|2[0-3]):[0-5]\d$/.test(time||''))return NaN;
  return Date.parse(date+'T'+time+':00+09:00');
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
 const api={today,timestamp,effective,deadline,visible};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
 else root.BoardPolicy=api;
})(typeof globalThis!=='undefined'?globalThis:this);
