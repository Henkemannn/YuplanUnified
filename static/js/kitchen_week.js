(function(){
  'use strict';

  function init(){
    var buttons = document.querySelectorAll('.kostcell-btn');
    buttons.forEach(function(btn){
      btn.addEventListener('click', function(){
        var week = parseInt(this.getAttribute('data-week'), 10);
        var dayIndex = parseInt(this.getAttribute('data-day-index'), 10);
        var meal = this.getAttribute('data-meal');
        var deptId = this.getAttribute('data-department-id');
        var kosttypId = this.getAttribute('data-kosttyp-id');
        if(!week || !dayIndex || !meal || !deptId || !kosttypId){
          return;
        }
        var isDone = this.classList.contains('done-ring');
        var desired = !isDone;
        var payload = {
          year: parseInt(document.querySelector('main.portal-container')?.getAttribute('data-year') || '0', 10),
          week: week,
          department_id: deptId,
          day_index: dayIndex,
          meal: meal,
          kosttyp_id: kosttypId,
          done: desired
        };
        fetch('/ui/kitchen/week/toggle_done', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
          body: JSON.stringify(payload)
        }).then(function(resp){
          if(resp.ok){
            // Toggle UI ring
            if(desired){
              btn.classList.add('done-ring');
              btn.style.outline = '3px solid #2ecc71';
              btn.style.outlineOffset = '0';
            } else {
              btn.classList.remove('done-ring');
              btn.style.outline = '';
              btn.style.outlineOffset = '';
            }
          }
        }).catch(function(){ /* no-op */ });
      });
    });
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
