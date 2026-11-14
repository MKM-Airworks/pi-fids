const buttons = [...document.querySelectorAll('button[data-mode]')];
for (const button of buttons) button.onclick = async () => {
  for (const b of buttons) b.disabled = true;
  const result = document.querySelector('#result');
  result.textContent = '切替中…';
  try {
    const response = await fetch('/api/demo-mode', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify({mode:button.dataset.mode})});
    result.textContent = response.ok ? button.textContent + 'へ切り替えました。' : '切替できません。管理者でログインしてください。';
  } catch { result.textContent = '接続できません。'; }
  finally { for (const b of buttons) b.disabled = false; }
};
