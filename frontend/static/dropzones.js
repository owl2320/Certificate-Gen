// Click-or-drop file pickers. Calls onChange() whenever a selection changes.
function initDropzones(onChange) {
  document.querySelectorAll('.drop').forEach(zone => {
    const input = document.getElementById(zone.dataset.for);
    const hint = zone.querySelector('.hint');
    const original = hint.textContent;

    const refresh = () => {
      const f = input.files[0];
      hint.textContent = f ? f.name : original;
      hint.className = f ? 'hint name' : 'hint';
      onChange();
    };

    input.addEventListener('change', refresh);
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('over'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('over');
      if (e.dataTransfer.files.length) { input.files = e.dataTransfer.files; refresh(); }
    });
  });
}