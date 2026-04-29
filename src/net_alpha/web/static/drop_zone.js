// Drop-zone preview (§6.2 I4). Vanilla JS, no Alpine — runs on every page
// that includes <input type="file" data-drop-zone> with a sibling
// data-testid="drop-zone-preview" element.
(function() {
  function init() {
    document.querySelectorAll('[data-drop-zone]').forEach(function(zone) {
      const preview = zone.parentElement.querySelector('[data-testid="drop-zone-preview"]');
      if (!preview) return;

      ['dragenter', 'dragover'].forEach(function(evt) {
        zone.parentElement.addEventListener(evt, function(e) {
          e.preventDefault();
          if (!e.dataTransfer) return;
          const files = Array.from(e.dataTransfer.items || [])
            .filter(function(item) { return item.kind === 'file'; });
          preview.textContent = files.length
            ? files.length + ' file' + (files.length === 1 ? '' : 's') + ' ready to drop'
            : '';
          preview.classList.remove('hidden');
        });
      });

      ['dragleave', 'drop'].forEach(function(evt) {
        zone.parentElement.addEventListener(evt, function() {
          preview.textContent = '';
          preview.classList.add('hidden');
        });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
