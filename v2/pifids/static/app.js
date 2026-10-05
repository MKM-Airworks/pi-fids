const names={ja:'日本語',en:'English','zh-Hant':'中文（繁體）','zh-Hans':'中文（简体）',ko:'한국어'};
const words={ja:['出発便','便名','行先','定刻'],en:['Departures','Flight','Destination','Scheduled'],'zh-Hant':['出發航班','航班','目的地','預定'],'zh-Hans':['出发航班','航班','目的地','预定'],ko:['출발편','항공편','목적지','예정']};
const mt=text=>window.managerText?window.managerText(text):text;
const $=id=>document.getElementById(id);const manager=document.body.dataset.view==='manager';
const airport=manager?'SHI':(new URLSearchParams(location.search).get('airport')||'SHI');
const displayId=new URLSearchParams(location.search).get('displayId')||'default';
const settingsKey='pifids:'+airport+':'+displayId;
let assetUrls={};let offline=false;
let displayConfig={mode:'board',airline:'',version:0};
let lastDisplayRenderKey=null;
let editing=null,pendingDelete=null,upstreamState=null,upstreamBusy=false;
let state=null,selected=[],lastSuccess=null;let settings={language:'en',interval:8,logo:'',rows:8,direction:new URLSearchParams(location.search).get('direction')==='arrival'?'arrival':'departure'};
try{settings={...settings,...JSON.parse(localStorage.getItem(settingsKey)||'{}')};}catch{}
const boardWords={ja:['定刻','予定','行先／経由','航空会社','便名','ゲート','備考','出発地／経由','到着便'],en:['STD','ETD','Destination / Via','Airline','Flight','Gate','Remark','Origin / Via','Arrivals'],'zh-Hant':['預定','預計','目的地／經由','航空公司','航班','登機口','備註','出發地／經由','抵達航班'],'zh-Hans':['预定','预计','目的地／经由','航空公司','航班','登机口','备注','出发地／经由','到达航班'],ko:['예정','예상','목적지 / 경유','항공사','항공편','게이트','비고','출발지 / 경유','도착편']};
function table(rows,display=false,draft=false){
 const board=document.createElement('table'), head=board.createTHead().insertRow();
 const arrival=settings.direction==='arrival';const labels=(boardWords[settings.language]||boardWords.en).slice(0,7);
 if(arrival){labels[2]=(boardWords[settings.language]||boardWords.en)[7];if(settings.language==='en'){labels[0]='STA';labels[1]='ETA';}}
 for(const label of display?labels:['便名','出発／到着','行先／出発地','定刻','予定時刻','ゲート','備考','言語',...(draft?['操作']:[])].map(mt)){const th=document.createElement('th');th.textContent=label;head.append(th);}
 const body=board.createTBody();
 for(const flight of rows){
  const row=body.insertRow();const langs=flight.languages?.length?flight.languages:[settings.language];row.lang=langs[Math.floor(Date.now()/1000/settings.interval)%langs.length];
  const values=display?[flight.time,flight.estimatedTime||'',flight.destination,'',flight.flightNumber,flight.gate||'',flight.remark||'']:[flight.flightNumber,mt(flight.direction==='arrival'?'到着':'出発'),flight.destination,flight.time,flight.estimatedTime||'',flight.gate||'',flight.remark||'',langs.map(x=>names[x]).join(' → ')];
  for(const value of values){const cell=row.insertCell();cell.textContent=value;}
  if(draft){
   const cell=row.insertCell();
   function button(label,action){const node=document.createElement('button');node.type='button';node.textContent=mt(label);node.onclick=action;cell.append(node);}
   if(pendingDelete?.id===flight.id){
    button('削除を確定',async()=>{try{await post('/api/flights/delete',pendingDelete);if(editing?.id===flight.id)resetEditor();pendingDelete=null;render();$('message').textContent=mt('下書きから削除しました。公開すると表示に反映されます。');}catch(error){$('message').textContent=error.message;pendingDelete=null;await refresh();}});
    button('キャンセル',()=>{pendingDelete=null;render();});
   }else{
    button('編集',()=>editFlight(flight));
    button('削除',()=>{pendingDelete={airport:state.airport,id:flight.id,expectedDraftRevision:state.draftRevision};render();});
   }
  }
  if(display&&flight.airlineLogo&&assetUrls[flight.airlineLogo]){const logo=document.createElement('img');logo.className='flight-logo';logo.alt=flight.flightNumber+' 航空会社ロゴ';logo.src=assetUrls[flight.airlineLogo];row.cells[3].append(logo);}
 }
 return board;
}
function render(){
 if(!state)return;
 if(manager){updateEditorLabels();$('draft').replaceChildren(table(state.draft,false,true));$('published').replaceChildren(table(state.flights));return;}
 const mode=displayConfig.mode, fullImage=mode!=='board'&&!!assetUrls[displayConfig.image];
 const arrival=settings.direction==='arrival';document.body.dataset.direction=arrival?'arrival':'departure';document.body.dataset.mode=mode;document.body.classList.toggle('image-only',fullImage);
 const labels=words[settings.language]||words.en;
 const purposes={ja:['チェックイン','搭乗口'],en:['Check-in','Boarding gate'],'zh-Hant':['報到櫃檯','登機口'],'zh-Hans':['值机柜台','登机口'],ko:['체크인','탑승구']};
 const purpose=(purposes[settings.language]||purposes.en)[mode==='counter'?0:1];
 const pageSize=Number.isInteger(settings.rows)&&settings.rows>=4&&settings.rows<=16?settings.rows:8;
 const visibleFlights=state.flights.filter(flight=>(flight.direction||'departure')===(arrival?'arrival':'departure'));
 const pages=Math.max(1,Math.ceil(visibleFlights.length/pageSize));
 const page=Math.floor(Date.now()/1000/15)%pages;
 const renderKey=JSON.stringify([state.version,displayConfig.version,mode,fullImage,settings.language,settings.direction,page,pageSize,Math.floor(Date.now()/1000/settings.interval),settings.logo]);
 $('status').textContent=(offline?'通信停止・保存済み表示 · ':'')+'画面 '+displayId+' · 表示指示 '+displayConfig.version+' · 版 '+state.version+' · 最終取得 '+lastSuccess.toLocaleTimeString();
 if(lastDisplayRenderKey===renderKey)return;lastDisplayRenderKey=renderKey;
 if(mode==='board'){
  if(visibleFlights.length){const board=table(visibleFlights.slice(page*pageSize,(page+1)*pageSize),true);board.className='flight-board';board.style.setProperty('--page-rows',pageSize);$('board').replaceChildren(board);}
  else{const empty=document.createElement('div');empty.className='empty-board';empty.textContent='No published flights / 公開便なし';$('board').replaceChildren(empty);}
  $('pageIndicator').textContent=(page+1)+' / '+pages;
 }else{
  const panel=document.createElement('section');panel.className='airline-sign';
  if(fullImage){const image=document.createElement('img');image.className='sign-image';image.alt=displayConfig.airline+' · 案内画面';image.src=assetUrls[displayConfig.image];panel.classList.add('sign-with-image');panel.append(image);}
  else{
   const caption=document.createElement('p');caption.className='sign-purpose';caption.textContent=purpose;
   panel.append(caption);
   if(displayConfig.logo&&assetUrls[displayConfig.logo]){panel.classList.add('has-logo');const logo=document.createElement('img');logo.className='sign-logo';logo.alt=displayConfig.airline;logo.src=assetUrls[displayConfig.logo];panel.append(logo);}
   else{const heading=document.createElement('h2');heading.textContent=displayConfig.airline;panel.append(heading);}
  }
  $('board').replaceChildren(panel);$('pageIndicator').textContent='';
 }
 $('title').textContent=mode==='board'?(arrival?(boardWords[settings.language]||boardWords.en)[8]:labels[0]):purpose;
 if(settings.language==='en'&&mode==='board')$('title').textContent=arrival?'Arrivals':'Departures';
 $('footerAirport').textContent=airport+' · '+(mode==='board'?'Flight information':displayConfig.airline);
 $('localDate').textContent=new Intl.DateTimeFormat('en-GB',{timeZone:airport==='ROR'?'Pacific/Palau':'Asia/Tokyo',day:'2-digit',month:'short',year:'numeric'}).format(new Date());
 $('status').textContent=(offline?'通信停止・保存済み表示 · ':'')+'画面 '+displayId+' · 表示指示 '+displayConfig.version+' · 版 '+state.version+' · 最終取得 '+lastSuccess.toLocaleTimeString();
}
function updateEditorLabels(){
 $('saveFlight').textContent=mt(editing?'変更を保存':'下書きに追加');
 $('cancelEdit').textContent=mt('編集をキャンセル');$('cancelEdit').hidden=!editing;
 $('editStatus').textContent=editing?mt('編集中')+' · '+$('flightForm').elements.flightNumber.value:'';
}
function resetEditor(){editing=null;$('flightForm').reset();selected=[];for(const box of $('languages').querySelectorAll('input'))box.checked=false;$('languageOrder').textContent='';updateEditorLabels();}
function editFlight(flight){
 editing={id:flight.id,expectedDraftRevision:state.draftRevision};pendingDelete=null;
 for(const key of ['flightNumber','destination','time','estimatedTime','gate','remark','airlineLogo','direction'])$('flightForm').elements[key].value=flight[key]||(key==='direction'?'departure':'');
 selected=[...(flight.languages||[])];for(const [index,box]of [...$('languages').querySelectorAll('input')].entries())box.checked=selected.includes(Object.keys(names)[index]);
 $('languageOrder').textContent=selected.map(x=>names[x]).join(' → ');render();$('flightForm').scrollIntoView({behavior:'smooth',block:'start'});
}
async function refresh(){try{const a=manager?$('airport').value:airport;const response=await fetch('/api/state?airport='+encodeURIComponent(a));if(!response.ok)throw Error(mt('取得失敗'));const next=await response.json();if(!manager){const control=await fetch('/api/display?airport='+encodeURIComponent(a)+'&displayId='+encodeURIComponent(displayId));if(!control.ok)throw Error('表示指示の取得失敗');const nextControl=await control.json();const nextUrls=await prepareAssets(nextControl,false,next.flights);for(const url of Object.values(assetUrls))URL.revokeObjectURL(url);assetUrls=nextUrls;displayConfig=nextControl;lastDisplayRenderKey=null;}state=next;lastSuccess=new Date();offline=false;if(!manager){try{localStorage.setItem(settingsKey+':snapshot',JSON.stringify({state,displayConfig,lastSuccess:lastSuccess.toISOString()}));}catch{}}render();if(manager){$('displayLink').href='/display?airport='+a;await refreshAssets(a);await refreshUpstream(a);}}catch(error){offline=true;$(manager?'message':'status').textContent=(manager?'Update stopped: '+error.message:'更新停止：'+error.message+'（最後の表示を保持）');}}
async function post(path,data){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(result.error);await refresh();}
if(manager){for(const [code,name]of Object.entries(names)){const label=document.createElement('label');const box=document.createElement('input');box.type='checkbox';box.onchange=()=>{selected=selected.filter(x=>x!==code);if(box.checked)selected.push(code);$('languageOrder').textContent=selected.map(x=>names[x]).join(' → ');};label.append(box,document.createTextNode(name));$('languages').append(label);}$('airport').onchange=()=>{resetEditor();pendingDelete=null;refresh();};$('cancelEdit').onclick=resetEditor;$('flightForm').onsubmit=async event=>{event.preventDefault();try{const data=Object.fromEntries(new FormData(event.target));await post(editing?'/api/flights/update':'/api/flights',{...data,airport:$('airport').value,languages:selected,...(editing||{})});resetEditor();$('message').textContent=mt('下書きを保存しました。公開すると表示に反映されます。');}catch(error){$('message').textContent=error.message;}};$('publish').onclick=async()=>{try{await post('/api/publish',{airport:$('airport').value});$('message').textContent=mt('公開しました。');}catch(error){$('message').textContent=error.message;}};}else{for(const [code,name]of Object.entries(names)){const option=document.createElement('option');option.value=code;option.textContent=name;$('defaultLanguage').append(option);}$('defaultLanguage').value=settings.language;$('interval').value=settings.interval;$('logoUrl').value=settings.logo;$('rowsPerPage').value=settings.rows;$('boardDirection').value=settings.direction;function logo(){const image=$('airportLogo');image.hidden=!settings.logo;image.src=settings.logo;image.onerror=()=>image.hidden=true;}logo();$('saveSettings').onclick=()=>{const interval=Number($('interval').value);if(!Number.isFinite(interval)||interval<3||interval>60)return;const raw=$('logoUrl').value.trim();if(raw){try{const url=new URL(raw);if(!['http:','https:'].includes(url.protocol))return;}catch{return;}}const rows=Number($('rowsPerPage').value);if(!Number.isInteger(rows)||rows<4||rows>16)return;settings={language:$('defaultLanguage').value,interval,logo:raw,rows,direction:$('boardDirection').value};localStorage.setItem(settingsKey,JSON.stringify(settings));logo();render();};setInterval(()=>{$('clock').textContent=new Intl.DateTimeFormat('en-GB',{timeZone:airport==='ROR'?'Pacific/Palau':'Asia/Tokyo',hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date());if(state)render();},1000);}


if(manager){function targetLink(){$('targetDisplay').href='/display?airport='+encodeURIComponent($('airport').value)+'&displayId='+encodeURIComponent($('displayId').value);} $('displayId').oninput=targetLink;$('airport').addEventListener('change',targetLink);$('displayForm').onsubmit=async event=>{event.preventDefault();try{await post('/api/display',{...Object.fromEntries(new FormData(event.target)),airport:$('airport').value});targetLink();$('message').textContent=mt('表示指示を保存しました。対象画面を開き、反映を確認してください。');}catch(error){$('message').textContent=error.message;}};}

const imageCacheName='pifids-images-v1';
function imagePath(digest){return '/asset?airport='+encodeURIComponent(airport)+'&id='+digest;}
async function prepareAssets(config,cachedOnly=false,flights=[]){
 const cache=await caches.open(imageCacheName);const urls={};
 try{for(const digest of [...new Set([config.logo,config.image,...flights.map(flight=>flight.airlineLogo)].filter(Boolean))]){
  const path=imagePath(digest);let response=await cache.match(path);
  if(!response&&!cachedOnly){response=await fetch(path);if(!response.ok)throw Error('画像取得失敗');const bytes=await response.clone().arrayBuffer();const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');if(hash!==digest)throw Error('画像の整合性エラー');await cache.put(path,response.clone());}
  if(!response)throw Error('保存済み画像なし');urls[digest]=URL.createObjectURL(await response.blob());
 }return urls;}catch(error){for(const url of Object.values(urls))URL.revokeObjectURL(url);throw error;}
}
async function startDisplay(){
 try{await navigator.serviceWorker.register('/sw.js');}catch{}
 try{const saved=JSON.parse(localStorage.getItem(settingsKey+':snapshot')||'null');if(saved){const urls=await prepareAssets(saved.displayConfig,true,saved.state.flights);assetUrls=urls;state=saved.state;displayConfig=saved.displayConfig;lastSuccess=new Date(saved.lastSuccess);offline=true;render();}}catch{}
 await refresh();setInterval(refresh,5000);
}
async function refreshAssets(a){
 const response=await fetch('/api/assets?airport='+encodeURIComponent(a));if(!response.ok)throw Error(mt('画像一覧取得失敗'));const items=await response.json();for(const id of ['logoAsset','imageAsset','flightLogo']){const select=$(id),old=select.value;select.replaceChildren();const none=document.createElement('option');none.value='';none.textContent=mt('なし');select.append(none);for(const item of items){const option=document.createElement('option');option.value=item.digest;option.textContent=item.name;select.append(option);}select.value=items.some(item=>item.digest===old)?old:'';}
}
if(manager){$('assetForm').onsubmit=async event=>{event.preventDefault();try{const file=$('assetFile').files[0];if(!file||file.size>2*1024*1024)throw Error(mt('画像は2MBまでです'));const body=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(Error(mt('画像読込失敗')));reader.readAsDataURL(file);});await post('/api/assets',{airport:$('airport').value,name:file.name,body});$('message').textContent=mt('画像を登録しました。ロゴまたは案内画像を選んで画面に適用してください。');}catch(error){$('message').textContent=error.message;}};}

