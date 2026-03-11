(function(){
  function $(sel, root){ return (root || document).querySelector(sel); }

  function init(){
    var addBtn = document.getElementById('service-addon-add-row');
    var body = document.getElementById('service-addon-body');
    if(!addBtn || !body) return;

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

    addBtn.addEventListener('click', function(){
      var first = body.querySelector('.service-addon-row');
      if(!first) return;
      var clone = first.cloneNode(true);
      clone.querySelectorAll('input').forEach(function(input){ input.value = ''; });
      clone.querySelectorAll('select').forEach(function(select){ select.selectedIndex = 0; });
      body.appendChild(clone);
      bindRemove(clone);
    });
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
