// Page flow: upload -> pick columns -> generate -> download.
const $ = id => document.getElementById(id);
let sid = null, timer = null;

const say = (text, cls = '') => { $('msg').textContent = text; $('msg').className = cls; };
const lock = (id, locked) => $(id).classList.toggle('locked', locked);

initDropzones(() => { $('load').disabled = !($('data').files[0] && $('tpl').files[0]); });

$('load').onclick = async () => {
  $('load').disabled = true;
  $('load').textContent = 'Reading…';
  try {
    const info = await api.createSession($('data').files[0], $('tpl').files[0], $('bijoy').checked);
    sid = info.session_id;
    renderColumns(info);
    lock('s1', true); lock('s2', false); lock('s3', false);
    say('');
  } catch (e) {
    alert('Could not read files: ' + e.message);
    $('load').disabled = false;
  }
  $('load').textContent = 'Read columns';
};

$('gen').onclick = async () => {
  const columns = readSelectedColumns();
  if (!Object.keys(columns).length) return say('Select at least one column.', 'err');
  $('gen').disabled = true; $('dl').hidden = true; $('fill').style.width = '0';
  try {
    await api.generate(sid, columns, $('merge').checked);
    say('Starting…');
    timer = setInterval(poll, 400);
  } catch (e) { say(e.message, 'err'); $('gen').disabled = false; }
};

async function poll() {
  try {
    const p = await api.progress(sid);
    $('fill').style.width = p.percent + '%';
    if (p.status === 'running') say(`${p.done}/${p.total} certificates generated`);
    if (p.status === 'done') {
      clearInterval(timer);
      say(`Done. ${p.total} certificates ready.`, 'ok');
      $('dl').hidden = false; $('reset').hidden = false; $('gen').disabled = false;
    }
    if (p.status === 'error') {
      clearInterval(timer);
      say(p.error, 'err');
      $('gen').disabled = false; $('reset').hidden = false;
    }
  } catch (e) { clearInterval(timer); say(e.message, 'err'); $('gen').disabled = false; }
}

$('dl').onclick = () => { location.href = api.downloadUrl(sid); };

$('reset').onclick = () => {
  clearInterval(timer);
  if (sid) api.remove(sid).catch(() => {});
  sid = null;
  ['data', 'tpl'].forEach(id => { $(id).value = ''; $(id).dispatchEvent(new Event('change')); });
  lock('s1', false); lock('s2', true); lock('s3', true);
  $('dl').hidden = true; $('reset').hidden = true; $('fill').style.width = '0';
  say('');
};