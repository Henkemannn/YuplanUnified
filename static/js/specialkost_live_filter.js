(function(){
  function qsa(sel, root){
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  function normalize(text){
    return String(text || '').toLowerCase().trim();
  }

  function itemLabel(item){
    var named = item.querySelector('[data-specialkost-name]');
    if(named){
      return normalize(named.textContent || '');
    }
    return normalize(item.textContent || '');
  }

  function applyFilter(root, query){
    var groups = qsa('[data-specialkost-group]', root);
    var anyVisible = false;
    groups.forEach(function(group){
      var items = qsa('[data-specialkost-item]', group);
      var groupVisibleCount = 0;

      items.forEach(function(item){
        var visible = !query || itemLabel(item).indexOf(query) !== -1;
        item.style.display = visible ? '' : 'none';
        if(visible){ groupVisibleCount += 1; }
      });

      var groupVisible = groupVisibleCount > 0;
      group.style.display = groupVisible ? '' : 'none';
      if(groupVisible){
        anyVisible = true;
        if(!group.hasAttribute('open')){
          group.setAttribute('open', 'open');
        }
      }
    });

    root.setAttribute('data-specialkost-filter-empty', anyVisible ? '0' : '1');
  }

  function initRoot(root){
    var input = root.querySelector('[data-specialkost-filter-input]');
    if(!input){ return; }

    applyFilter(root, normalize(input.value));

    input.addEventListener('input', function(){
      applyFilter(root, normalize(input.value));
    });
  }

  function init(){
    qsa('[data-specialkost-filter-root]').forEach(initRoot);
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
