const names={ja:'日本語',en:'English','zh-Hant':'中文（繁體）','zh-Hans':'中文（简体）',ko:'한국어'};
const words={ja:['出発便','便名','行先','定刻'],en:['Departures','Flight','Destination','Scheduled'],'zh-Hant':['出發航班','航班','目的地','預定'],'zh-Hans':['出发航班','航班','目的地','预定'],ko:['출발편','항공편','목적지','예정']};
const mt=text=>window.managerText?window.managerText(text):text;
const $=id=>document.getElementById(id);const manager=document.body.dataset.view==='manager';
const airport=manager?'SHI':(new URLSearchParams(location.search).get('airport')||'SHI');
const displayId=new URLSearchParams(location.search).get('displayId')||'default';
const settingsKey='pifids:'+airport+':'+displayId;
let syncedClock=null;
let managerSession=null;
function fidsNow(){return syncedClock?syncedClock.now(performance.now()):Date.now();}
function setClock(clock,age=0){if(clock?.utcNow)syncedClock=BoardPolicy.synchronizedClock(new Date(Date.parse(clock.utcNow)+age).toISOString(),Date.now(),performance.now());}
let assetUrls={};let offline=false;
let displayConfig={mode:'board',airline:'',version:0};
let lastDisplayRenderKey=null;
let editing=null,pendingDelete=null,upstreamState=null,upstreamBusy=false;
let state=null,selected=[],lastSuccess=null;let settings={language:'en',interval:8,logo:'',rows:8,direction:new URLSearchParams(location.search).get('direction')==='arrival'?'arrival':'departure'};
try{settings={...settings,...JSON.parse(localStorage.getItem(settingsKey)||'{}')};}catch{}
const boardWords={ja:['定刻','予定','行先／経由','航空会社','便名','ゲート','備考','出発地／経由','到着便'],en:['STD','ETD','Destination / Via','Airline','Flight','Gate','Remark','Origin / Via','Arrivals'],'zh-Hant':['預定','預計','目的地／經由','航空公司','航班','登機口','備註','出發地／經由','抵達航班'],'zh-Hans':['预定','预计','目的地／经由','航空公司','航班','登机口','备注','出发地／经由','到达航班'],ko:['예정','예상','목적지 / 경유','항공사','항공편','게이트','비고','출발지 / 경유','도착편']};
function table(rows,display=false,draft=false){
 const board=document.createElement('table'), head=board.createTHead().insertRow();
 const arrival=boardDirection()==='arrival';const labels=(boardWords[settings.language]||boardWords.en).slice(0,7);
 if(arrival){labels[2]=(boardWords[settings.language]||boardWords.en)[7];if(settings.language==='en'){labels[0]='STA';labels[1]='ETA';}}
 const columns=display?boardColumns():null;
 for(const label of display?columns.map(key=>labels[BoardPolicy.columns.indexOf(key)]):['便名','出発／到着','行先／出発地','運航日','STD / STA','ETD / ETA','ATD / ATA','ゲート','備考','言語',...(draft?['操作']:[])].map(mt)){const th=document.createElement('th');th.textContent=label;head.append(th);}
 const body=board.createTBody();
 for(const flight of rows){
  const row=body.insertRow();const langs=flight.languages?.length?flight.languages:[settings.language];row.lang=langs[Math.floor(fidsNow()/1000/settings.interval)%langs.length];
  const values=display?[flight.time,flight.estimatedTime||'',AirportNames.label(state?.airportNames,flight.destination,row.lang),'',flight.flightNumber,flight.gate||'',flight.remark||'']:[flight.flightNumber,mt(flight.direction==='arrival'?'到着':'出発'),flight.destination,flight.serviceDate||'',flight.time,flight.estimatedTime?(flight.estimatedDate&&flight.estimatedDate!==flight.serviceDate?flight.estimatedDate+' ':'')+flight.estimatedTime:'',flight.actualTime?(flight.actualDate&&flight.actualDate!==flight.serviceDate?flight.actualDate+' ':'')+flight.actualTime:'',flight.gate||'',flight.remark||'',langs.map(x=>names[x]).join(' → ')];
  const shown=display?columns.map(key=>values[BoardPolicy.columns.indexOf(key)]):values;
  for(const value of shown){const cell=row.insertCell();cell.textContent=value;}
  if(display){const widths={scheduled:8,estimated:8,destination:25,airline:12,flight:12,gate:6,remark:15},total=columns.reduce((n,key)=>n+widths[key],0);for(const [i,key]of columns.entries()){head.cells[i].style.width=widths[key]/total*100+'%';head.cells[i].dataset.column=key;row.cells[i].dataset.column=key;}}
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
  if(display&&columns.includes('airline')&&flight.airlineLogo&&assetUrls[flight.airlineLogo]){const logo=document.createElement('img');logo.className='flight-logo';logo.alt=flight.flightNumber+' 航空会社ロゴ';logo.src=assetUrls[flight.airlineLogo];row.cells[columns.indexOf('airline')].append(logo);}
 }
 return board;
}
function render(){
 if(!state)return;
 if(manager){updateEditorLabels();$('draft').replaceChildren(state.draft.length?table(state.draft,false,true):emptyManager('下書きの便はありません。便を追加するかWebから取り込んでください。'));$('published').replaceChildren(state.flights.length?table(state.flights):emptyManager('公開済みの便はありません。下書きを確認して公開してください。'));return;}
 const mode=displayConfig.mode, fullImage=mode!=='board'&&!!assetUrls[displayConfig.image];
 const arrival=boardDirection()==='arrival';document.body.dataset.direction=arrival?'arrival':'departure';document.body.dataset.mode=mode;document.body.classList.toggle('image-only',fullImage);
 const labels=words[settings.language]||words.en;
 const purposes={ja:['チェックイン','搭乗口'],en:['Check-in','Boarding gate'],'zh-Hant':['報到櫃檯','登機口'],'zh-Hans':['值机柜台','登机口'],ko:['체크인','탑승구']};
 const purpose=(purposes[settings.language]||purposes.en)[mode==='counter'?0:1];
 const pageSize=Number.isInteger(settings.rows)&&settings.rows>=4&&settings.rows<=16?settings.rows:8;
 const visibleFlights=mode==='board'?BoardPolicy.visible(state.flights,arrival?'arrival':'departure',displayConfig,fidsNow()):[];
 const pages=Math.max(1,Math.ceil(visibleFlights.length/pageSize));
 const page=Math.floor(fidsNow()/1000/15)%pages;
 const renderKey=mode!=='board'?JSON.stringify([mode,displayConfig,settings.logo]):JSON.stringify([visibleFlights,state.version,displayConfig.version,mode,fullImage,settings.language,settings.direction,page,pageSize,Math.floor(fidsNow()/1000/settings.interval),settings.logo]);
 $('status').textContent=(offline?'通信停止・保存済み表示 · ':'')+'画面 '+displayId+' · 表示指示 '+displayConfig.version+' · 版 '+state.version+' · 最終取得 '+lastSuccess.toLocaleTimeString();
 if(lastDisplayRenderKey===renderKey)return;lastDisplayRenderKey=renderKey;
 if(mode==='board'){
  if(visibleFlights.length){const board=table(visibleFlights.slice(page*pageSize,(page+1)*pageSize),true);board.className='flight-board';board.style.setProperty('--page-rows',pageSize);$('board').replaceChildren(board);}
  else{const empty=document.createElement('div');empty.className='empty-board';empty.textContent='No flights to display / 表示対象便なし';$('board').replaceChildren(empty);}
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
 const airportLogo=$('airportLogo'),boardLogo=displayConfig.board?.logo;airportLogo.src=mode==='board'&&boardLogo?assetUrls[boardLogo]||'':settings.logo;airportLogo.hidden=!airportLogo.getAttribute('src');
 $('title').textContent=mode==='board'?(arrival?(boardWords[settings.language]||boardWords.en)[8]:labels[0]):purpose;
 if(settings.language==='en'&&mode==='board')$('title').textContent=arrival?'Arrivals':'Departures';
 $('footerAirport').textContent=airport+' · '+(mode==='board'?'Flight information':displayConfig.airline);
 $('localDate').textContent=new Intl.DateTimeFormat('en-GB',{timeZone:state?.timezone||(airport==='ROR'?'Pacific/Palau':'Asia/Tokyo'),day:'2-digit',month:'short',year:'numeric'}).format(new Date(fidsNow()));
 $('status').textContent=(offline?'通信停止・保存済み表示 · ':'')+'画面 '+displayId+' · 表示指示 '+displayConfig.version+' · 版 '+state.version+' · 最終取得 '+lastSuccess.toLocaleTimeString();
}
function updateEditorLabels(){
 $('saveFlight').textContent=mt(editing?'変更を保存':'下書きに追加');
 $('cancelEdit').textContent=mt('編集をキャンセル');$('cancelEdit').hidden=!editing;
 $('editStatus').textContent=editing?mt('編集中')+' · '+$('flightForm').elements.flightNumber.value:'';
}
function resetEditor(){editing=null;$('flightForm').reset();$('flightForm').elements.serviceDate.value=BoardPolicy.today(fidsNow());selected=[];for(const box of $('languages').querySelectorAll('input'))box.checked=false;$('languageOrder').textContent='';updateEditorLabels();}
function editFlight(flight){
 $('flightEditor').open=true;
 editing={id:flight.id,expectedDraftRevision:state.draftRevision};pendingDelete=null;
 for(const key of ['flightNumber','destination','serviceDate','time','estimatedTime','estimatedDate','actualTime','actualDate','gate','remark','airlineLogo','direction'])$('flightForm').elements[key].value=flight[key]||(key==='direction'?'departure':'');
 selected=[...(flight.languages||[])];for(const [index,box]of [...$('languages').querySelectorAll('input')].entries())box.checked=selected.includes(Object.keys(names)[index]);
 $('languageOrder').textContent=selected.map(x=>names[x]).join(' → ');render();$('flightForm').scrollIntoView({behavior:'smooth',block:'start'});
}
async function refresh(){try{if(manager){const sessionResponse=await fetch('/api/session');if(!sessionResponse.ok)throw Error('Could not load session');const session=await sessionResponse.json();if(!session.authenticated){location.replace('/login');return;}if(JSON.stringify(session.user)!==JSON.stringify(managerSession?.user)){managerSession=session;window.managerSession=session;window.dispatchEvent(new Event('managersessionchange'));managerPage();}}const a=manager?$('airport').value:airport;const response=await fetch('/api/state?airport='+encodeURIComponent(a));if(!response.ok)throw Error(mt('取得失敗'));const next=await response.json();if(!manager){const control=await fetch('/api/display?airport='+encodeURIComponent(a)+'&displayId='+encodeURIComponent(displayId));if(!control.ok)throw Error('表示指示の取得失敗');const nextControl=await control.json();const contentChanged=JSON.stringify([nextControl,next.flights,next.airportNames])!==JSON.stringify([displayConfig,state?.flights,state?.airportNames]);if(contentChanged){const nextUrls=await prepareAssets(nextControl,false,next.flights);const previousUrls=assetUrls;assetUrls=nextUrls;displayConfig=nextControl;lastDisplayRenderKey=null;setTimeout(()=>{for(const url of Object.values(previousUrls))URL.revokeObjectURL(url);},1000);}displayConfig=nextControl;}state=next;if(manager)window.installationTimezone=next.timezone;BoardPolicy.configureTimezone(next.timezone||'Asia/Tokyo');setClock(next.clock);lastSuccess=new Date();offline=false;if(!manager){try{localStorage.setItem(settingsKey+':snapshot',JSON.stringify({state,displayConfig,lastSuccess:lastSuccess.toISOString()}));}catch{}}render();if(manager){$('displayLink').href='/display?airport='+a;refreshAirportCodes();await refreshAssets(a);await refreshRegistry(a);await refreshUpstream(a);if(managerSession?.user?.role==='admin')await refreshClock();}}catch(error){offline=true;$(manager?'message':'status').textContent=(manager?'Update stopped: '+error.message:'更新停止：'+error.message+'（最後の表示を保持）');}}
async function post(path,data){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(result.error);await refresh();return result;}
if(manager){$('openFlightEditor').onclick=()=>{resetEditor();$('flightEditor').open=true;$('flightEditor').scrollIntoView({behavior:'smooth',block:'start'});};for(const [code,name]of Object.entries(names)){const label=document.createElement('label');const box=document.createElement('input');box.type='checkbox';box.onchange=()=>{selected=selected.filter(x=>x!==code);if(box.checked)selected.push(code);$('languageOrder').textContent=selected.map(x=>names[x]).join(' → ');};label.append(box,document.createTextNode(name));$('languages').append(label);}$('airport').onchange=()=>{resetEditor();pendingDelete=null;refresh();};$('cancelEdit').onclick=resetEditor;$('flightForm').onsubmit=async event=>{event.preventDefault();try{const data=Object.fromEntries(new FormData(event.target));await post(editing?'/api/flights/update':'/api/flights',{...data,airport:$('airport').value,languages:selected,...(editing||{})});resetEditor();$('message').textContent=mt('下書きを保存しました。公開すると表示に反映されます。');}catch(error){$('message').textContent=error.message;}};$('publish').onclick=async()=>{try{await post('/api/publish',{airport:$('airport').value});$('message').textContent=mt('公開しました。');}catch(error){$('message').textContent=error.message;}};}else{for(const [code,name]of Object.entries(names)){const option=document.createElement('option');option.value=code;option.textContent=name;$('defaultLanguage').append(option);}$('defaultLanguage').value=settings.language;$('interval').value=settings.interval;$('logoUrl').value=settings.logo;$('rowsPerPage').value=settings.rows;$('boardDirection').value=settings.direction;function logo(){const image=$('airportLogo');image.hidden=!settings.logo;image.src=settings.logo;image.onerror=()=>image.hidden=true;}logo();$('saveSettings').onclick=()=>{const interval=Number($('interval').value);if(!Number.isFinite(interval)||interval<3||interval>60)return;const raw=$('logoUrl').value.trim();if(raw){try{const url=new URL(raw);if(!['http:','https:'].includes(url.protocol))return;}catch{return;}}const rows=Number($('rowsPerPage').value);if(!Number.isInteger(rows)||rows<4||rows>16)return;settings={language:$('defaultLanguage').value,interval,logo:raw,rows,direction:$('boardDirection').value};localStorage.setItem(settingsKey,JSON.stringify(settings));logo();render();};setInterval(()=>{$('clock').textContent=new Intl.DateTimeFormat('en-GB',{timeZone:state?.timezone||(airport==='ROR'?'Pacific/Palau':'Asia/Tokyo'),hour:'2-digit',minute:'2-digit'}).format(new Date(fidsNow()));if(state)render();},1000);}


if(manager){function targetLink(){$('targetDisplay').href='/display?airport='+encodeURIComponent($('airport').value)+'&displayId='+encodeURIComponent($('displayId').value)+'&preview=screens';} $('displayId').oninput=targetLink;$('loadDisplaySettings').onclick=()=>loadDisplayControl().catch(error=>$('message').textContent=error.message);$('displayId').onchange=()=>loadDisplayControl().catch(error=>$('message').textContent=error.message);$('airport').addEventListener('change',()=>{targetLink();loadDisplayControl().catch(error=>$('message').textContent=error.message);});$('displayForm').onsubmit=async event=>{event.preventDefault();try{const data=Object.fromEntries(new FormData(event.target));if(data.usage==='board')data.board=readBoardForm();for(const key of ['departureHideMinutes','arrivalHideMinutes'])data[key]=Number(data[key]);const profile=$('terminalProfile').value;await post('/api/terminals',{...data,airport:$('airport').value});if(data.usage==='signage'&&profile)await post('/api/signage',{airport:$('airport').value,displayId:data.displayId,profileName:profile});targetLink();$('message').textContent=mt('端末設定を保存しました。');}catch(error){$('message').textContent=error.message;}};}

const imageCacheName='pifids-images-v1';
function imagePath(digest){return '/asset?airport='+encodeURIComponent(airport)+'&id='+digest;}
async function prepareAssets(config,cachedOnly=false,flights=[]){
 const cache=await caches.open(imageCacheName);const urls={};
 try{for(const digest of [...new Set([config.logo,config.image,config.board?.logo,...flights.map(flight=>flight.airlineLogo)].filter(Boolean))]){
  const path=imagePath(digest);let response=await cache.match(path);
  if(!response&&!cachedOnly){response=await fetch(path);if(!response.ok)throw Error('画像取得失敗');const bytes=await response.clone().arrayBuffer();const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');if(hash!==digest)throw Error('画像の整合性エラー');await cache.put(path,response.clone());}
  if(!response)throw Error('保存済み画像なし');urls[digest]=URL.createObjectURL(await response.blob());
 }return urls;}catch(error){for(const url of Object.values(urls))URL.revokeObjectURL(url);throw error;}
}
async function startDisplay(){
 try{await navigator.serviceWorker.register('/sw.js');}catch{}
 try{const saved=JSON.parse(localStorage.getItem(settingsKey+':snapshot')||'null');if(saved){const urls=await prepareAssets(saved.displayConfig,true,saved.state.flights);assetUrls=urls;state=saved.state;BoardPolicy.configureTimezone(state.timezone||'Asia/Tokyo');setClock(saved.state.clock,Math.max(0,Date.now()-Date.parse(saved.lastSuccess)));displayConfig=saved.displayConfig;lastSuccess=new Date(saved.lastSuccess);offline=true;render();}}catch{}
 await refresh();setInterval(refresh,5000);
}
async function refreshAssets(a){
 const response=await fetch('/api/assets?airport='+encodeURIComponent(a));if(!response.ok)throw Error(mt('画像一覧取得失敗'));const items=await response.json();for(const id of ['logoAsset','imageAsset','flightLogo','boardLogo']){const select=$(id),old=select.value;select.replaceChildren();const none=document.createElement('option');none.value='';none.textContent=mt('なし');select.append(none);for(const item of items.filter(item=>item.kind==='legacy'||item.kind===(id==='imageAsset'?'signage':'logo'))){const option=document.createElement('option');option.value=item.digest;option.textContent=item.name;select.append(option);}select.value=items.some(item=>item.digest===old)?old:'';}
}
if(manager){$('assetForm').onsubmit=async event=>{event.preventDefault();try{const file=$('assetFile').files[0];if(!file||file.size>2*1024*1024)throw Error(mt('画像は2MBまでです'));const body=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(Error(mt('画像読込失敗')));reader.readAsDataURL(file);});const kind=$('assetKind').value,name=$('assetName').value.trim();const uploaded=await post('/api/assets',{airport:$('airport').value,name,kind,body});if(kind==='signage'){$('profileForm').reset();$('registeredProfile').value='';$('profileForm').elements.name.value=name;$('imageAsset').value=uploaded.digest;$('applySavedProfile').hidden=true;$('profileNext').textContent=mt('航空会社名と表示種別を確認し、表示画面を保存してください。');$('profileForm').scrollIntoView({behavior:'smooth',block:'center'});}$('message').textContent=mt('画像を登録しました。ロゴまたは案内画像を選んで画面に適用してください。');}catch(error){$('message').textContent=error.message;}};}

