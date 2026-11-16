(() => {
  const daily = document.querySelector('#flightPage');
  daily.append(...['flightsPanel','csvPanel','upstreamPanel'].map(id => document.getElementById(id)));
  if (document.currentScript.dataset.role !== 'admin') return;
  const heading = document.createElement('nav');
  heading.className = 'demo-flight-tabs';
  heading.setAttribute('aria-label', 'フライト情報の種類');
  heading.innerHTML = '<button type="button">日別フライト</button> <button type="button">シーズンダイヤ</button>';
  daily.before(heading);

  const panel = document.createElement('section');
  panel.className = 'manager-panel';
  panel.hidden = true;
  panel.innerHTML = `<h2>シーズンダイヤ</h2>
    <p>保存した変更はパラオ現地日付の次回の日次展開から反映されます。</p>
    <p id="seasonal-summary"></p>
    <div style="overflow-x:auto"><table aria-label="保存済みシーズンダイヤ">
      <thead><tr><th>便名</th><th>出発／到着</th><th>出発地</th><th>到着地</th><th>適用開始</th><th>適用終了</th><th>運航曜日</th><th>月内の運航週</th><th>定刻</th><th>操作</th></tr></thead>
      <tbody id="seasonal-schedules"></tbody>
    </table></div>
    <form hidden aria-label="シーズンダイヤ編集">
      <label>便名 <input name="flightNumber" required></label>
      <label>出発地 <input name="origin" maxlength="3" required></label>
      <label>到着地 <input name="destination" maxlength="3" required></label>
      <label>適用開始日 <input name="validFrom" type="date" required></label>
      <label>適用終了日 <input name="validTo" type="date" required></label>
      <label>運航曜日（1＝月曜、7＝日曜） <input name="operatingDays" pattern="[1-7]{1,7}" required></label>
      <label>月内の運航週（日曜始まり・空欄は毎週） <input name="weeksText" pattern="[1-6]{1,6}" placeholder="135"></label>
      <label>定刻 <input name="scheduledTime" type="time" required></label>
      <label>プレビュー運航日 <input name="serviceDate" type="date" required></label>
      <button type="submit" value="preview">プレビュー</button>
      <button type="submit" value="save">シーズンダイヤを保存</button>
    </form>
    <p role="status"></p>
    <table aria-label="運航日プレビュー"><thead><tr><th>便名</th><th>出発／到着</th><th>行先／出発地</th><th>定刻</th></tr></thead><tbody></tbody></table>`;
  heading.after(panel);
  const [dayButton, seasonButton] = heading.querySelectorAll('button');
  const form = panel.querySelector('form');
  const rows = panel.querySelector('#seasonal-schedules');
  let selectedId;
  const status = panel.querySelector('[role=status]');
  const preview = panel.querySelector('table[aria-label="運航日プレビュー"] tbody');
  let schedule;

  async function request(path, body) {
    const response = await fetch('/api/demo-seasonal' + path, body ? {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
    } : {});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    return data;
  }

  function selectFlight(flight) {
    selectedId = flight.id;
    form.hidden = false;
    for (const key of ['flightNumber','origin','destination','validFrom','validTo','scheduledTime']) {
      form.elements[key].value = flight[key];
    }
    form.elements.operatingDays.value = flight.operatingDays.join('');
    form.elements.weeksText.value = flight.weeksText || '';
    preview.replaceChildren();
  }

  async function load(keep = '') {
    schedule = null;
    rows.replaceChildren();
    selectedId = null;
    form.hidden = true;
    try {
      schedule = await request('');
      for (const flight of schedule.flights) {
        const row = rows.insertRow();
        const weekdays = flight.operatingDays.map(day => '月火水木金土日'[day-1]).join('・');
        const direction = flight.direction === 'arrival' ? '到着' : '出発';
        for (const value of [flight.flightNumber, direction, flight.origin, flight.destination,
                             flight.validFrom, flight.validTo, weekdays, flight.weeksText || (flight.validFrom===flight.validTo ? '日付指定' : '毎週'), flight.scheduledTime]) {
          row.insertCell().textContent = value;
        }
        const edit = document.createElement('button');
        edit.type = 'button';
        edit.textContent = '編集';
        edit.setAttribute('aria-label', flight.flightNumber + ' ' + flight.validFrom + ' ' + direction + 'を編集');
        edit.onclick = () => {
          status.textContent = '';
          selectFlight(flight);
          form.elements.flightNumber.focus();
        };
        const actions = row.insertCell();
        actions.append(edit);
        if (schedule.conflicts.includes(flight.id)) actions.append(' 競合あり');
      }
      if (!schedule.flights.length) rows.insertRow().insertCell().textContent = '保存済みの運航便はありません。';
      panel.querySelector('#seasonal-summary').textContent = schedule.source +
        ' · '+schedule.flights.length+'件 · 保存した変更の適用開始 ' + schedule.effective +
        (schedule.conflicts.length ? ' · 配信元との競合あり。現在の値を確認して保存してください。' : '');
      form.elements.serviceDate.min = schedule.effective;
      form.elements.serviceDate.max = schedule.coverage.to;
      if (!form.elements.serviceDate.value || form.elements.serviceDate.value < schedule.effective) {
        form.elements.serviceDate.value = schedule.effective;
      }
      const flight = schedule.flights.find(row => row.id === keep);
      if (flight) selectFlight(flight);
    } catch (error) {
      status.textContent = error.message;
    }
  }

  function selectTab(isSeasonal) {
    panel.hidden = !isSeasonal;
    daily.hidden = isSeasonal;
    dayButton.setAttribute('aria-pressed', String(!isSeasonal));
    seasonButton.setAttribute('aria-pressed', String(isSeasonal));
  }

  dayButton.onclick = () => selectTab(false);
  seasonButton.onclick = () => {
    selectTab(true);
    status.textContent = '';
    load();
  };
  function resetTabs() {
    panel.hidden = true;
    heading.hidden = Boolean(location.hash && location.hash !== '#flightsPanel');
    if (!heading.hidden) selectTab(false);
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
      const id = selectedId;
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
