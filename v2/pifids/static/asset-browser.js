(()=>{
 if(document.body.dataset.view!=='manager')return;
 const t=(ja,en)=>document.documentElement.lang==='ja'?ja:en;
 const dialog=document.createElement('dialog');dialog.id='assetBrowser';document.body.append(dialog);
 const heading=document.createElement('h2'),close=document.createElement('button'),reload=document.createElement('button');close.type=reload.type='button';close.onclick=()=>dialog.close();reload.onclick=()=>load();
 const toolbar=document.createElement('div');toolbar.className='asset-browser-toolbar';
 const search=document.createElement('input');search.type='search';
 const filter=document.createElement('select');const filterLabels=[['all','すべて','All'],['logo','ロゴ','Logos'],['signage','案内画像','Signage'],['default','Default画像','Default images'],['unused','未使用','Unused']];for(const [value,ja,en]of filterLabels){const option=document.createElement('option');option.value=value;option.textContent=t(ja,en);filter.append(option);}
 const message=document.createElement('p');message.id='assetBrowserMessage';message.setAttribute('role','status');
 const grid=document.createElement('div');grid.className='asset-browser-grid';const detail=document.createElement('section');detail.className='asset-browser-detail';
 const content=document.createElement('div');content.className='asset-browser-content';content.append(grid,detail);toolbar.append(search,filter,reload,close);dialog.append(heading,toolbar,message,content);
 let items=[],airport='',selected='',loading=false;
 const url=item=>item.builtin?'/static/branding/mkm-airworks-horizontal.png':'/asset?airport='+encodeURIComponent(airport)+'&id='+item.digest;
 const isDefault=item=>item.builtin||item.usage.some(ref=>ref.field==='defaultImage');
 function usageLabel(ref){const categories={terminal:t('端末','Terminal'),airline:t('航空会社','Airline'),profile:t('表示画面','Screen profile'),draft:t('下書き便','Draft flight'),published:t('公開便','Published flight')};return (categories[ref.kind]||ref.kind)+'：'+ref.name+(ref.field==='defaultImage'?' · Default':'');}
 function render(){
  grid.replaceChildren();const query=search.value.trim().toLowerCase();
  const visible=items.filter(item=>item.name.toLowerCase().includes(query)&&(filter.value==='all'||filter.value==='unused'&&item.canDelete||filter.value==='default'&&isDefault(item)||filter.value===item.kind));
  for(const item of visible){const tile=document.createElement('button');tile.type='button';tile.className='asset-browser-tile';tile.setAttribute('aria-pressed',String(selected===item.digest));const image=document.createElement('img');image.src=url(item);image.alt='';const label=document.createElement('span');label.textContent=item.name;tile.append(image,label);tile.onclick=()=>{selected=item.digest;render();};grid.append(tile);}
  if(!visible.length){const empty=document.createElement('p');empty.textContent=t('該当する画像がありません。','No matching images.');grid.append(empty);}
  detail.replaceChildren();const item=items.find(x=>x.digest===selected);
  if(!item){detail.textContent=t('画像を選ぶと拡大表示と使用先を確認できます。','Select an image to preview it and see where it is used.');return;}
  const title=document.createElement('h3');title.textContent=item.name;const image=document.createElement('img');image.src=url(item);image.alt=item.name;
  const info=document.createElement('p');info.textContent=item.builtin?t('内蔵Default画像（削除できません）','Built-in default image (cannot be deleted)'):[item.width&&item.height?item.width+' × '+item.height:'',Math.round(item.bytes/1024)+' KB',item.mime].filter(Boolean).join(' · ');
  const usages=document.createElement('ul');for(const ref of item.usage){const li=document.createElement('li');li.textContent=usageLabel(ref);usages.append(li);}
  const help=document.createElement('p');help.textContent=item.builtin?t('犬付きMKMロゴは常に使用できます。','The MKM logo with the dog is always available.'):item.canDelete?t('未使用の画像です。削除できます。','This image is unused and can be deleted.'):t('使用中です。上記の設定から画像の割り当てを解除すると削除できます。','This image is in use. Remove the assignments above before deleting it.');
  const remove=document.createElement('button');remove.type='button';remove.textContent=t('この画像を削除','Delete this image');remove.disabled=!item.canDelete;
  remove.onclick=async()=>{if(!confirm(t('この画像を削除しますか？','Delete this image?')+'\n'+item.name))return;try{await post('/api/assets/delete',{airport,digest:item.digest});selected='';await load();message.textContent=t('画像を削除しました。','Image deleted.');}catch(error){message.textContent=error.message;}};
  detail.append(title,image,info,usages,help,remove);
 }
 async function load(){if(loading)return;loading=true;message.textContent=t('画像一覧を読み込み中…','Loading images…');try{const current=$('airport').value;const response=await fetch('/api/assets/catalog?airport='+encodeURIComponent(current));const data=await response.json();if(!response.ok)throw Error(data.error||'Could not load images');if(current!==$('airport').value)return;airport=current;items=data;message.textContent=t('登録画像：','Registered images: ')+items.filter(x=>!x.builtin).length;render();}catch(error){message.textContent=error.message;}finally{loading=false;}}
 search.oninput=filter.onchange=render;
 $('openAssetBrowser').onclick=async()=>{heading.textContent=t('登録済みのロゴ・案内画像','Registered logos and signage images');close.textContent=t('閉じる','Close');reload.textContent=t('一覧を更新','Refresh');search.placeholder=t('画像名で検索','Search image names');search.setAttribute('aria-label',search.placeholder);filter.setAttribute('aria-label',t('画像の種類','Image type'));dialog.showModal();await load();};
 function labels(){for(const [value,ja,en]of filterLabels)filter.querySelector('option[value="'+value+'"]').textContent=t(ja,en);$('openAssetBrowser').textContent=t('登録済みのロゴ・画像を見る','Browse registered logos and images');}labels();window.addEventListener('managerlanguagechange',()=>{labels();dialog.close();});
 $('airport').addEventListener('change',()=>{dialog.close();selected='';items=[];grid.replaceChildren();detail.replaceChildren();});
})();