async function startManager(){
 $('flightForm').elements.serviceDate.value=BoardPolicy.today(fidsNow());
 try{
  const response=await fetch('/api/session');if(!response.ok)throw Error('Could not load sign-in status');const session=await response.json();
  if(!session.authenticated){location.replace('/login');return;}
  managerSession=session;window.managerSession=session;window.dispatchEvent(new Event('managersessionchange'));managerPage();
  const sitesResponse=await fetch('/api/sites');if(!sitesResponse.ok)throw Error('Could not load installation airports');const sites=await sitesResponse.json();const previousAirport=$('airport').value;$('airport').replaceChildren(...sites.map(site=>{const option=document.createElement('option');option.value=site.airport;option.textContent=site.airport;return option;}));if(sites.some(site=>site.airport===previousAirport))$('airport').value=previousAirport;if(session.airport){$('airport').value=session.airport;$('airport').disabled=true;}
  $('targetDisplay').href='/display?airport='+encodeURIComponent($('airport').value)+'&displayId='+encodeURIComponent($('displayId').value)+'&preview=screens';
  $('logout').hidden=!session.secured;$('logout').onclick=async()=>{try{await post('/api/logout',{});location.replace('/login');}catch(error){$('message').textContent=error.message;}};
  await refresh();$('flightForm').elements.serviceDate.value=BoardPolicy.today(fidsNow());await loadDisplayControl();setInterval(refresh,5000);
 }catch(error){$('message').textContent=error.message;}
}
if(manager){startManager();}else{startDisplay();}

