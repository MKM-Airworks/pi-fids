(() => {
 if(!manager)return;
 let prepared=null;
 const file=$('seasonalCsvFile'),day=$('seasonalCsvDate'),message=$('seasonalCsvMessage'),apply=$('importSeasonalCsv');
 const clear=()=>{prepared=null;apply.disabled=true;};file.onchange=day.onchange=clear;$('airport').addEventListener('change',clear);
 $('previewSeasonalCsv').onclick=async()=>{clear();try{
  if(!file.files[0]||file.files[0].size>128*1024)throw Error(mt('UTF-8のCSV（128KBまで）を選んでください。'));
  if(!day.value)day.value=BoardPolicy.today(fidsNow());
  const payload={airport:$('airport').value,serviceDate:day.value,csv:await file.files[0].text(),expectedDraftRevision:state.draftRevision};
  const result=await post('/api/schedules/csv/preview',payload);
  prepared=payload;apply.disabled=false;
  message.textContent=mt('シーズナル設定：')+result.scheduleCount+' · '+result.coverage.from+' → '+result.coverage.to+' · '+mt('運航日の便数：')+result.flights.length;
  const table=document.createElement('table');for(const row of result.flights){const tr=table.insertRow();for(const text of [row.flightNumber,row.direction,row.destination,row.serviceDate,row.time])tr.insertCell().textContent=text;}$('seasonalCsvPreview').replaceChildren(table);
 }catch(error){message.textContent=error.message;}};
 apply.onclick=async()=>{if(!prepared)return;apply.disabled=true;try{await post('/api/schedules/csv/import',prepared);clear();message.textContent=mt('CSVを下書きへ取り込みました。確認して「下書きを公開」を押してください。');}catch(error){clear();message.textContent=error.message;}};
})();
