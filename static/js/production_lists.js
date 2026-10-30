document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-production-lists-week-form]");
  const yearSelect = form && form.querySelector("[data-production-lists-year]");
  const weekSelect = form && form.querySelector('select[name="week"]');
  if (!form || !yearSelect || !weekSelect) {
    return;
  }

  const navigate = () => {
    if (Number(weekSelect.value) > 52) {
      weekSelect.value = "1";
    }
    form.submit();
  };

  weekSelect.addEventListener("change", navigate);
  yearSelect.addEventListener("change", navigate);
});