if(!manager){
 const setup=new URLSearchParams(location.search).get('setup')==='1';
 document.body.classList.toggle('display-setup',setup);
 const kiosk=new URLSearchParams(location.search).get('kiosk')==='1';
 document.body.classList.toggle('kiosk-display',kiosk&&!setup);
 const back=$('managerBack'),preview=new URLSearchParams(location.search).get('preview');back.hidden=kiosk;back.href='/?airport='+encodeURIComponent(airport)+(preview==='screens'?'#screensPanel':'#signagePanel');
 const setupUrl=new URL(location.href);setupUrl.searchParams.set('setup','1');$('settingsLink').href=setupUrl.href;
 $('fullscreen').onclick=async()=>{try{if(!document.documentElement.requestFullscreen)throw Error('このブラウザでは全画面表示を利用できません。ブラウザの全画面操作を使用してください。');await document.documentElement.requestFullscreen();}catch(error){$('fullscreenMessage').textContent=error.message||'全画面表示を開始できませんでした。';}};
 document.addEventListener('fullscreenchange',()=>document.body.classList.toggle('is-fullscreen',!!document.fullscreenElement));
}

if(manager)window.addEventListener('managerlanguagechange',()=>{render();refreshAssets($('airport').value).catch(error=>$('message').textContent=error.message);$('message').textContent='';});

