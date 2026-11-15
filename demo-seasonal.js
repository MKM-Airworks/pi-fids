(() => {
  const daily = document.querySelector('#flightPage');
  const heading = document.createElement('nav');
  heading.className = 'form-actions';
  heading.setAttribute('aria-label', 'フライト情報の種類');
  heading.innerHTML = '<button type="button">日別フライト</button> <button type="button">シーズンダイヤ</button>';
  daily.before(heading);

  const panel = document.createElement('section');
  panel.className = 'manager-panel';
  panel.hidden = true;
  panel.innerHTML = `<h2>シーズンダイヤ</h2>
    <p>保存した変更はパラオ現地日付の次回の日次展開から反映されます。</p>
    <p id="seasonal-summary"></p>
    <label>対象便 <select name="schedule"></select></label>
    <form>
      <label>便名 <input name="flightNumber" required></label>
      <label>出発地 <input name="origin" maxlength="3" required></label>
      <label>到着地 <input name="destination" maxlength="3" required></label>
      <label>適用開始日 <input name="validFrom" type="date" required></label>
      <label>適用終了日 <input name="validTo" type="date" required></label>
      <label>運航曜日（1＝月曜、7＝日曜） <input name="operatingDays" pattern="[1-7]{1,7}" required></label>
      <label>定刻 <input name="scheduledTime" type="time" required></label>
      <label>プレビュー運航日 <input name="serviceDate" type="date" required></label>
      <button type="submit" value="preview">プレビュー</button>
      <button type="submit" value="save">シーズンダイヤを保存</button>
    </form>
    <p role="status"></p>
    <table><thead><tr><th>便名</th><th>出発／到着</th><th>行先／出発地</th><th>定刻</th></tr></thead><tbody></tbody></table>`;
  heading.after(panel);
  const [dayButton, seasonButton] = heading.querySelectorAll('button');
  const form = panel.querySelector('form');
  const select = panel.querySelector('select');
  const status = panel.querySelector('[role=status]');
  const preview = panel.querySelector('tbody');
  let schedule;

  async function request(path, body) {
    const response = await fetch('/api/demo-seasonal' + path, body ? {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
    } : {});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    return data;
  }

  function selectFlight() {
    const flight = schedule.flights.find(row => row.id === select.value);
    if (!flight) return;
    for (const key of ['flightNumber','origin','destination','validFrom','validTo','scheduledTime']) {
      form.elements[key].value = flight[key];
    }
    form.elements.operatingDays.value = flight.operatingDays.join('');
    preview.replaceChildren();
  }

  async function load(keep = '') {
    schedule = null;
    select.replaceChildren();
    form.hidden = true;
    try {
      schedule = await request('');
      for (const flight of schedule.flights) {
        const warning = schedule.conflicts.includes(flight.id) ? ' · 競合あり' : '';
        select.add(new Option(flight.flightNumber + ' · ' + flight.validFrom + ' · ' +
          (flight.direction === 'arrival' ? '到着' : '出発') + warning, flight.id));
      }
      panel.querySelector('#seasonal-summary').textContent = schedule.source +
        ' · 保存した変更の適用開始 ' + schedule.effective +
        (schedule.conflicts.length ? ' · 配信元との競合あり。現在の値を確認して保存してください。' : '');
      if (keep && schedule.flights.some(row => row.id === keep)) select.value = keep;
      form.hidden = !schedule.flights.length;
      form.elements.serviceDate.min = schedule.effective;
      form.elements.serviceDate.max = schedule.coverage.to;
      if (!form.elements.serviceDate.value || form.elements.serviceDate.value < schedule.effective) {
        form.elements.serviceDate.value = schedule.effective;
      }
      selectFlight();
    } catch (error) {
      status.textContent = error.message;
    }
  }

  dayButton.onclick = () => { panel.hidden = true; daily.hidden = false; };
  seasonButton.onclick = () => { daily.hidden = true; panel.hidden = false; status.textContent = ''; load(); };
  select.onchange = selectFlight;
  function resetTabs() {
    panel.hidden = true;
    heading.hidden = Boolean(location.hash && location.hash !== '#flightsPanel');
  }
  addEventListener('hashchange', resetTabs);
  resetTabs();
  form.onsubmit = async event => {
    event.preventDefault();
    if (!schedule) return;
    const values = Object.fromEntries(new FormData(form));
    const {serviceDate, ...fields} = values;
    fields.operatingDays = Array.from(fields.operatingDays, Number).sort();
    const buttons = [...form.querySelectorAll('button')];
    buttons.forEach(button => { button.disabled = true; });
    status.textContent = '';
    try {
      const action = event.submitter.value;
      const id = select.value;
      const result = await request('/' + action, {id, revision:schedule.revision, fields, serviceDate});
      if (action === 'save') await load(id);
      preview.replaceChildren();
      for (const flight of result.flights) {
        const row = preview.insertRow();
        for (const cell of [flight.flightNumber, flight.direction === 'arrival' ? '到着' : '出発',
                            flight.destination, flight.time]) row.insertCell().textContent = cell;
      }
      status.textContent = (action === 'save' ? '保存しました。適用開始 ' + result.effective + '。 ' : '') +
        serviceDate + ' のプレビュー · ' + result.flights.length + '便';
    } catch (error) {
      status.textContent = error.message;
    } finally {
      buttons.forEach(button => { button.disabled = false; });
    }
  };
})();
