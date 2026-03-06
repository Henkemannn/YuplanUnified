(function () {
  function initReportWeeklyFilterAutosubmit() {
    var form = document.getElementById("report-weekly-filter-form");
    if (!form) {
      return;
    }

    var weekField = document.getElementById("week-select");
    var departmentField = document.getElementById("department-select");
    var yearField = document.getElementById("year-select");
    var isSubmitting = false;

    form.addEventListener("submit", function () {
      isSubmitting = true;
    });

    function readValue(el) {
      return String((el && el.value) || "").trim();
    }

    function maybeAutoSubmit(event) {
      if (isSubmitting) {
        return;
      }
      var field = event.currentTarget;
      if (!field) {
        return;
      }
      var current = readValue(field);
      var previous = field.dataset.lastValue;
      if (typeof previous === "string" && previous === current) {
        return;
      }
      field.dataset.lastValue = current;
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.submit();
      }
    }

    [weekField, departmentField, yearField].forEach(function (field) {
      if (!field) {
        return;
      }
      field.dataset.lastValue = readValue(field);
      field.addEventListener("change", maybeAutoSubmit);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initReportWeeklyFilterAutosubmit);
  } else {
    initReportWeeklyFilterAutosubmit();
  }
})();