async function refreshUpstream(a){
 const serviceDate=$('upstreamDate').value;
 const response=await fetch('/api/upstream?airport='+encodeURIComponent(a)+(serviceDate?'&serviceDate='+encodeURIComponent(serviceDate):''));
 const result=await response.json();if(!response.ok){upstreamState=null;$('upstreamCheck').disabled=true;$('upstreamImport').disabled=true;$('upstreamStatus').textContent=result.error;$('upstreamPreview').replaceChildren();return;}
 renderWebSync(result);
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

let displayFormRevision=0;
if(manager)$('displayForm').addEventListener('input',event=>{if(event.target.name!=='displayId')displayFormRevision++;});
async function loadDisplayControl(){
 const revision=displayFormRevision,identity=[$('airport').value,$('displayId').value];
 const response=await fetch('/api/display?airport='+encodeURIComponent(identity[0])+'&displayId='+encodeURIComponent(identity[1]));
 const control=await response.json();if(!response.ok)throw Error(control.error);
 if(revision!==displayFormRevision||identity[0]!==$('airport').value||identity[1]!==$('displayId').value)return;
 for(const key of ['departureHideMinutes','arrivalHideMinutes'])$('displayForm').elements[key].value=control[key];
 const terminal=registryState.terminals.find(x=>x.displayId===identity[1]);$('displayForm').elements.name.value=terminal?.name||'';
 $('terminalUsage').value=terminal?.usage||'signage';$('terminalDirection').value=control.board?.direction||'departure';$('boardLogo').value=control.board?.logo||'';
 for(const direction of ['departure','arrival'])for(const box of $(direction+'Columns').querySelectorAll('input'))box.checked=(control.board?.[direction+'Columns']||BoardPolicy.columns).includes(box.value);
 $('terminalProfile').replaceChildren();for(const profile of [{name:mt('なし'),value:''},...registryState.profiles.map(p=>({name:p.name,value:p.name}))]){const option=document.createElement('option');option.value=profile.value;option.textContent=profile.name;$('terminalProfile').append(option);}$('terminalProfile').value=terminal?.profileName||'';boardFormVisibility();
}

function emptyManager(text){const box=document.createElement('p');box.className='manager-empty';box.textContent=mt(text);return box;}

let registryState={terminals:[],profiles:[]};
function namedOptions(id,items,valueKey,blank){
 const select=$(id),old=select.value;select.replaceChildren();
 if(blank!==null){const option=document.createElement('option');option.value='';option.textContent=mt(blank);select.append(option);}
 for(const item of items){const option=document.createElement('option');option.value=item[valueKey];option.textContent=item.name;select.append(option);}
 if([...select.options].some(x=>x.value===old))select.value=old;
}
async function refreshRegistry(a){
 const response=await fetch('/api/registry?airport='+encodeURIComponent(a));if(!response.ok)throw Error('Could not load terminals and layouts');
 if(a!==$('airport').value)return;registryState=await response.json();
 namedOptions('registeredTerminal',registryState.terminals,'displayId','新しい端末');
 namedOptions('registeredProfile',registryState.profiles,'name','新しい表示画面');
 const signageTerminals=registryState.terminals.filter(x=>x.usage==='signage');
 namedOptions('signageTerminal',signageTerminals,'displayId',signageTerminals.length?null:'端末を登録してください');
 namedOptions('signageProfile',registryState.profiles,'name','便一覧');
 $('signageForm').querySelector('button').disabled=!signageTerminals.length;
 $('signageTerminal').disabled=!signageTerminals.length;
 $('signageEmpty').hidden=!!signageTerminals.length;
 await signageStatus();renderTerminalLists();
}
async function signageStatus(){
 const id=$('signageTerminal').value,a=$('airport').value;
 if(!id){$('signageCurrent').textContent='';$('signagePreview').hidden=true;return;}
 const response=await fetch('/api/display?airport='+encodeURIComponent(a)+'&displayId='+encodeURIComponent(id));if(!response.ok)return;
 const control=await response.json();if(id!==$('signageTerminal').value||a!==$('airport').value)return;
 const applied=registryState.terminals.find(x=>x.displayId===id)?.profileName;
 const match=registryState.profiles.find(x=>x.mode===control.mode&&x.airline===control.airline&&x.logo===control.logo&&x.image===control.image);
 const identity=a+':'+id;if(signageViewedTerminal!==identity){$('signageProfile').value=control.mode==='board'?'':applied||match?.name||'';signageViewedTerminal=identity;}
 $('signageCurrent').textContent=mt('現在の表示')+': '+(control.mode==='board'?mt('便一覧'):applied||match?.name||control.airline);
 $('signagePreview').hidden=false;$('signagePreview').href='/display?airport='+encodeURIComponent(a)+'&displayId='+encodeURIComponent(id)+'&preview=signage';
}
let signageViewedTerminal='',savedProfile=null;
function managerPage(){
 if(!manager)return;const hash=location.hash||'#flightsPanel';
 let page=['#signagePanel','#screensPanel','#assetsPanel','#airportCodesPanel','#usersPanel','#clockPanel','#auditPanel'].includes(hash)?hash:'#flightsPanel';
 const allowed=managerSession?.user?.role==='admin';
 if(!allowed&&!['#flightsPanel','#signagePanel'].includes(page))page='#flightsPanel';
 for(const link of document.querySelectorAll('.manager-nav a'))link.hidden=!allowed&&!['#flightsPanel','#signagePanel'].includes(link.hash);
 $('flightPage').hidden=page!=='#flightsPanel';
 for(const id of ['signagePanel','screensPanel','assetsPanel','airportCodesPanel','usersPanel','clockPanel','auditPanel'])$(id).hidden=page!=='#'+id;
 for(const link of document.querySelectorAll('.manager-nav a')){if(link.hash===page)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');}
 const titles={'#flightsPanel':'フライト情報管理','#signagePanel':'チェックイン・ゲート表示管理','#screensPanel':'端末の設定','#assetsPanel':'ロゴ・画像登録','#airportCodesPanel':'空港コード入力・更新','#clockPanel':'時刻同期・修正','#usersPanel':'ユーザー管理','#auditPanel':'監査ログ'};
 document.querySelector('.manager-intro h1').textContent=mt(titles[page]);
 const descriptions={'#flightsPanel':'便を編集して公開し、空港内の表示を管理します。','#signagePanel':'登録済みの端末と表示画面を選択して切り替えます。','#screensPanel':'航空会社・クラスなど、運用で分かる名称を登録します。','#assetsPanel':'ロゴと案内画面を用途別に登録します。','#airportCodesPanel':'空港コードと表示言語ごとの空港名を登録します。','#clockPanel':'表示端末の時計は管理端末とLANで同期します。','#usersPanel':'ユーザーの登録・権限・利用状態を管理します。','#auditPanel':'誰が何を更新したか確認します。'};
 document.querySelector('.manager-intro > div > p:last-child').textContent=mt(descriptions[page]);
}
if(manager){
 managerPage();window.addEventListener('hashchange',managerPage);
 window.addEventListener('managerlanguagechange',()=>{managerPage();refreshRegistry($('airport').value).catch(error=>$('message').textContent=error.message);});
 $('registeredTerminal').onchange=()=>{const item=registryState.terminals.find(x=>x.displayId===$('registeredTerminal').value);$('displayId').value=item?.displayId||'';$('displayForm').elements.name.value=item?.name||'';if(item)loadDisplayControl().catch(error=>$('message').textContent=error.message);};
 $('applySavedProfile').onclick=async()=>{if(!savedProfile||savedProfile.airport!==$('airport').value)return;await refreshRegistry(savedProfile.airport);$('signageProfile').value=savedProfile.name;location.hash='#signagePanel';$('message').textContent=mt('表示する端末を選び、表示を切り替えてください。');};
 $('profileForm').addEventListener('input',()=>{$('applySavedProfile').hidden=true;$('profileNext').textContent='';});
 $('airport').addEventListener('change',()=>{savedProfile=null;$('applySavedProfile').hidden=true;$('profileNext').textContent='';});
 $('registeredProfile').onchange=()=>{const item=registryState.profiles.find(x=>x.name===$('registeredProfile').value);$('profileForm').reset();$('registeredProfile').value=item?.name||'';if(item)for(const key of ['name','mode','airline','logo','image'])$('profileForm').elements[key].value=item[key];};
 $('profileForm').onsubmit=async event=>{event.preventDefault();try{const data=Object.fromEntries(new FormData(event.target));await post('/api/profiles',{...data,airport:$('airport').value});$('registeredProfile').value=data.name;savedProfile={airport:$('airport').value,name:data.name};$('applySavedProfile').hidden=false;$('profileNext').textContent=mt('保存しました。次に表示する端末を選びます。');$('message').textContent=mt('表示画面を保存しました。');}catch(error){$('message').textContent=error.message;}};
 $('signagePreview').onclick=async event=>{event.preventDefault();const id=$('signageTerminal').value,profile=$('signageProfile').value,a=$('airport').value;if(!id)return;try{await post('/api/signage',{airport:a,displayId:id,profileName:profile});location.href='/display?airport='+encodeURIComponent(a)+'&displayId='+encodeURIComponent(id)+'&preview=signage';}catch(error){$('message').textContent=error.message;}};
 $('signageTerminal').onchange=()=>signageStatus().catch(error=>$('message').textContent=error.message);
 $('signageForm').onsubmit=async event=>{event.preventDefault();if(!$('signageTerminal').value){$('message').textContent=mt('端末を登録してください');return;}try{await post('/api/signage',{...Object.fromEntries(new FormData(event.target)),airport:$('airport').value});$('message').textContent=mt('表示を切り替えました。対象画面を確認してください。');}catch(error){$('message').textContent=error.message;}};
 $('airport').addEventListener('change',()=>{$('displayForm').reset();$('profileForm').reset();$('registeredTerminal').value='';$('registeredProfile').value='';});
}

function boardDirection(){return displayConfig.board?.direction||settings.direction;}
function boardColumns(){return BoardPolicy.selectedColumns(displayConfig.board,boardDirection());}
function readBoardForm(){const data={direction:$('terminalDirection').value,logo:$('boardLogo').value};for(const direction of ['departure','arrival'])data[direction+'Columns']=[...$(direction+'Columns').querySelectorAll('input:checked')].map(x=>x.value);return data;}
function boardFormVisibility(){ $('terminalProfileSettings').hidden=$('terminalUsage').value!=='signage';
 const board=$('terminalUsage').value==='board';$('boardTerminalSettings').hidden=!board;
 for(const input of $('boardTerminalSettings').querySelectorAll('input,select'))input.disabled=!board;
 $('departureColumnSettings').hidden=$('terminalDirection').value!=='departure';$('arrivalColumnSettings').hidden=$('terminalDirection').value!=='arrival';
}
if(manager){
 const labels={scheduled:'定刻',estimated:'予定時刻',destination:'行先／出発地',airline:'航空会社ロゴ',flight:'便名',gate:'ゲート',remark:'備考'};
 for(const direction of ['departure','arrival'])for(const key of BoardPolicy.columns){const label=document.createElement('label'),box=document.createElement('input'),caption=document.createElement('span');box.type='checkbox';box.value=key;box.checked=true;caption.dataset.managerLabel=labels[key];caption.textContent=mt(labels[key]);label.append(box,caption);$(direction+'Columns').append(label);}
 $('terminalUsage').onchange=boardFormVisibility;$('terminalDirection').onchange=boardFormVisibility;boardFormVisibility();
 $('displayForm').addEventListener('reset',()=>queueMicrotask(boardFormVisibility));
 function assetHelp(){$('signageSizeHelp').hidden=$('assetKind').value!=='signage';$('logoSizeHelp').hidden=$('assetKind').value!=='logo';}
 $('assetKind').onchange=assetHelp;$('openLogoRegistration').onclick=()=>{$('assetKind').value='logo';assetHelp();};assetHelp();
 window.addEventListener('managerlanguagechange',()=>{for(const label of document.querySelectorAll('[data-manager-label]'))label.textContent=mt(label.dataset.managerLabel);});
}

let clockState=null,clockReceivedAt=0,clockSnapshot=null;
function tickManagerClock(){
 if(!manager||!clockState)return;
 if(clockSnapshot!==clockState){clockSnapshot=clockState;clockReceivedAt=performance.now();}
 const elapsed=performance.now()-clockReceivedAt;
 const formatter=new Intl.DateTimeFormat('en-GB',{timeZone:state?.timezone||'Asia/Tokyo',dateStyle:'medium',timeStyle:'medium'});
 const cells=$('clockInfo').querySelectorAll('dd');
 for(const [index,key]of [[0,'utcNow'],[1,'systemUtcNow']]){
  if(cells[index])cells[index].textContent=formatter.format(new Date(Date.parse(clockState[key])+elapsed));
 }
}
async function refreshClock(){const response=await fetch('/api/clock?airport='+encodeURIComponent($('airport').value));if(!response.ok)throw Error('Could not load clock');clockState=await response.json();const formatter=new Intl.DateTimeFormat('en-GB',{timeZone:state?.timezone||'Asia/Tokyo',dateStyle:'medium',timeStyle:'medium'});$('clockInfo').replaceChildren();for(const [label,value]of [['FIDS時刻',formatter.format(new Date(clockState.utcNow))],['管理PCのOS時刻',formatter.format(new Date(clockState.systemUtcNow))],['OS時刻修正サービス',clockState.osClockAvailable?mt('利用可能'):mt('未設定または停止中')],['Windows Timeサービス',clockState.osClockStatus?.serviceStatus||mt('未確認')],['NTP時刻サーバー',clockState.osClockStatus?.ntpServerEnabled?mt('有効'):mt('未確認')]]){const term=document.createElement('dt'),detail=document.createElement('dd');term.textContent=mt(label);detail.textContent=value;$('clockInfo').append(term,detail);}
 $('clockForm').querySelector('button').disabled=!clockState.osClockAvailable;
 $('osClockHelp').textContent=clockState.osClockAvailable?mt('OS時刻を修正できます。表示端末は次回のNTP同期で追従します。'):mt('Windows管理PCで時刻サービスの初期設定が必要です。現在のプレビューではOS時刻は変更できません。');}
if(manager){$('clockForm').onsubmit=async event=>{event.preventDefault();try{await post('/api/clock',{airport:$('airport').value,mode:'set',targetLocal:$('correctedClock').value,expectedRevision:clockState.revision});$('message').textContent=mt('管理PCのOS時刻を修正しました。');}catch(error){$('message').textContent=error.message;}};$('resetClock').onclick=()=>refreshClock().catch(error=>$('message').textContent=error.message);}
if(manager){
 setInterval(tickManagerClock,1000);
 setInterval(()=>{if(!document.hidden&&!$('clockPanel').hidden)refreshClock().catch(()=>{});},15000);
}

function refreshAirportCodes(){
 if(!manager)return;
 const entries=Object.entries(state?.airportNames||{}).sort(([a],[b])=>a.localeCompare(b));
 const select=$('registeredAirportCode'),old=select.value;
 select.replaceChildren(new Option(mt('新しい空港コード'),''));
 for(const [code,item] of entries)select.add(new Option(code+' · '+(item.en||item.ja||code),code));
 if(entries.some(([code])=>code===old))select.value=old;
 const table=document.createElement('table'),head=table.createTHead().insertRow();
 for(const text of ['空港コード（3文字）',...Object.values(names)]){const th=document.createElement('th');th.textContent=mt(text);head.append(th);}
 const body=table.createTBody();
 for(const [code,item] of entries){const row=body.insertRow();for(const value of [code,...Object.keys(names).map(lang=>item[lang]||'')])row.insertCell().textContent=value;}
 $('airportCodeList').replaceChildren(table);
}
if(manager){
 $('registeredAirportCode').onchange=()=>{const form=$('airportCodeForm'),code=$('registeredAirportCode').value,item=state.airportNames?.[code]||{};form.elements.code.value=code;for(const lang of Object.keys(names))form.elements[lang].value=item[lang]||'';};
 $('airportCodeForm').onsubmit=async event=>{event.preventDefault();const form=event.target;try{const data=Object.fromEntries(new FormData(form));const code=data.code.toUpperCase();delete data.code;await post('/api/airport-names',{airport:$('airport').value,code,names:data});$('registeredAirportCode').value=code;form.elements.code.value=code;$('message').textContent=mt('空港名を保存しました。表示端末にも反映します。');}catch(error){$('message').textContent=error.message;}};
 $('airport').addEventListener('change',()=>{$('airportCodeForm').reset();});
 window.addEventListener('managerlanguagechange',refreshAirportCodes);
}

function renderTerminalLists(){
 const language=$('managerLanguage').value;
 const key=JSON.stringify([registryState,language]);
 if(renderTerminalLists.key===key)return;renderTerminalLists.key=key;
 const current=t=>t.currentDisplay||t.profileName|| (t.usage==='board'?mt(t.direction==='arrival'?'到着':'出発')+' · '+mt('便一覧'):mt('未設定'));
 function make(target,items,signage){
  const container=$(target);container.replaceChildren();
  if(!items.length){container.append(emptyManager('登録済みの端末はありません'));return;}
  const table=document.createElement('table');table.className='terminal-list';
  const head=table.createTHead().insertRow();
  for(const label of ['端末名','端末ID','現在の表示','操作']){const th=document.createElement('th');th.textContent=mt(label);head.append(th);}
  for(const t of items){const row=table.insertRow();for(const value of [t.name,t.displayId,current(t)])row.insertCell().textContent=value;
   const cell=row.insertCell();
   function button(label,action){const b=document.createElement('button');b.type='button';b.textContent=mt(label);b.onclick=action;cell.append(b);}
   if(signage){const select=document.createElement('select');for(const profile of registryState.profiles){const option=document.createElement('option');option.value=profile.name;option.textContent=profile.name;select.append(option);}select.value=t.profileName||'';cell.append(select);
    button('表示を切り替える',async()=>{try{if(!select.value)return;await post('/api/signage',{airport:$('airport').value,displayId:t.displayId,profileName:select.value});$('message').textContent=mt('表示を切り替えました。対象画面を確認してください。');}catch(e){$('message').textContent=e.message;}});
   }else{
    button('設定を変更',()=>{$('registeredTerminal').value=t.displayId;$('displayId').value=t.displayId;loadDisplayControl().then(()=>$('displayForm').scrollIntoView({behavior:'smooth'}));});
    button('削除',async()=>{if(!confirm(mt('この端末の登録を削除しますか？')+' '+t.name))return;try{await post('/api/terminals/delete',{airport:$('airport').value,displayId:t.displayId});$('registeredTerminal').value='';$('displayId').value='';$('displayForm').elements.name.value='';$('message').textContent=mt('端末の登録を削除しました。');}catch(e){$('message').textContent=e.message;}});
   }
  }container.append(table);
 }
 make('signageTerminalList',registryState.terminals.filter(t=>t.usage==='signage'),true);
 make('settingsTerminalList',registryState.terminals,false);
}

function renderWebSync(result){
 const en=(localStorage.getItem('pifids:manager-language')||document.documentElement.lang)==='en';
 const t=(ja,english)=>en?english:ja;
 const mode=$('upstreamMode'),button=$('saveUpstreamMode');
 if(!mode.dataset.dirty)mode.value=result.mode||'manual';
 mode.disabled=button.disabled=!result.configured||managerSession?.user?.role!=='admin';
 const labels={online:t('オンライン','Online'),offline:t('オフライン — 最後の公開情報を継続表示','Offline — retaining last published data'),unknown:t('未確認','Not checked'),error:t('接続エラー（認証・データを確認）','Connection error (check credentials or data)')};
 $('upstreamConnection').textContent=t('接続状態：','Connection: ')+(result.configured?labels[result.connectionStatus||'unknown']:t('未設定','Not configured'));
 const format=value=>value?new Date(value).toLocaleString(en?'en-GB':'ja-JP',{timeZone:state?.timezone||'Asia/Tokyo'}):'—';
 $('upstreamTimes').textContent=t('最終受信：','Last received: ')+format(result.lastSuccess)+' · '+t('最終Web公開：','Last Web publication: ')+format(result.lastPublish)+' · '+t('接続確認：','Connection checked: ')+format(result.lastAttempt);
 const states={review_required:t('未公開の変更があります。下書きを確認・公開してから自動同期を再開します。','Unpublished changes require review and publication before automatic sync can resume.'),not_applicable:t('当日適用できるWeb情報がありません。最後の公開情報を保持しています。','No applicable Web data for today. Keeping last published data.'),failed:t('自動同期に失敗しました。最後の公開情報を保持し、次回再試行します。','Automatic sync failed. Keeping last published data and retrying next time.')};
 if(states[result.autoResult])$('upstreamConnection').textContent+=' · '+states[result.autoResult];
}
if(manager)$('saveUpstreamMode').onclick=async()=>{try{const mode=$('upstreamMode').value;if(mode==='auto'&&!confirm(mt('自動受信・公開を開始します。新しいWeb配信は確認なしで表示へ反映されます。よろしいですか？')))return;await post('/api/upstream/mode',{airport:$('airport').value,mode});delete $('upstreamMode').dataset.dirty;await refreshUpstream($('airport').value);}catch(error){$('message').textContent=error.message;}};

if(manager)$('upstreamMode').onchange=()=>{$('upstreamMode').dataset.dirty='true';};
