// Customer booking page: refresh free times, keep wash durations and the summary in sync.
(function () {
  const form = document.getElementById("booking-form");
  if (!form) return;

  const slotsEl = document.getElementById("slots");
  const washBox = form.querySelector(".wash-options");
  const durations = JSON.parse(washBox.dataset.durations);

  const checked = (name) => form.querySelector(`[name="${name}"]:checked`);
  const fmt = (mins) => {
    const h = Math.floor(mins / 60), m = mins % 60;
    if (h && m) return `${h} h ${m} min`;
    return h ? `${h} h` : `${m} min`;
  };
  const sum = (key) => document.querySelector(`[data-sum="${key}"]`);
  const setSum = (key, text, empty) => {
    const el = sum(key);
    if (!el) return;
    el.textContent = text;
    el.classList.toggle("is-empty", !!empty);
  };

  function updateDurations() {
    const car = checked("car_type")?.value || "Sedan";
    form.querySelectorAll(".wash-time").forEach((el) => {
      el.textContent = fmt(durations[car][el.dataset.wash]);
    });
  }

  function updateSummary() {
    const car = checked("car_type")?.value;
    const wash = checked("wash_type")?.value;
    const plate = form.querySelector("#car_plate").value.trim().toUpperCase().replace(/\s+/g, " ");
    setSum("plate", plate || "YOUR PLATE");
    setSum("car", car || "");
    setSum("wash", wash || "");
    if (car && wash) setSum("duration", fmt(durations[car][wash]));
    setSum("day", checked("date")?.dataset.label || "");
    const time = checked("time");
    setSum("time", time ? time.dataset.label : "Pick a time", !time);
  }

  // Changing the car, wash or day changes which times are free.
  form.addEventListener("change", (e) => {
    if (e.target.matches("[data-refresh-slots]")) {
      if (e.target.name === "car_type") updateDurations();
      htmx.trigger(slotsEl, "refresh");
    }
    updateSummary();
  });
  form.querySelector("#car_plate").addEventListener("input", updateSummary);
  slotsEl.addEventListener("htmx:afterSwap", updateSummary);

  // Keep the chosen day in view in the scrolling strip.
  const day = checked("date");
  if (day) day.nextElementSibling.scrollIntoView({ block: "nearest", inline: "center" });

  // Bring the first problem into view after a failed submit.
  const firstError = document.querySelector(".field-error");
  if (firstError) firstError.closest(".step")?.scrollIntoView({ block: "start" });

  form.addEventListener("submit", (e) => {
    if (!checked("time")) {
      e.preventDefault();
      let msg = slotsEl.parentElement.querySelector(".js-time-error");
      if (!msg) {
        msg = document.createElement("div");
        msg.className = "field-error js-time-error";
        slotsEl.after(msg);
      }
      msg.textContent = "Pick a time.";
      slotsEl.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  });
  slotsEl.addEventListener("change", () => slotsEl.parentElement.querySelector(".js-time-error")?.remove());
})();
