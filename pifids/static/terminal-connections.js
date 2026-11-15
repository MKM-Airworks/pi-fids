(()=>{
 if(document.body.dataset.view!=='manager')return;
 const t=(ja,en)=>document.documentElement.lang==='ja'?ja:en;
 const dialog=document.createElement('dialog');dialog.id='terminalConnectionDialog';document.body.append(dialog);
 const heading=document.createElement('h2'),help=document.createElement('p'),selectLabel=document.createElement('label'),sourceLabel=document.createElement('label'),warning=document.createElement('p'),status=document.createElement('p'),issue=document.createElement('button'),close=document.createElement('button');
 const select=document.createElement('select'),source=document.createElement('input');source.type='url';source.placeholder='http://192.168.0.227:8805';source.required=true;selectLabel.append(select);sourceLabel.append(source);status.setAttribute('role','status');issue.type=close.type='button';dialog.append(heading,help,selectLabel,sourceLabel,warning,status,issue,close);
 let issued=[];
 function labels(){
  $('openTerminalConnection').textContent=t('接続設定を発行・ダウンロード','Issue and download connection settings');
  heading.textContent=t('表示端末の接続設定','Display terminal connection');help.textContent=t('保存済みの端末を選び、接続設定ファイルを新しい表示端末へ渡してください。接続キーは画面には表示しません。','Select a saved terminal and transfer the connection file to its display PC. The key is not shown on screen.');
  selectLabel.firstChild?.nodeType===3&&selectLabel.firstChild.remove();sourceLabel.firstChild?.nodeType===3&&sourceLabel.firstChild.remove();selectLabel.prepend(t('登録済み端末','Registered terminal'));sourceLabel.prepend(t('管理PCの配信先URL','Management PC feed URL'));close.textContent=t('閉じる','Close');
 }
 function selection(){const exists=issued.includes(select.value);issue.disabled=!select.value;issue.textContent=exists?t('接続設定を再発行・ダウンロード','Reissue and download connection settings'):t('接続設定を発行・ダウンロード','Issue and download connection settings');warning.textContent=exists?t('再発行すると旧キーは直ちに失効します。対象端末へ新しい設定を適用するまで新規受信は停止します。','Reissuing immediately invalidates the old key. New reception stops until the display uses the new connection file.'):t('この端末専用の接続キーを発行します。ファイルは安全に保管し、対象端末だけに渡してください。','A key will be issued for this terminal. Keep the file private and transfer it only to that display.');}
 window.openTerminalConnection=async displayId=>{
  labels();status.textContent=t('接続設定を確認中…','Checking connection settings…');issue.disabled=true;dialog.showModal();
  try{const response=await fetch('/api/terminal-connections');const data=await response.json();if(!response.ok)throw Error(data.error||'Could not load connection settings');issued=data.issued;source.value=data.source||'';select.replaceChildren();for(const terminal of registryState.terminals){const option=document.createElement('option');option.value=terminal.displayId;option.textContent=terminal.name+' · '+terminal.displayId;select.append(option);}if(displayId&&registryState.terminals.some(x=>x.displayId===displayId))select.value=displayId;selection();status.textContent=select.value?'':t('先に端末を登録・保存してください。','Register and save a terminal first.');}catch(error){status.textContent=error.message;}
 };
 select.onchange=()=>{status.textContent='';selection();};close.onclick=()=>dialog.close();
 issue.onclick=async()=>{
  if(!source.reportValidity())return;
  const exists=issued.includes(select.value);
  if(exists&&!confirm(t('旧キーを失効させ、接続設定を再発行しますか？','Invalidate the old key and reissue the connection settings?')))return;
  issue.disabled=true;status.textContent=t('接続設定を発行中…','Issuing connection settings…');
  try{const connection=await post('/api/terminal-connections/issue',{airport:$('airport').value,displayId:select.value,source:source.value.trim(),replace:exists});if(!issued.includes(connection.displayId))issued.push(connection.displayId);const blob=new Blob([JSON.stringify(connection,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=connection.airport+'-'+connection.displayId+'.connection.json';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);status.textContent=t('発行しました。ダウンロードしたファイルを表示端末のセットアップで指定してください。ファイルはGitHubや共有資料へ保存しないでください。','Issued. Select the downloaded file during display setup. Do not save it to GitHub or shared documentation.');}catch(error){status.textContent=error.message;}finally{selection();}
 };
 $('openTerminalConnection').onclick=()=>window.openTerminalConnection($('registeredTerminal').value||$('displayId').value);labels();window.addEventListener('managerlanguagechange',()=>{labels();dialog.close();});$('airport').addEventListener('change',()=>dialog.close());
})();
