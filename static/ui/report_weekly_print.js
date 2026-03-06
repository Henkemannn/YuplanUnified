(function () {
  function qsa(sel) {
    return Array.prototype.slice.call(document.querySelectorAll(sel));
  }

  function setupReportWeeklyPrint() {
    var root = document.querySelector('[data-testid="report-weekly"]');
    if (!root) {
      return;
    }

    var detailsEls = qsa('.admin-report-week__details');
    var btn = document.querySelector('.js-report-weekly-print');
    var wasOpen = [];

    function openAllDetails() {
      wasOpen = detailsEls.map(function (el) {
        return !!el.open;
      });
      detailsEls.forEach(function (el) {
        el.open = true;
      });
    }

    function restoreDetails() {
      if (!wasOpen.length) {
        return;
      }
      detailsEls.forEach(function (el, idx) {
        el.open = !!wasOpen[idx];
      });
      wasOpen = [];
    }

    if (btn) {
      btn.addEventListener('click', function () {
        openAllDetails();
        if (window && typeof window.requestAnimationFrame === 'function') {
          window.requestAnimationFrame(function () {
            window.print();
          });
        } else {
          window.print();
        }
      });
    }

    window.addEventListener('beforeprint', openAllDetails);
    window.addEventListener('afterprint', restoreDetails);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupReportWeeklyPrint);
  } else {
    setupReportWeeklyPrint();
  }
})();