async function startManager(){
 try{
  const response=await fetch('/api/session');if(!response.ok)throw Error('Could not load sign-in status');const session=await response.json();
  if(!session.authenticated){location.replace('/login');return;}
  if(session.airport){$('airport').value=session.airport;$('airport').disabled=true;}
  $('targetDisplay').href='/display?airport='+encodeURIComponent($('airport').value)+'&displayId='+encodeURIComponent($('displayId').value);
  $('logout').hidden=!session.secured;$('logout').onclick=async()=>{try{await post('/api/logout',{});location.replace('/login');}catch(error){$('message').textContent=error.message;}};
  await refresh();setInterval(refresh,5000);
 }catch(error){$('message').textContent=error.message;}
}
if(manager){startManager();}else{startDisplay();}

if(!manager){
 const setup=new URLSearchParams(location.search).get('setup')==='1';
 document.body.classList.toggle('display-setup',setup);
 const kiosk=new URLSearchParams(location.search).get('kiosk')==='1';
 document.body.classList.toggle('kiosk-display',kiosk&&!setup);
 const setupUrl=new URL(location.href);setupUrl.searchParams.set('setup','1');$('settingsLink').href=setupUrl.href;
 $('fullscreen').onclick=async()=>{try{if(!document.documentElement.requestFullscreen)throw Error('このブラウザでは全画面表示を利用できません。ブラウザの全画面操作を使用してください。');await document.documentElement.requestFullscreen();}catch(error){$('fullscreenMessage').textContent=error.message||'全画面表示を開始できませんでした。';}};
 document.addEventListener('fullscreenchange',()=>document.body.classList.toggle('is-fullscreen',!!document.fullscreenElement));
}

