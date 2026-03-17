(function(){
  function $(sel, root){ return (root || document).querySelector(sel); }

  function init(){
    var addBtn = document.getElementById('service-addon-add-row');
    var body = document.getElementById('service-addon-body');
    if(!addBtn || !body) return;

    function syncCreateState(row){
      if(!row) return;
      var wrap = row.querySelector('.service-addon-new-wrap');
      var input = row.querySelector('.service-addon-new');
      var toggle = row.querySelector('.js-service-addon-create-toggle');
      if(!wrap || !toggle) return;
      var visible = wrap.classList.contains('is-visible') || !!(input && String(input.value || '').trim());
      wrap.classList.toggle('is-visible', visible);
      toggle.textContent = visible ? 'Dolj nytt tillagg' : '+ Skapa nytt tillagg';
    }

    function bindCreateToggle(scope){
      var buttons = (scope || document).querySelectorAll('.js-service-addon-create-toggle');
      buttons.forEach(function(btn){
        if(btn.dataset.createBound === '1') return;
        btn.dataset.createBound = '1';
        btn.addEventListener('click', function(){
          var row = btn.closest('.service-addon-row');
          if(!row) return;
          var wrap = row.querySelector('.service-addon-new-wrap');
          if(!wrap) return;
          var willShow = !wrap.classList.contains('is-visible');
          wrap.classList.toggle('is-visible', willShow);
          syncCreateState(row);
          if(willShow){
            var input = row.querySelector('.service-addon-new');
            if(input && typeof input.focus === 'function'){
              input.focus();
            }
          }
        });
      });
      var rows = (scope || document).querySelectorAll('.service-addon-row');
      rows.forEach(syncCreateState);
    }

    function bindRemove(scope){
      var buttons = (scope || document).querySelectorAll('.js-service-addon-remove');
      buttons.forEach(function(btn){
        if(btn.dataset.bound === '1') return;
        btn.dataset.bound = '1';
        btn.addEventListener('click', function(){
          var row = btn.closest('.service-addon-row');
          if(!row) return;
          row.remove();
          if(!body.querySelector('.service-addon-row')){
            addBtn.click();
          }
        });
      });
    }

    bindRemove(body);
    bindCreateToggle(body);

    addBtn.addEventListener('click', function(){
      var first = body.querySelector('.service-addon-row');
      if(!first) return;
      var clone = first.cloneNode(true);
      clone.querySelectorAll('input').forEach(function(input){ input.value = ''; });
      clone.querySelectorAll('select').forEach(function(select){
        if(select.name === 'service_addon_family[]'){
          var found = false;
          for(var i=0; i<select.options.length; i++){
            if(String(select.options[i].value || '') === 'ovrigt'){
              select.selectedIndex = i;
              found = true;
              break;
            }
          }
          if(!found){ select.selectedIndex = 0; }
          return;
        }
        select.selectedIndex = 0;
      });
      var wrap = clone.querySelector('.service-addon-new-wrap');
      if(wrap){ wrap.classList.remove('is-visible'); }
      body.appendChild(clone);
      bindRemove(clone);
      bindCreateToggle(clone);
    });
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
