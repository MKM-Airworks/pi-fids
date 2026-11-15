/* Keep action feedback visible even when the page's original message is off screen. */
(()=>{
 if(document.body.dataset.view!=='manager')return;
 const notice=document.createElement('div');notice.id='actionFeedback';notice.hidden=true;
 notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');
 document.body.append(notice);
 const pending=new WeakSet();let sequence=0,timer;
 const text=(ja,en)=>document.documentElement.lang==='ja'?ja:en;
 const messages=()=>[...document.querySelectorAll('#message,[id$="Message"],#seasonalCsvMessage')];
 function show(value,busy=false){clearTimeout(timer);notice.textContent=value;notice.hidden=false;notice.dataset.busy=String(busy);}
 function prepare(element,key){
  const original=element[key];if(typeof original!=='function'||original.feedbackWrapped)return;
  const wrapped=function(event){
   if(pending.has(element)){event.preventDefault();event.stopImmediatePropagation();return;}
   const token=++sequence,before=new Map(messages().map(x=>[x,x.textContent]));
   const button=key==='onsubmit'?event.submitter:element;
   show(text('操作を受け付けました。','Action received.'));
   let result;
   try{result=original.call(this,event);}catch(error){show(error.message);throw error;}
   if(!result||typeof result.then!=='function'){
    timer=setTimeout(()=>{notice.hidden=true;},4000);return;
   }
   pending.add(element);
   // Run the handler first: it may read FormData or deliberately disable a button.
   const restoreEnabled=button&&!button.disabled;
   if(button){button.disabled=true;button.setAttribute('aria-busy','true');button.dataset.actionBusy='true';}
   show(text('処理中…','Working…'),true);
   return Promise.resolve(result).then(value=>{
    if(token===sequence){
     const changed=messages().filter(x=>x.textContent.trim()&&x.textContent!==before.get(x));
     show(changed.at(-1)?.textContent||text('処理が完了しました。','Action completed.'));
     timer=setTimeout(()=>{notice.hidden=true;},8000);
    }
    return value;
   },error=>{if(token===sequence)show(error.message||text('処理に失敗しました。','Action failed.'));throw error;}).finally(()=>{
    pending.delete(element);
    if(button){if(restoreEnabled)button.disabled=false;button.removeAttribute('aria-busy');delete button.dataset.actionBusy;}
   });
  };
  wrapped.feedbackWrapped=true;element[key]=wrapped;
 }
 // Capture also covers buttons created later in terminal/user lists.
 document.addEventListener('click',event=>{const button=event.target.closest('button');if(button)prepare(button,'onclick');},true);
 document.addEventListener('submit',event=>prepare(event.target,'onsubmit'),true);
 document.addEventListener('invalid',()=>show(text('入力内容を確認してください。必須項目や入力範囲をご確認ください。','Check required fields and input ranges.')),true);
})();
