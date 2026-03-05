(function(){
  function initMenuImportUpload(){
    var input = document.getElementById('menu_file');
    var label = document.getElementById('menu-file-name');
    var submit = document.getElementById('menu-import-submit');
    if(!input || !label || !submit) return;

    function syncUploadState(){
      var hasFile = !!(input.files && input.files[0]);
      label.textContent = hasFile ? input.files[0].name : 'Ingen fil vald';
      submit.disabled = !hasFile;
    }

    syncUploadState();
    input.addEventListener('change', syncUploadState);
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', initMenuImportUpload);
  } else {
    initMenuImportUpload();
  }
})();
