(function(root){
 function active(config,now,zone){
  if(!config?.start)return true;
  const parts=new Intl.DateTimeFormat('en-CA',{timeZone:zone||'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(now));
  const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));
  const day=p.year+'-'+p.month+'-'+p.day,time=p.hour+':'+p.minute;
  const overnight=config.end<config.start;
  const inTime=overnight?(time>=config.start||time<config.end):(time>=config.start&&time<config.end);
  if(!inTime)return false;
  if(!config.date)return true;
  let startDay=day;
  if(overnight&&time<config.end){const d=new Date(day+'T12:00:00Z');d.setUTCDate(d.getUTCDate()-1);startDay=d.toISOString().slice(0,10);}
  return startDay===config.date;
 }
 root.SignagePolicy={active};
 if(typeof module!=='undefined')module.exports=root.SignagePolicy;
})(typeof window==='undefined'?globalThis:window);