if(manager)window.addEventListener('managerlanguagechange',()=>{render();refreshAssets($('airport').value).catch(error=>$('message').textContent=error.message);$('message').textContent='';});

async function refreshUpstream(a){
 const serviceDate=$('upstreamDate').value;
 const response=await fetch('/api/upstream?airport='+encodeURIComponent(a)+(serviceDate?'&serviceDate='+encodeURIComponent(serviceDate):''));
 const result=await response.json();if(!response.ok){upstreamState=null;$('upstreamCheck').disabled=true;$('upstreamImport').disabled=true;$('upstreamStatus').textContent=result.error;$('upstreamPreview').replaceChildren();return;}
 upstreamState=result;$('upstreamCheck').disabled=!result.configured||upstreamBusy;$('upstreamImport').disabled=!result.canImport||upstreamBusy;
 if(!result.configured){$('upstreamStatus').textContent=mt('Web接続は未設定です。');$('upstreamPreview').replaceChildren();return;}
 if(!serviceDate)$('upstreamDate').value=result.serviceDate;
 const status={available:'取込み可能',no_flights:'運航便なし（明示公開）',no_operating_flights:'運航曜日に該当する便なし',no_active_schedules:'有効なダイヤなし',expired:'期限切れ',not_yet_effective:'有効期間前'};
 const attempt={verified:'取得済み',failed:'取得失敗',unauthorized:'認証エラー',not_published:'未公開',unavailable:'通信停止'};
 $('upstreamStatus').textContent=upstreamBusy?mt('Web情報を確認中です。'):[mt(attempt[result.lastResult]||'未取得'),result.webVersion?mt('配信版')+' '+result.webVersion:'',result.preview?mt('検証データ'):'',result.status?mt(status[result.status]):'',result.lastSuccess?mt('最終取得')+' '+new Date(result.lastSuccess).toLocaleString():''].filter(Boolean).join(' · ');
 $('upstreamPreview').replaceChildren(table(result.flights||[]));
}
if(manager){
 $('upstreamDate').onchange=()=>{upstreamState=null;$('upstreamImport').disabled=true;refreshUpstream($('airport').value).catch(error=>$('message').textContent=error.message);};
 $('upstreamCheck').onclick=async()=>{upstreamBusy=true;$('upstreamCheck').disabled=true;$('upstreamImport').disabled=true;$('upstreamStatus').textContent=mt('Web情報を確認中です。');try{await post('/api/upstream/check',{airport:$('airport').value});}catch(error){$('message').textContent=error.message;}finally{upstreamBusy=false;await refreshUpstream($('airport').value);}};
 $('upstreamImport').onclick=async()=>{if(!upstreamState?.canImport||upstreamBusy)return;const snapshot=upstreamState;upstreamBusy=true;try{await post('/api/upstream/import',{airport:$('airport').value,serviceDate:snapshot.serviceDate,webVersion:snapshot.webVersion,expectedDraftRevision:state.draftRevision});resetEditor();pendingDelete=null;$('message').textContent=mt('Web情報を下書きに取り込みました。確認後に公開してください。');}catch(error){$('message').textContent=error.message;}finally{upstreamBusy=false;await refreshUpstream($('airport').value);}};
 window.addEventListener('managerlanguagechange',()=>refreshUpstream($('airport').value).catch(error=>$('message').textContent=error.message));
}
