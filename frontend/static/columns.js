// Column picker: build the list from the API response, read back {original: newName}.
function renderColumns(info) {
  document.getElementById('rows').textContent =
    `${info.row_count} rows found in ${info.columns.length} columns.`;
  const box = document.getElementById('cols');
  box.innerHTML = '';

  info.columns.forEach(name => {
    const row = document.createElement('div');
    row.className = 'col';

    const cb = document.createElement('input');
    cb.type = 'checkbox'; cb.checked = true; cb.dataset.col = name;

    const label = document.createElement('div');
    label.className = 'n';
    label.textContent = name;
    const sample = document.createElement('small');
    sample.textContent = info.preview[0]?.[name] ?? '';
    label.append(sample);

    const rename = document.createElement('input');
    rename.type = 'text'; rename.placeholder = 'Rename column';
    rename.setAttribute('aria-label', 'New name for ' + name);

    row.append(cb, label, rename);
    box.append(row);
  });
}

function readSelectedColumns() {
  const columns = {};
  document.querySelectorAll('#cols .col').forEach(row => {
    const cb = row.querySelector('input[type=checkbox]');
    if (cb.checked) {
      columns[cb.dataset.col] = row.querySelector('input[type=text]').value.trim() || cb.dataset.col;
    }
  });
  return columns;
}