(function () {
  function readJson(id, fallback) {
    var node = document.getElementById(id);
    if (!node || !node.textContent) return fallback;
    try {
      return JSON.parse(node.textContent);
    } catch (_err) {
      return fallback;
    }
  }

  var picker = document.querySelector('.menu-week-picker');
  if (!picker) return;

  var prevBtn = picker.querySelector('.js-week-prev');
  var nextBtn = picker.querySelector('.js-week-next');
  var toggleBtn = picker.querySelector('.js-week-dropdown-toggle');
  var dropdown = picker.querySelector('.js-week-dropdown');

  var availableWeeks = readJson('js-available-weeks', []);
  var currentWeekKey = readJson('js-current-week-key', '');
  var params = new URLSearchParams(window.location.search);
  var keepEdit = params.get('edit') === '1';

  if (!Array.isArray(availableWeeks) || availableWeeks.length === 0) {
    if (prevBtn) prevBtn.disabled = true;
    if (nextBtn) nextBtn.disabled = true;
    return;
  }

  function withOptionalEdit(url) {
    try {
      var target = new URL(url, window.location.origin);
      if (keepEdit) {
        target.searchParams.set('edit', '1');
      }
      return target.pathname + target.search;
    } catch (_err) {
      return url;
    }
  }

  function navigate(url) {
    if (!url) return;
    window.location.assign(withOptionalEdit(url));
  }

  function weekKey(item) {
    return String(item.year) + '-' + String(item.week);
  }

  var currentIndex = availableWeeks.findIndex(function (item) {
    return weekKey(item) === String(currentWeekKey);
  });
  if (currentIndex < 0) {
    currentIndex = availableWeeks.findIndex(function (item) {
      return Number(item.year) === Number(params.get('year')) && Number(item.week) === Number(params.get('week'));
    });
  }

  if (prevBtn) {
    prevBtn.disabled = currentIndex <= 0;
    prevBtn.addEventListener('click', function () {
      if (currentIndex <= 0) return;
      navigate(availableWeeks[currentIndex - 1].url);
    });
  }

  if (nextBtn) {
    nextBtn.disabled = currentIndex < 0 || currentIndex >= availableWeeks.length - 1;
    nextBtn.addEventListener('click', function () {
      if (currentIndex < 0 || currentIndex >= availableWeeks.length - 1) return;
      navigate(availableWeeks[currentIndex + 1].url);
    });
  }

  function closeDropdown() {
    if (!dropdown || dropdown.hidden) return;
    dropdown.hidden = true;
    if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'false');
  }

  function openDropdown() {
    if (!dropdown) return;
    dropdown.hidden = false;
    if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'true');
  }

  if (toggleBtn && dropdown) {
    toggleBtn.addEventListener('click', function () {
      if (dropdown.hidden) {
        openDropdown();
      } else {
        closeDropdown();
      }
    });

    dropdown.addEventListener('click', function (event) {
      var item = event.target.closest('.menu-week-picker__item');
      if (!item) return;
      var url = item.getAttribute('data-url') || item.getAttribute('href');
      event.preventDefault();
      closeDropdown();
      navigate(url);
    });

    document.addEventListener('click', function (event) {
      if (!picker.contains(event.target)) {
        closeDropdown();
      }
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        closeDropdown();
      }
    });
  }
})();
