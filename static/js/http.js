// Minimal fetch wrapper injecting CSRF token if present in <meta name="csrf-token">
(function(){
  function csrfToken(){
    var m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : null;
  }
  var origFetch = window.fetch;
  window.fetch = function(input, init){
    init = init || {};
    init.headers = init.headers || {};
    var method = (init.method || 'GET').toUpperCase();
    if(['POST','PUT','PATCH','DELETE'].indexOf(method) !== -1){
      var tok = csrfToken();
      if(tok){
        if(init.headers instanceof Headers){
            init.headers.set('X-CSRF-Token', tok);
        } else if (Array.isArray(init.headers)) {
            init.headers.push(['X-CSRF-Token', tok]);
        } else {
            init.headers['X-CSRF-Token'] = tok;
        }
      }
    }
    return origFetch(input, init);
  };
})();
