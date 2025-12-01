(function(){
  function onFilter(){
    var q = (document.getElementById('dept-search')?.value || '').toLowerCase();
    var rows = document.querySelectorAll('table.admin-departments tbody tr');
    rows.forEach(function(tr){
      var nameCell = tr.querySelector('td');
      var name = (nameCell?.textContent || '').toLowerCase();
      tr.style.display = (!q || name.indexOf(q) !== -1) ? '' : 'none';
    });
  }
  document.addEventListener('DOMContentLoaded', function(){
    var inp = document.getElementById('dept-search');
    if(inp){ inp.addEventListener('keyup', onFilter); }
    
    // Double-submit protection for all forms with class 'admin-form-protect'
    var protectedForms = document.querySelectorAll('form.admin-form-protect');
    protectedForms.forEach(function(form){
      form.addEventListener('submit', function(e){
        var btn = form.querySelector('button[type="submit"]');
        if(btn && !btn.disabled){
          btn.disabled = true;
          var originalText = btn.textContent;
          btn.textContent = 'Bearbetar...';
          btn.dataset.originalText = originalText;
        }
      });
    });
    
    // Reload link handler (CSP-safe, no javascript: protocol)
    var reloadLinks = document.querySelectorAll('a.reload-link[data-action="reload"]');
    reloadLinks.forEach(function(link){
      link.addEventListener('click', function(e){
        e.preventDefault();
        location.reload();
      });
    });
  });
})();
