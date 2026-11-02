// Staff calendar: FullCalendar plus a details dialog with quick status changes.
document.addEventListener("DOMContentLoaded", function () {
  const el = document.getElementById("calendar");
  if (!el || typeof FullCalendar === "undefined") return;

  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const urlFor = (template, id) => template.replace(/0$/, String(id));
  const small = window.matchMedia("(max-width: 767.98px)").matches;

  const ACTIONS = {
    Pending: { label: "Set back to pending", cls: "btn-ghost" },
    Attended: { label: "Arrived", cls: "btn-primary" },
    "No Show": { label: "No show", cls: "btn-ghost" },
    Cancelled: { label: "Cancel booking", cls: "btn-ghost" },
  };

  const toggle = document.getElementById("show-cancelled");
  let showCancelled = false;
  try { showCancelled = localStorage.getItem("cal-show-cancelled") === "1"; } catch (e) {}
  toggle.checked = showCancelled;

  const calendar = new FullCalendar.Calendar(el, {
    locale: "en-GB",
    initialView: small ? "timeGridDay" : "timeGridWeek",
    firstDay: 1,
    height: "auto",
    slotMinTime: el.dataset.open + ":00",
    slotMaxTime: el.dataset.close + ":00",
    slotDuration: "00:15:00",
    slotLabelInterval: "01:00",
    allDaySlot: false,
    nowIndicator: true,
    expandRows: true,
    dayMaxEvents: 4,
    eventMinHeight: 22,
    headerToolbar: small
      ? { left: "prev,next", center: "title", right: "today" }
      : { left: "prev,next today", center: "title", right: "dayGridMonth,timeGridWeek,timeGridDay" },
    footerToolbar: small ? { center: "dayGridMonth,timeGridWeek,timeGridDay" } : false,
    buttonText: { today: "Today", month: "Month", week: "Week", day: "Day" },
    titleFormat: small ? { month: "short", day: "numeric" } : { year: "numeric", month: "short", day: "numeric" },
    dayHeaderFormat: { weekday: "short", day: "numeric" },
    slotLabelFormat: { hour: "numeric", hour12: true },
    eventTimeFormat: { hour: "numeric", minute: "2-digit", hour12: true },
    events(info, success, failure) {
      const params = new URLSearchParams({ start: info.startStr, end: info.endStr });
      fetch(`${el.dataset.events}?${params}`, { headers: { Accept: "application/json" } })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error("Couldn't load bookings."))))
        .then((events) => success(showCancelled ? events : events.filter((e) => e.extendedProps.status !== "Cancelled")))
        .catch(failure);
    },
    eventDidMount(info) {
      const p = info.event.extendedProps;
      info.el.title = `${p.plate}, ${p.carType}, ${p.washType} (${p.status})`;
    },
    eventClick(info) {
      info.jsEvent.preventDefault();
      openBooking(info.event);
    },
    dateClick(info) {
      if (info.view.type === "dayGridMonth") {
        calendar.changeView("timeGridDay", info.dateStr);
        return;
      }
      const d = info.date;
      const pad = (n) => String(n).padStart(2, "0");
      const params = new URLSearchParams({
        date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
        time: `${pad(d.getHours())}:${pad(d.getMinutes())}`,
        next: window.location.pathname,
      });
      window.location.href = `${el.dataset.addUrl}?${params}`;
    },
  });
  calendar.render();

  toggle.addEventListener("change", () => {
    showCancelled = toggle.checked;
    try { localStorage.setItem("cal-show-cancelled", showCancelled ? "1" : "0"); } catch (e) {}
    calendar.refetchEvents();
  });

  // ----- details dialog -----
  const modalEl = document.getElementById("booking-modal");
  const modal = new bootstrap.Modal(modalEl);
  const f = (name) => modalEl.querySelector(`[data-f="${name}"]`);
  let current = null;

  function statusBadge(status, key) {
    const span = document.createElement("span");
    span.className = `status status-${key}`;
    span.textContent = status;
    return span;
  }

  function render(event) {
    const p = event.extendedProps;
    f("plate").textContent = p.plate;
    f("when").textContent = p.when;
    f("wash").textContent = `${p.washType}, ${p.carType}`;
    f("customer").textContent = p.name;
    f("phone").textContent = p.contact;
    f("phone").href = `tel:+673${p.contact}`;
    f("status").replaceChildren(statusBadge(p.status, p.statusKey));
    f("edit").href = `${urlFor(el.dataset.editUrl, event.id)}?next=${encodeURIComponent(window.location.pathname)}`;
    f("error").hidden = true;

    const box = f("actions");
    box.replaceChildren();
    Object.entries(ACTIONS).forEach(([status, cfg]) => {
      if (status === p.status) return;
      if (p.status === "Pending" && status === "Pending") return;
      const b = document.createElement("button");
      b.type = "button";
      b.className = `btn btn-sm ${cfg.cls}`;
      b.textContent = cfg.label;
      b.addEventListener("click", () => setStatus(event, status, b));
      box.appendChild(b);
    });
  }

  function openBooking(event) {
    current = event;
    render(event);
    modal.show();
  }

  async function setStatus(event, status, button) {
    button.disabled = true;
    try {
      const res = await fetch(urlFor(el.dataset.statusUrl, event.id), {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ status }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) throw new Error(data.message || "Couldn't change the status.");
      const e = data.event;
      event.setProp("classNames", e.classNames);
      Object.entries(e.extendedProps).forEach(([k, v]) => event.setExtendedProp(k, v));
      render(event);
    } catch (err) {
      f("error").textContent = err.message;
      f("error").hidden = false;
      button.disabled = false;
    }
  }

  modalEl.addEventListener("hidden.bs.modal", () => { current = null; });
});
