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

  function resolveFilterScope(root){
    if(qsa('[data-specialkost-group]', root).length){
      return root;
    }
    var node = root.parentElement;
    while(node){
      if(qsa('[data-specialkost-group]', node).length){
        return node;
      }
      node = node.parentElement;
    }
    return root;
  }

  function setOpenIfClosed(detailsEl){
    if(detailsEl && detailsEl.tagName === 'DETAILS' && !detailsEl.hasAttribute('open')){
      detailsEl.setAttribute('open', 'open');
    }
  }

  function isOpen(detailsEl){
    return detailsEl && detailsEl.tagName === 'DETAILS' && detailsEl.hasAttribute('open');
  }

  function setOpenState(detailsEl, open){
    if(!detailsEl || detailsEl.tagName !== 'DETAILS'){
      return;
    }
    if(open){
      detailsEl.setAttribute('open', 'open');
    } else {
      detailsEl.removeAttribute('open');
    }
  }

  function getDetailsNodes(scope){
    var groups = qsa('[data-specialkost-group]', scope);
    var subgroups = qsa('[data-specialkost-subgroup]', scope);
    return groups.concat(subgroups);
  }

  function captureDetailsState(scope){
    var state = [];
    getDetailsNodes(scope).forEach(function(detailsEl){
      state.push({
        node: detailsEl,
        open: isOpen(detailsEl)
      });
    });
    return state;
  }

  function restoreDetailsState(snapshot){
    (snapshot || []).forEach(function(entry){
      if(!entry || !entry.node){
        return;
      }
      setOpenState(entry.node, !!entry.open);
    });
  }

  function applyFilter(root, query){
    var groups = qsa('[data-specialkost-group]', root);
    var anyVisible = false;
    groups.forEach(function(group){
      var groupVisibleCount = 0;

      var subgroups = qsa('[data-specialkost-subgroup]', group);
      if(subgroups.length){
        subgroups.forEach(function(subgroup){
          var subgroupVisibleCount = 0;
          var subgroupItems = qsa('[data-specialkost-item]', subgroup);

          subgroupItems.forEach(function(item){
            var visible = !query || itemLabel(item).indexOf(query) !== -1;
            item.style.display = visible ? '' : 'none';
            if(visible){ subgroupVisibleCount += 1; }
          });

          var subgroupVisible = subgroupVisibleCount > 0;
          subgroup.style.display = subgroupVisible ? '' : 'none';
          if(subgroupVisible){
            groupVisibleCount += subgroupVisibleCount;
            setOpenIfClosed(subgroup);
          }
        });
      } else {
        var items = qsa('[data-specialkost-item]', group);
        items.forEach(function(item){
          var visible = !query || itemLabel(item).indexOf(query) !== -1;
          item.style.display = visible ? '' : 'none';
          if(visible){ groupVisibleCount += 1; }
        });
      }

      var groupVisible = groupVisibleCount > 0;
      group.style.display = groupVisible ? '' : 'none';
      if(groupVisible){
        anyVisible = true;
        setOpenIfClosed(group);
      }
    });

    root.setAttribute('data-specialkost-filter-empty', anyVisible ? '0' : '1');
  }

  function initRoot(root){
    var input = root.querySelector('[data-specialkost-filter-input]');
    if(!input){ return; }

    var scope = resolveFilterScope(root);
    var searchState = {
      active: false,
      snapshot: null
    };

    applyFilter(scope, normalize(input.value));

    input.addEventListener('input', function(){
      var query = normalize(input.value);
      var hasQuery = !!query;

      if(hasQuery && !searchState.active){
        searchState.snapshot = captureDetailsState(scope);
        searchState.active = true;
      }

      applyFilter(scope, query);

      if(!hasQuery && searchState.active){
        restoreDetailsState(searchState.snapshot);
        searchState.snapshot = null;
        searchState.active = false;
      }
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
