(function(){
  function init(){
    var btn = document.querySelector('.js-print-snapshot');
    if(!btn){ return; }
    btn.addEventListener('click', function(){ window.print(); });
  }
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
