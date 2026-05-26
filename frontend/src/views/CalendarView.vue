<script setup>
import { ref, computed, onMounted, reactive, watch, watchEffect } from "vue"
import FullCalendar from "@fullcalendar/vue3"
import dayGridPlugin from "@fullcalendar/daygrid"
import timeGridPlugin from "@fullcalendar/timegrid"
import interactionPlugin from "@fullcalendar/interaction"
import multiMonthPlugin from "@fullcalendar/multimonth"
import listPlugin from "@fullcalendar/list"
import { calendarApi, timetableApi, notificationApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"
import { useAuthStore } from "@/stores/auth"

const toast = useToast()
const auth = useAuthStore()
const calendarRef = ref(null)

// ── Data ───────────────────────────────────────────────────────────────────────
const academicEvents = ref([])
const publicHolidays = ref([])
const timetableList = ref([])
// entries per timetable id: { [id]: TimetableEntry[] }
const timetableEntriesMap = ref({})
// which timetables are checked on in the sidebar
const enabledTimetables = ref(new Set())
const semesters = ref([])
const loading = ref(true)
const holidaysLoading = ref(false)
const institutionalHolidays = ref([])
const showInstitutionalHolidays = ref(true)
const showSemesterBreaks = ref(true)

// Overlay toggles
const showTimetableSessions = ref(true)
const showHolidays = ref(true)
const countryCode = ref("TZ")          // Tanzania default
const currentYear = new Date().getFullYear()

// Event type config
const EVENT_TYPES = {
  event:        { label: "Event",        color: "#10B981" },
  exam:         { label: "Exam",         color: "#F97316" },
  holiday:      { label: "Holiday",      color: "#EF4444" },
  deadline:     { label: "Deadline",     color: "#EAB308" },
  class:        { label: "Class",        color: "#3B82F6" },
  meeting:      { label: "Meeting",      color: "#8B5CF6" },
  announcement: { label: "Announcement", color: "#6B7280" },
  makeup:       { label: "Make-up",      color: "#EC4899" },
  semester_break:{ label: "Sem Break",   color: "#14B8A6" },
}
const activeFilters = ref(new Set(Object.keys(EVENT_TYPES)))

// Day of week map (FullCalendar: 0=Sun, 1=Mon … 6=Sat — matches JS getDay())
const DAY_MAP = { Monday: 1, Tuesday: 2, Wednesday: 3, Thursday: 4, Friday: 5, Saturday: 6, Sunday: 0 }

// African + common countries
const COUNTRIES = [
  { code: "TZ", name: "Tanzania" }, { code: "KE", name: "Kenya" },
  { code: "UG", name: "Uganda" },   { code: "NG", name: "Nigeria" },
  { code: "ZA", name: "South Africa" }, { code: "GH", name: "Ghana" },
  { code: "ET", name: "Ethiopia" }, { code: "MA", name: "Morocco" },
  { code: "EG", name: "Egypt" },    { code: "RW", name: "Rwanda" },
  { code: "GB", name: "United Kingdom" }, { code: "US", name: "United States" },
  { code: "IN", name: "India" },
]

// ── Modals ─────────────────────────────────────────────────────────────────────
const showCreateModal    = ref(false)
const showEditModal      = ref(false)
const showDetailModal    = ref(false)
const showSemesterModal  = ref(false)
const showAllEventsModal = ref(false)
const showSidebar        = ref(true)
const selectedEvent      = ref(null)
const showReminderForm   = ref(false)
const showCancelForm     = ref(false)
const saving             = ref(false)
const updating           = ref(false)
const sendingReminder    = ref(false)
const deleting           = ref(false)
const cancelling         = ref(false)

// ── All Events list state ──────────────────────────────────────────────────────
const eventsSearch    = ref("")
const eventsTypeFilter = ref("all")
const deletingId      = ref(null)

const filteredEvents = computed(() => {
  let list = [...academicEvents.value]
  if (eventsTypeFilter.value !== "all") list = list.filter(e => e.event_type === eventsTypeFilter.value)
  if (eventsSearch.value.trim()) {
    const q = eventsSearch.value.toLowerCase()
    list = list.filter(e => e.title.toLowerCase().includes(q) || (e.description || "").toLowerCase().includes(q))
  }
  return list.sort((a, b) => new Date(a.start) - new Date(b.start))
})

async function deleteEventById(id) {
  if (!window.confirm("Permanently delete this event?")) return
  deletingId.value = id
  try {
    await calendarApi.deleteEvent(id)
    toast.success("Event deleted.")
    await loadAcademicEvents()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to delete event."))
  } finally { deletingId.value = null }
}

function openEditFromList(evt) {
  selectedEvent.value = { id: evt.id, ...evt }
  openEditEvent()
  showAllEventsModal.value = false
}

const editEventForm = reactive({
  title: "", description: "", event_type: "event",
  start: "", end: "", location: "", all_day: false,
  color: "#10B981", is_public: true,
  affects_timetable: false, timetable_scope: "",
})

// ── Semester form ──────────────────────────────────────────────────────────────
const editingSemester = ref(null)
const savingSemester  = ref(false)
const semForm = reactive({
  name: "", academic_year: "", semester_number: 1,
  start_date: "", end_date: "",
  break_start: "", break_end: "",
  exam_start: "", exam_end: "",
  registration_start: "", registration_end: "",
  timezone: "Africa/Dar_es_Salaam", is_current: false,
})

const createForm = reactive({
  title: "", description: "", event_type: "event",
  start: "", end: "", location: "", all_day: false,
  color: "#10B981", is_public: true,
  affects_timetable: false, timetable_scope: "",
})

const reminderForm = reactive({ channel: "email", scheduled_at: "" })
const cancelReason = ref("")

// ── Helpers ────────────────────────────────────────────────────────────────────
function toLocalDateStr(d) {
  return d.getFullYear() + "-"
    + String(d.getMonth() + 1).padStart(2, "0") + "-"
    + String(d.getDate()).padStart(2, "0")
}

/** All dates (YYYY-MM-DD) with the given JS-day-of-week within [startStr, endStr]. */
function getDatesForDay(dayOfWeek, startStr, endStr) {
  if (!startStr || !endStr) return []
  const dates = []
  const start = new Date(startStr + "T00:00:00")
  const end   = new Date(endStr   + "T00:00:00")
  const diff  = (dayOfWeek - start.getDay() + 7) % 7
  let cur = new Date(start.getFullYear(), start.getMonth(), start.getDate() + diff)
  while (cur <= end) {
    dates.push(toLocalDateStr(cur))
    cur = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + 7)
  }
  return dates
}

/** "break" | "exam" | false — which academic period a date falls in */
function semesterPeriodOf(dateStr) {
  const d = new Date(dateStr + "T00:00:00")
  for (const sem of semesters.value) {
    if (sem.break_start && sem.break_end) {
      if (d >= new Date(sem.break_start + "T00:00:00") && d <= new Date(sem.break_end + "T00:00:00"))
        return "break"
    }
    if (sem.exam_start && sem.exam_end) {
      if (d >= new Date(sem.exam_start + "T00:00:00") && d <= new Date(sem.exam_end + "T00:00:00"))
        return "exam"
    }
  }
  return false
}

// ── Holiday date set (for fading sessions) ────────────────────────────────────
const holidayDateSet = computed(() => {
  const s = new Set()
  if (showHolidays.value) {
    for (const h of publicHolidays.value) s.add(h.date)
  }
  if (showInstitutionalHolidays.value) {
    for (const h of institutionalHolidays.value) {
      if (!h.end_date) {
        s.add(h.date)
      } else {
        let cur = new Date(h.date + "T00:00:00")
        const endD = new Date(h.end_date + "T00:00:00")
        while (cur <= endD) {
          s.add(toLocalDateStr(cur))
          cur = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + 1)
        }
      }
    }
  }
  return s
})

// ── Event building ────────────────────────────────────────────────────────────
const currentSemester = computed(() => semesters.value.find(s => s.is_current) || semesters.value[0])

const allEvents = computed(() => {
  const events = []

  // Academic events (includes cancelled — loaded that way)
  for (const evt of academicEvents.value) {
    if (!activeFilters.value.has(evt.event_type)) continue
    const typeColor  = EVENT_TYPES[evt.event_type]?.color || evt.color || "#10B981"
    const borderClr  = evt.affects_timetable ? "#7C3AED" : (evt.is_cancelled ? "#6B7280" : typeColor)
    events.push({
      id: evt.id,
      title: evt.is_cancelled ? `✗ ${evt.title}` : (evt.affects_timetable ? `⚡ ${evt.title}` : evt.title),
      start: evt.start, end: evt.end || undefined,
      allDay: evt.all_day,
      backgroundColor: evt.is_cancelled ? "#9CA3AF" : typeColor,
      borderColor: borderClr,
      textColor: "#ffffff",
      extendedProps: { _source: "calendar", ...evt },
      classNames: [
        ...(evt.is_cancelled       ? ["fc-event-cancelled"]          : []),
        ...(evt.affects_timetable  ? ["fc-event-affects-timetable"]  : []),
      ],
    })
  }

  // Public holiday backgrounds
  if (showHolidays.value && activeFilters.value.has("holiday")) {
    for (const h of publicHolidays.value) {
      events.push({
        id: `ph-${h.date}`,
        title: `🎌 ${h.localName || h.name}`,
        start: h.date, allDay: true,
        display: "background",
        backgroundColor: "#FEE2E2",
        extendedProps: { _source: "holiday", ...h },
      })
    }
  }

  // Institutional holiday backgrounds
  if (showInstitutionalHolidays.value && activeFilters.value.has("holiday")) {
    for (const h of institutionalHolidays.value) {
      events.push({
        id: `ih-${h.id}`,
        title: `🏛 ${h.name}`,
        start: h.date, end: h.end_date || undefined, allDay: true,
        display: "background",
        backgroundColor: "#FDE68A",
        extendedProps: { _source: "inst-holiday", ...h },
      })
    }
  }

  // Semester break background (green)
  if (showSemesterBreaks.value) {
    for (const sem of semesters.value) {
      if (sem.break_start && sem.break_end) {
        events.push({
          id: `brk-${sem.id}`,
          title: `📅 ${sem.name} Break`,
          start: sem.break_start, end: sem.break_end, allDay: true,
          display: "background", backgroundColor: "#D1FAE5",
          extendedProps: { _source: "sem-break", semester: sem },
        })
      }
      // Exam period background (light orange)
      if (sem.exam_start && sem.exam_end) {
        events.push({
          id: `exam-bg-${sem.id}`,
          title: `📝 ${sem.name} Exams`,
          start: sem.exam_start, end: sem.exam_end, allDay: true,
          display: "background", backgroundColor: "#FEF3C7",
          extendedProps: { _source: "exam-period", semester: sem },
        })
      }
    }
  }

  // ── Timetable sessions — one event per occurrence date across ALL enabled timetables.
  //    Each timetable is paired with its own semester's date range via calendar_semester_id.
  if (showTimetableSessions.value) {
    for (const tt of timetableList.value) {
      if (!enabledTimetables.value.has(tt.id)) continue
      const entries = timetableEntriesMap.value[tt.id] || []
      if (!entries.length) continue

      // Resolve the date range: prefer the semester this timetable was generated for,
      // fall back to the current/first semester, then to the full academic year.
      const linkedSem = tt.calendar_semester_id
        ? semesters.value.find(s => s.id === tt.calendar_semester_id)
        : null
      const sem       = linkedSem || currentSemester.value
      const rangeStart = sem?.start_date || `${currentYear}-01-15`
      const rangeEnd   = sem?.end_date   || `${currentYear}-12-15`

      for (const entry of entries) {
        const slot = entry.time_slot
        if (!slot) continue
        const slotType = slot.slot_type || (slot.is_break ? "break" : "class")
        if (["break", "lunch"].includes(slotType)) continue

        const dow = DAY_MAP[slot.day]
        if (dow === undefined) continue

        for (const dateStr of getDatesForDay(dow, rangeStart, rangeEnd)) {
          const isHoliday   = holidayDateSet.value.has(dateStr)
          const period      = semesterPeriodOf(dateStr)
          const faded       = isHoliday || period === "break"
          const examSession = period === "exam"

          let bg = "#1D4ED8", border = "#1E40AF"
          if (isHoliday)            { bg = "#93C5FD"; border = "#60A5FA" }
          else if (period === "break")  { bg = "#A5B4FC"; border = "#818CF8" }
          else if (examSession)         { bg = "#F59E0B"; border = "#D97706" }

          events.push({
            id: `sess-${entry.id}-${dateStr}`,
            title: `${entry.course?.code || "?"} · ${entry.room?.code || "TBD"}`,
            start: `${dateStr}T${slot.start_time}`,
            end:   `${dateStr}T${slot.end_time}`,
            backgroundColor: bg,
            borderColor: border,
            textColor: "#ffffff",
            extendedProps: {
              _source: "session",
              _isHoliday: isHoliday,
              _isFaded: faded,
              _isExam: examSession,
              _timetableName: tt.name,
              _semesterName: sem?.name || "",
              course: entry.course,
              lecturer: entry.lecturer,
              room: entry.room,
              student_group: entry.student_group,
              time_slot: slot,
            },
          })
        }
      }
    }
  }

  return events
})

// ── FullCalendar options ──────────────────────────────────────────────────────
const calendarOptions = reactive({
  plugins: [dayGridPlugin, timeGridPlugin, interactionPlugin, multiMonthPlugin, listPlugin],
  initialView: "dayGridMonth",
  headerToolbar: {
    left: "prev,next today",
    center: "title",
    right: "multiMonthYear,dayGridMonth,timeGridWeek,timeGridDay,listWeek",
  },
  views: {
    multiMonthYear: { type: "multiMonth", duration: { months: 12 }, buttonText: "Year" },
    listWeek:    { buttonText: "List" },
    timeGridDay:  { buttonText: "Day" },
    timeGridWeek: { buttonText: "Week" },
    dayGridMonth: { buttonText: "Month" },
  },
  nowIndicator: true,
  weekNumbers: false,
  dayMaxEvents: 3,
  moreLinkClick: "popover",
  navLinks: true,
  selectable: false,
  selectMirror: true,
  editable: false,
  height: "auto",
  events: [],
  eventClick: handleEventClick,
  select: handleDateSelect,
  eventDidMount(info) {
    const ep = info.event.extendedProps
    if (ep.is_cancelled) {
      info.el.style.opacity = "0.5"
      const t = info.el.querySelector(".fc-event-title")
      if (t) t.style.textDecoration = "line-through"
    }
    if (ep._isHoliday) {
      info.el.style.opacity = "0.3"
      info.el.title = "Public holiday — class likely cancelled"
    } else if (ep._isFaded) {
      info.el.style.opacity = "0.45"
      info.el.title = "Semester break — no regular classes"
    } else if (ep._isExam) {
      info.el.style.opacity = "0.7"
      info.el.title = "Exam period"
    }
  },
})

// Keep events + selectable reactive
watchEffect(() => { calendarOptions.events = allEvents.value })
watchEffect(() => { calendarOptions.selectable = auth.isAdmin || auth.isTimetableOfficer })

// Navigate to current semester start date when it becomes available
watch(currentSemester, (sem) => {
  if (sem?.start_date && calendarRef.value) {
    calendarRef.value.getApi().gotoDate(sem.start_date)
  }
}, { flush: "post" })

// ── Data loading ──────────────────────────────────────────────────────────────
async function loadAcademicEvents() {
  try {
    // include_cancelled=true so we can display them with strikethrough
    const { data } = await calendarApi.events({ include_cancelled: true })
    academicEvents.value = data.data || []
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load events."))
  }
}

async function loadSemesters() {
  try {
    const { data } = await calendarApi.semesters()
    semesters.value = data.data || []
  } catch { semesters.value = [] }
}

async function loadTimetables() {
  try {
    const { data } = await timetableApi.list({})
    timetableList.value = data.data || []
    // Enable all non-archived timetables by default
    const enabled = new Set(
      timetableList.value
        .filter(t => t.status !== "archived")
        .map(t => t.id)
    )
    enabledTimetables.value = enabled
    // Load entries for all timetables in parallel
    await loadAllTimetableEntries()
  } catch { timetableList.value = [] }
}

async function loadAllTimetableEntries() {
  if (!timetableList.value.length) return
  const results = await Promise.allSettled(
    timetableList.value.map(tt =>
      timetableApi.get(tt.id)
        .then(({ data }) => ({ id: tt.id, entries: data.data?.entries || [] }))
        .catch(() => ({ id: tt.id, entries: [] }))
    )
  )
  const map = {}
  for (const r of results) {
    if (r.status === "fulfilled") map[r.value.id] = r.value.entries
  }
  timetableEntriesMap.value = map
}

async function loadPublicHolidays() {
  holidaysLoading.value = true
  try {
    const years = [currentYear - 1, currentYear, currentYear + 1]
    const results = await Promise.allSettled(
      years.map(y =>
        fetch(`https://date.nager.at/api/v3/PublicHolidays/${y}/${countryCode.value}`)
          .then(r => (r.ok ? r.json() : []))
          .catch(() => [])
      )
    )
    publicHolidays.value = results
      .filter(r => r.status === "fulfilled")
      .flatMap(r => r.value)
      .filter(h => Array.isArray(h.types) && h.types.includes("Public"))
  } finally {
    holidaysLoading.value = false
  }
}

async function loadInstitutionalHolidays() {
  try {
    const { data } = await calendarApi.holidays()
    institutionalHolidays.value = data.data || []
  } catch { institutionalHolidays.value = [] }
}

// ── Semester CRUD ─────────────────────────────────────────────────────────────
function openNewSemester() {
  editingSemester.value = null
  Object.assign(semForm, {
    name: `Semester 1`, academic_year: `${currentYear}/${currentYear + 1}`,
    semester_number: 1,
    start_date: `${currentYear}-02-01`, end_date: `${currentYear}-06-30`,
    break_start: "", break_end: "",
    exam_start: "", exam_end: "",
    registration_start: "", registration_end: "",
    timezone: "Africa/Dar_es_Salaam", is_current: false,
  })
  showSemesterModal.value = true
}

function openEditSemester(sem) {
  editingSemester.value = sem
  Object.assign(semForm, {
    name: sem.name, academic_year: sem.academic_year,
    semester_number: sem.semester_number,
    start_date: sem.start_date, end_date: sem.end_date,
    break_start: sem.break_start || "", break_end: sem.break_end || "",
    exam_start: sem.exam_start || "",   exam_end: sem.exam_end || "",
    registration_start: sem.registration_start || "",
    registration_end:   sem.registration_end   || "",
    timezone: sem.timezone || "Africa/Dar_es_Salaam",
    is_current: sem.is_current,
  })
  showSemesterModal.value = true
}

async function saveSemester() {
  if (!semForm.name || !semForm.start_date || !semForm.end_date) {
    toast.error("Name, start date and end date are required.")
    return
  }
  savingSemester.value = true
  try {
    const payload = { ...semForm }
    // Strip empty optional dates → null so backend accepts them
    for (const k of ["break_start","break_end","exam_start","exam_end","registration_start","registration_end"]) {
      if (!payload[k]) payload[k] = null
    }
    if (editingSemester.value) {
      await calendarApi.updateSemester(editingSemester.value.id, payload)
      toast.success("Semester updated.")
    } else {
      await calendarApi.createSemester(payload)
      toast.success("Semester created.")
    }
    showSemesterModal.value = false
    await loadSemesters()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to save semester."))
  } finally {
    savingSemester.value = false
  }
}

async function deleteSemester(id) {
  if (!window.confirm("Delete this semester? This cannot be undone.")) return
  try {
    await calendarApi.deleteSemester(id)
    toast.success("Semester deleted.")
    await loadSemesters()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to delete semester."))
  }
}

async function makeCurrentSemester(id) {
  try {
    await calendarApi.setCurrentSemester(id)
    await loadSemesters()
    toast.success("Semester set as current.")
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to set current semester."))
  }
}

// ── Calendar event handlers ───────────────────────────────────────────────────
function handleEventClick(info) {
  const ep = info.event.extendedProps
  // Background events (holidays) shouldn't open a modal
  if (info.event.display === "background") return
  selectedEvent.value = {
    id: info.event.id,
    title: info.event.title.replace(/^[✗⚡] /, ""),
    start: info.event.start,
    end: info.event.end,
    allDay: info.event.allDay,
    ...ep,
  }
  showReminderForm.value = false
  showCancelForm.value = false
  showDetailModal.value = true
}

function handleDateSelect(info) {
  createForm.start = info.startStr.slice(0, 16)
  createForm.end   = info.endStr.slice(0, 16)
  createForm.all_day = info.allDay
  showCreateModal.value = true
}

// ── Event CRUD ────────────────────────────────────────────────────────────────
async function createEvent() {
  if (!createForm.title || !createForm.start) {
    toast.error("Title and start date are required.")
    return
  }
  saving.value = true
  try {
    await calendarApi.createEvent({ ...createForm })
    toast.success("Event created.")
    closeCreateModal()
    await loadAcademicEvents()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to create event."))
  } finally { saving.value = false }
}

async function cancelSelectedEvent() {
  cancelling.value = true
  try {
    await calendarApi.cancelEvent(selectedEvent.value.id, cancelReason.value)
    toast.success("Event cancelled.")
    showCancelForm.value = false
    cancelReason.value = ""
    closeDetailModal()
    await loadAcademicEvents()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to cancel event."))
  } finally { cancelling.value = false }
}

async function uncancelSelectedEvent() {
  try {
    await calendarApi.uncancelEvent(selectedEvent.value.id)
    toast.success("Event restored.")
    closeDetailModal()
    await loadAcademicEvents()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to restore event."))
  }
}

async function deleteSelectedEvent() {
  if (!window.confirm("Permanently delete this event?")) return
  deleting.value = true
  try {
    await calendarApi.deleteEvent(selectedEvent.value.id)
    toast.success("Event deleted.")
    closeDetailModal()
    await loadAcademicEvents()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to delete event."))
  } finally { deleting.value = false }
}

function openEditEvent() {
  const evt = selectedEvent.value
  Object.assign(editEventForm, {
    title: evt.title || "",
    description: evt.description || "",
    event_type: evt.event_type || "event",
    start: evt.start ? new Date(evt.start).toISOString().slice(0, 16) : "",
    end: evt.end ? new Date(evt.end).toISOString().slice(0, 16) : "",
    location: evt.location || "",
    all_day: evt.allDay || evt.all_day || false,
    color: evt.color || "#10B981",
    is_public: evt.is_public !== undefined ? evt.is_public : true,
    affects_timetable: evt.affects_timetable || false,
    timetable_scope: evt.timetable_scope || "",
  })
  showDetailModal.value = false
  showEditModal.value = true
}

async function updateEvent() {
  if (!editEventForm.title || !editEventForm.start) {
    toast.error("Title and start date are required.")
    return
  }
  updating.value = true
  try {
    await calendarApi.updateEvent(selectedEvent.value.id, { ...editEventForm })
    toast.success("Event updated.")
    showEditModal.value = false
    selectedEvent.value = null
    await loadAcademicEvents()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to update event."))
  } finally { updating.value = false }
}

async function sendReminder() {
  sendingReminder.value = true
  try {
    const evt = selectedEvent.value
    await notificationApi.send({
      recipient_id: auth.user?.id,
      recipient_email: auth.user?.email,
      channel: reminderForm.channel,
      notification_type: "reminder",
      subject: `Reminder: ${evt.title}`,
      body: `You have an upcoming event: "${evt.title}" on ${formatDate(evt.start)}${evt.location ? " at " + evt.location : ""}.`,
      scheduled_at: reminderForm.scheduled_at || undefined,
    })
    toast.success("Reminder set.")
    showReminderForm.value = false
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to set reminder."))
  } finally { sendingReminder.value = false }
}

// ── Misc helpers ──────────────────────────────────────────────────────────────
function closeCreateModal() {
  showCreateModal.value = false
  Object.assign(createForm, {
    title: "", description: "", event_type: "event",
    start: "", end: "", location: "", all_day: false,
    color: "#10B981", is_public: true,
    affects_timetable: false, timetable_scope: "",
  })
}

function closeDetailModal() {
  showDetailModal.value = false
  showReminderForm.value = false
  showCancelForm.value = false
  selectedEvent.value = null
}

function toggleFilter(type) {
  const s = new Set(activeFilters.value)
  s.has(type) ? s.delete(type) : s.add(type)
  activeFilters.value = s
}

function formatDate(dt) {
  if (!dt) return "—"
  return new Date(dt).toLocaleString(undefined, {
    weekday: "short", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  })
}
function formatDateOnly(dt) {
  if (!dt) return "—"
  return new Date(dt + "T00:00:00").toLocaleDateString(undefined, {
    weekday: "short", month: "long", day: "numeric", year: "numeric",
  })
}

const isCalendarSource = computed(() => selectedEvent.value?._source === "calendar")
const isSessionSource  = computed(() => selectedEvent.value?._source === "session")
const canManage        = computed(() => auth.isAdmin || auth.isTimetableOfficer)

// ── Watchers ──────────────────────────────────────────────────────────────────
watch(countryCode, loadPublicHolidays)

onMounted(async () => {
  loading.value = true
  await Promise.all([
    loadAcademicEvents(), loadSemesters(), loadTimetables(),
    loadPublicHolidays(), loadInstitutionalHolidays(),
  ])
  loading.value = false
})
</script>

<template>
  <div class="flex flex-col h-full gap-0">

    <!-- ── Header ─────────────────────────────────────────────────────────── -->
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Academic Calendar</h1>
        <p class="text-sm text-gray-500 mt-0.5">
          <span v-if="currentSemester">
            {{ currentSemester.name }} · {{ currentSemester.academic_year }}
            <span class="text-gray-400">
              · {{ formatDateOnly(currentSemester.start_date) }} → {{ formatDateOnly(currentSemester.end_date) }}
            </span>
          </span>
          <span v-else class="text-amber-600 font-medium">No semester configured — sessions use full-year range</span>
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button class="btn-secondary text-sm" @click="showSidebar = !showSidebar">
          {{ showSidebar ? "Hide" : "Show" }} Panel
        </button>
        <a :href="calendarApi.exportIcs()" target="_blank" class="btn-secondary text-sm">Export ICS</a>
        <button class="btn-secondary text-sm" @click="showAllEventsModal = true">
          View All Events
        </button>
        <button v-if="canManage" class="btn-primary text-sm" @click="showCreateModal = true">
          + Create Event
        </button>
      </div>
    </div>

    <!-- ── Main layout ─────────────────────────────────────────────────────── -->
    <div class="flex gap-4 min-h-0 flex-1">

      <!-- ── Sidebar ──────────────────────────────────────────────────────── -->
      <aside v-if="showSidebar" class="w-64 flex-shrink-0 space-y-4 overflow-y-auto pb-4">

        <!-- Timetable overlay -->
        <div class="card p-4 space-y-3">
          <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Timetable Overlay</h3>
          <label class="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" v-model="showTimetableSessions" class="rounded text-blue-600" />
            <span class="text-gray-700">Show class sessions</span>
          </label>

          <!-- Per-timetable checkboxes (each uses its own semester's date range) -->
          <div v-if="showTimetableSessions && timetableList.length" class="space-y-1.5">
            <p class="text-xs text-gray-400">Showing each timetable in its own semester range:</p>
            <label
              v-for="tt in timetableList" :key="tt.id"
              class="flex items-start gap-2 text-xs cursor-pointer group"
            >
              <input
                type="checkbox"
                class="rounded text-blue-600 mt-0.5 flex-shrink-0"
                :checked="enabledTimetables.has(tt.id)"
                @change="e => { const s = new Set(enabledTimetables); e.target.checked ? s.add(tt.id) : s.delete(tt.id); enabledTimetables = s }"
              />
              <span class="leading-tight">
                <span class="font-medium text-gray-800 block">{{ tt.name }}</span>
                <span class="text-gray-400">
                  Sem {{ tt.semester }} · {{ tt.academic_year }}
                  <span v-if="tt.calendar_semester_id"
                    class="text-blue-500 ml-1"
                    :title="semesters.find(s=>s.id===tt.calendar_semester_id)?.name || 'Linked semester'">
                    🔗
                  </span>
                  <span v-else class="text-amber-500 ml-1" title="Not linked to a semester — uses current semester range">⚠</span>
                </span>
                <span
                  class="inline-block mt-0.5 px-1 rounded text-white text-[10px] leading-4"
                  :class="tt.status==='active'?'bg-green-500':tt.status==='archived'?'bg-gray-400':'bg-amber-400'">
                  {{ tt.status }}
                </span>
              </span>
            </label>
            <p v-if="!timetableList.length" class="text-xs text-gray-400 italic">No timetables found.</p>
          </div>

          <!-- Session legend -->
          <div v-if="showTimetableSessions" class="pt-1 space-y-1 text-xs text-gray-500 border-t border-gray-100">
            <div class="flex items-center gap-2"><span class="w-3 h-2 rounded bg-blue-700 inline-block"></span>Regular class</div>
            <div class="flex items-center gap-2"><span class="w-3 h-2 rounded bg-amber-400 inline-block"></span>Exam period</div>
            <div class="flex items-center gap-2 opacity-50"><span class="w-3 h-2 rounded bg-indigo-400 inline-block"></span>Semester break</div>
            <div class="flex items-center gap-2 opacity-30"><span class="w-3 h-2 rounded bg-blue-300 inline-block"></span>Public holiday</div>
          </div>
        </div>

        <!-- Holidays & Breaks -->
        <div class="card p-4 space-y-3">
          <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Holidays &amp; Breaks</h3>
          <label class="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" v-model="showHolidays" class="rounded text-red-500" />
            <span class="text-gray-700">National holidays</span>
            <span v-if="holidaysLoading" class="text-xs text-gray-400 ml-auto">loading…</span>
          </label>
          <div v-if="showHolidays">
            <select v-model="countryCode" class="input text-sm mt-1">
              <option v-for="c in COUNTRIES" :key="c.code" :value="c.code">{{ c.name }}</option>
            </select>
          </div>
          <label class="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" v-model="showInstitutionalHolidays" class="rounded text-amber-500" />
            <span class="text-gray-700">Institutional holidays</span>
            <span class="ml-auto text-xs text-amber-600 font-medium">{{ institutionalHolidays.length }}</span>
          </label>
          <label class="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" v-model="showSemesterBreaks" class="rounded text-teal-500" />
            <span class="text-gray-700">Breaks &amp; exam periods</span>
          </label>
        </div>

        <!-- Event type filters -->
        <div class="card p-4 space-y-1">
          <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Event Types</h3>
          <button
            v-for="(cfg, type) in EVENT_TYPES" :key="type"
            class="flex items-center gap-2 w-full text-left rounded-lg px-2 py-1.5 text-sm transition-colors"
            :class="activeFilters.has(type) ? 'opacity-100 hover:bg-gray-50' : 'opacity-35'"
            @click="toggleFilter(type)"
          >
            <span class="w-3 h-3 rounded-full flex-shrink-0" :style="{ backgroundColor: cfg.color }"></span>
            <span class="text-gray-700">{{ cfg.label }}</span>
            <svg v-if="activeFilters.has(type)" class="ml-auto w-3.5 h-3.5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
            </svg>
          </button>
        </div>

        <!-- Semester configuration panel -->
        <div class="card p-4 space-y-3">
          <div class="flex items-center justify-between">
            <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Semesters</h3>
            <button v-if="canManage" class="text-xs text-blue-600 hover:text-blue-800 font-medium" @click="openNewSemester">
              + New
            </button>
          </div>

          <!-- No semesters yet -->
          <div v-if="!semesters.length" class="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg p-3">
            No semesters configured. Classes will span the full calendar year.
            <button v-if="canManage" class="block mt-2 text-blue-600 font-medium" @click="openNewSemester">
              → Configure now
            </button>
          </div>

          <!-- Semester list -->
          <div v-for="sem in semesters" :key="sem.id"
            class="rounded-lg border p-2.5 text-xs space-y-1"
            :class="sem.is_current ? 'border-green-300 bg-green-50' : 'border-gray-200 bg-gray-50'">
            <div class="flex items-center justify-between gap-1">
              <span class="flex items-center gap-1.5 font-semibold text-gray-900 truncate">
                <span v-if="sem.is_current" class="w-2 h-2 rounded-full bg-green-500 flex-shrink-0"></span>
                <span v-else class="w-2 h-2 rounded-full bg-gray-300 flex-shrink-0"></span>
                {{ sem.name }}
              </span>
              <div class="flex gap-1 flex-shrink-0">
                <button v-if="canManage && !sem.is_current"
                  class="text-teal-600 hover:text-teal-800 px-1 font-medium" title="Set as current"
                  @click="makeCurrentSemester(sem.id)">✓</button>
                <button v-if="canManage"
                  class="text-blue-600 hover:text-blue-800 px-1" title="Edit"
                  @click="openEditSemester(sem)">✎</button>
                <button v-if="canManage"
                  class="text-red-400 hover:text-red-600 px-1" title="Delete"
                  @click="deleteSemester(sem.id)">×</button>
              </div>
            </div>
            <p class="text-gray-500 pl-3.5">{{ sem.start_date }} → {{ sem.end_date }}</p>
            <div v-if="sem.break_start" class="pl-3.5 text-teal-600">
              Break: {{ sem.break_start }} → {{ sem.break_end }}
            </div>
            <div v-if="sem.exam_start" class="pl-3.5 text-amber-600">
              Exams: {{ sem.exam_start }} → {{ sem.exam_end }}
            </div>
          </div>
        </div>
      </aside>

      <!-- ── Calendar ──────────────────────────────────────────────────────── -->
      <div class="flex-1 min-w-0 bg-white rounded-xl border border-gray-200 overflow-y-auto calendar-container">
        <div v-if="loading" class="flex items-center justify-center h-96 text-gray-400 text-sm">
          Loading calendar…
        </div>
        <FullCalendar v-else ref="calendarRef" :options="calendarOptions" />
      </div>
    </div>

    <!-- ── Semester Modal ─────────────────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="showSemesterModal" class="modal-backdrop" @click.self="showSemesterModal = false">
        <div class="modal-box w-full max-w-2xl">
          <div class="modal-header">
            <h2 class="text-lg font-bold text-gray-900">
              {{ editingSemester ? "Edit Semester" : "New Semester" }}
            </h2>
            <button class="modal-close" @click="showSemesterModal = false">✕</button>
          </div>
          <div class="modal-body space-y-4">
            <!-- Core fields -->
            <div class="grid grid-cols-2 gap-3">
              <div class="col-span-2 md:col-span-1">
                <label class="label">Semester Name *</label>
                <input v-model="semForm.name" class="input" placeholder="e.g. Semester 1 2024/25"/>
              </div>
              <div>
                <label class="label">Academic Year *</label>
                <input v-model="semForm.academic_year" class="input" placeholder="2024/2025"/>
              </div>
              <div>
                <label class="label">Semester Number</label>
                <select v-model.number="semForm.semester_number" class="input">
                  <option :value="1">1st Semester</option>
                  <option :value="2">2nd Semester</option>
                  <option :value="3">3rd Semester (trimester)</option>
                </select>
              </div>
            </div>

            <!-- Teaching period -->
            <div class="border border-blue-100 rounded-xl p-3 space-y-3 bg-blue-50/30">
              <p class="text-xs font-semibold text-blue-700 uppercase tracking-wide">Teaching Period *</p>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="label text-xs">Start Date *</label>
                  <input v-model="semForm.start_date" type="date" class="input text-sm"/>
                </div>
                <div>
                  <label class="label text-xs">End Date *</label>
                  <input v-model="semForm.end_date" type="date" class="input text-sm"/>
                </div>
              </div>
            </div>

            <!-- Mid-sem break -->
            <div class="border border-teal-100 rounded-xl p-3 space-y-3 bg-teal-50/20">
              <p class="text-xs font-semibold text-teal-700 uppercase tracking-wide">Mid-semester Break (optional)</p>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="label text-xs">Break Start</label>
                  <input v-model="semForm.break_start" type="date" class="input text-sm"/>
                </div>
                <div>
                  <label class="label text-xs">Break End</label>
                  <input v-model="semForm.break_end" type="date" class="input text-sm"/>
                </div>
              </div>
            </div>

            <!-- Exam period -->
            <div class="border border-amber-100 rounded-xl p-3 space-y-3 bg-amber-50/20">
              <p class="text-xs font-semibold text-amber-700 uppercase tracking-wide">Examination Period (optional)</p>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="label text-xs">Exam Start</label>
                  <input v-model="semForm.exam_start" type="date" class="input text-sm"/>
                </div>
                <div>
                  <label class="label text-xs">Exam End</label>
                  <input v-model="semForm.exam_end" type="date" class="input text-sm"/>
                </div>
              </div>
            </div>

            <!-- Registration -->
            <div class="border border-gray-100 rounded-xl p-3 space-y-3 bg-gray-50/50">
              <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Registration Window (optional)</p>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="label text-xs">Reg. Open</label>
                  <input v-model="semForm.registration_start" type="date" class="input text-sm"/>
                </div>
                <div>
                  <label class="label text-xs">Reg. Close</label>
                  <input v-model="semForm.registration_end" type="date" class="input text-sm"/>
                </div>
              </div>
            </div>

            <!-- Timezone + is_current -->
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="label text-xs">Timezone</label>
                <select v-model="semForm.timezone" class="input text-sm">
                  <option value="Africa/Dar_es_Salaam">Africa/Dar_es_Salaam (TZ)</option>
                  <option value="Africa/Nairobi">Africa/Nairobi (KE/UG)</option>
                  <option value="Africa/Lagos">Africa/Lagos (NG)</option>
                  <option value="Africa/Johannesburg">Africa/Johannesburg (ZA)</option>
                  <option value="Africa/Accra">Africa/Accra (GH)</option>
                  <option value="Africa/Cairo">Africa/Cairo (EG)</option>
                  <option value="UTC">UTC</option>
                  <option value="Europe/London">Europe/London</option>
                </select>
              </div>
              <div class="flex items-end pb-1">
                <label class="flex items-center gap-2 text-sm cursor-pointer">
                  <input v-model="semForm.is_current" type="checkbox" class="rounded text-blue-600"/>
                  <span class="font-medium text-gray-700">Mark as current semester</span>
                </label>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button v-if="editingSemester && canManage" class="btn-danger text-sm mr-auto"
              @click="deleteSemester(editingSemester.id); showSemesterModal = false">
              Delete
            </button>
            <button class="btn-secondary" @click="showSemesterModal = false">Cancel</button>
            <button class="btn-primary" :disabled="savingSemester" @click="saveSemester">
              {{ savingSemester ? "Saving…" : (editingSemester ? "Update Semester" : "Create Semester") }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── Create Event Modal ─────────────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="showCreateModal" class="modal-backdrop" @click.self="closeCreateModal">
        <div class="modal-box w-full max-w-lg">
          <div class="modal-header">
            <h2 class="text-lg font-bold text-gray-900">Create Academic Event</h2>
            <button class="modal-close" @click="closeCreateModal">✕</button>
          </div>
          <div class="modal-body space-y-3">
            <div>
              <label class="label">Event Title</label>
              <input v-model="createForm.title" class="input" placeholder="e.g. Mid-semester Exam"/>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="label">Type</label>
                <select v-model="createForm.event_type" class="input">
                  <option v-for="(cfg, type) in EVENT_TYPES" :key="type" :value="type">{{ cfg.label }}</option>
                </select>
              </div>
              <div>
                <label class="label">Location</label>
                <input v-model="createForm.location" class="input" placeholder="Room / Online"/>
              </div>
              <div>
                <label class="label">Start</label>
                <input v-model="createForm.start" type="datetime-local" class="input"/>
              </div>
              <div>
                <label class="label">End</label>
                <input v-model="createForm.end" type="datetime-local" class="input"/>
              </div>
            </div>
            <div>
              <label class="label">Description</label>
              <textarea v-model="createForm.description" rows="3" class="input" placeholder="Optional…"></textarea>
            </div>
            <div class="flex flex-wrap items-center gap-4">
              <label class="flex items-center gap-2 text-sm cursor-pointer">
                <input v-model="createForm.all_day" type="checkbox" class="rounded text-blue-600"/>
                All-day event
              </label>
              <label class="flex items-center gap-2 text-sm cursor-pointer">
                <input v-model="createForm.is_public" type="checkbox" class="rounded text-blue-600"/>
                Public
              </label>
              <label v-if="canManage" class="flex items-center gap-2 text-sm cursor-pointer"
                title="Sessions on this day will appear faded (affected by this event)">
                <input v-model="createForm.affects_timetable" type="checkbox" class="rounded text-purple-600"/>
                <span class="text-purple-700 font-medium">Affects timetable</span>
              </label>
            </div>
            <div v-if="createForm.affects_timetable">
              <label class="label">Timetable Scope</label>
              <input v-model="createForm.timetable_scope" class="input text-sm"
                placeholder="all · department · program · student_group"/>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn-secondary" @click="closeCreateModal">Cancel</button>
            <button class="btn-primary" :disabled="saving" @click="createEvent">
              {{ saving ? "Saving…" : "Create Event" }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── Event Detail Modal ─────────────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="showDetailModal && selectedEvent" class="modal-backdrop" @click.self="closeDetailModal">
        <div class="modal-box w-full max-w-lg">
          <div class="px-5 py-4 text-white rounded-t-2xl"
            :style="{ backgroundColor: isSessionSource ? '#1D4ED8' : (EVENT_TYPES[selectedEvent.event_type]?.color || '#3B82F6') }">
            <div class="flex items-start justify-between gap-2">
              <div>
                <p class="text-xs opacity-75 font-medium uppercase tracking-wide flex flex-wrap items-center gap-1.5">
                  <span>{{ isSessionSource ? "Class Session" : (selectedEvent.event_type || "Event") }}</span>
                  <span v-if="selectedEvent.is_cancelled"    class="bg-white/20 rounded px-1.5">CANCELLED</span>
                  <span v-if="selectedEvent.affects_timetable" class="bg-purple-500/80 rounded px-1.5">⚡ AFFECTS TIMETABLE</span>
                  <span v-if="selectedEvent._isHoliday"      class="bg-red-500/80 rounded px-1.5">🎌 HOLIDAY</span>
                  <span v-if="selectedEvent._isFaded && !selectedEvent._isHoliday" class="bg-white/20 rounded px-1.5">SEM BREAK</span>
                  <span v-if="selectedEvent._isExam"         class="bg-amber-500/80 rounded px-1.5">EXAM PERIOD</span>
                </p>
                <h2 class="text-xl font-bold mt-0.5">{{ selectedEvent.title }}</h2>
              </div>
              <button @click="closeDetailModal" class="text-white opacity-75 hover:opacity-100 text-2xl leading-none">✕</button>
            </div>
          </div>

          <div class="p-5 space-y-4">
            <!-- Session details -->
            <template v-if="isSessionSource">
              <div v-if="selectedEvent._isHoliday" class="text-sm bg-red-50 border border-red-200 rounded-lg p-3 text-red-700">
                🎌 This session falls on a public holiday and may be cancelled.
              </div>
              <div v-else-if="selectedEvent._isFaded" class="text-sm bg-indigo-50 border border-indigo-200 rounded-lg p-3 text-indigo-700">
                📅 This session falls during the semester break period.
              </div>
              <div v-else-if="selectedEvent._isExam" class="text-sm bg-amber-50 border border-amber-200 rounded-lg p-3 text-amber-700">
                📝 This session falls during the examination period.
              </div>
              <div class="grid grid-cols-2 gap-3 text-sm">
                <div class="info-chip">
                  <p class="info-label">Course</p>
                  <p class="info-val">{{ selectedEvent.course?.name }}</p>
                  <p class="text-xs text-gray-400">{{ selectedEvent.course?.code }}</p>
                </div>
                <div class="info-chip">
                  <p class="info-label">Date &amp; Time</p>
                  <p class="info-val">{{ formatDate(selectedEvent.start) }}</p>
                  <p class="text-xs text-gray-400">{{ selectedEvent.time_slot?.start_time }} – {{ selectedEvent.time_slot?.end_time }}</p>
                </div>
                <div class="info-chip">
                  <p class="info-label">Lecturer</p>
                  <p class="info-val">{{ selectedEvent.lecturer?.name || "—" }}</p>
                </div>
                <div class="info-chip">
                  <p class="info-label">Room</p>
                  <p class="info-val">{{ selectedEvent.room?.name || "TBD" }}</p>
                  <p class="text-xs text-gray-400">Cap: {{ selectedEvent.room?.capacity || "?" }}</p>
                </div>
                <div v-if="selectedEvent.student_group" class="info-chip col-span-2">
                  <p class="info-label">Student Group</p>
                  <p class="info-val">{{ selectedEvent.student_group?.name }}</p>
                </div>
                <div v-if="selectedEvent._timetableName" class="info-chip col-span-2">
                  <p class="info-label">Timetable · Semester</p>
                  <p class="info-val text-sm">{{ selectedEvent._timetableName }}<span v-if="selectedEvent._semesterName" class="text-gray-400 font-normal"> · {{ selectedEvent._semesterName }}</span></p>
                </div>
              </div>
            </template>

            <!-- Academic event details -->
            <template v-else-if="isCalendarSource">
              <div class="grid grid-cols-2 gap-3 text-sm">
                <div class="info-chip">
                  <p class="info-label">Start</p>
                  <p class="info-val">{{ formatDate(selectedEvent.start) }}</p>
                </div>
                <div class="info-chip">
                  <p class="info-label">End</p>
                  <p class="info-val">{{ formatDate(selectedEvent.end) }}</p>
                </div>
                <div v-if="selectedEvent.location" class="info-chip">
                  <p class="info-label">Location</p>
                  <p class="info-val">{{ selectedEvent.location }}</p>
                </div>
                <div v-if="selectedEvent.recurrence && selectedEvent.recurrence !== 'none'" class="info-chip">
                  <p class="info-label">Recurrence</p>
                  <p class="info-val capitalize">{{ selectedEvent.recurrence }}</p>
                </div>
              </div>
              <p v-if="selectedEvent.description" class="text-sm text-gray-600 bg-gray-50 rounded-lg p-3">
                {{ selectedEvent.description }}
              </p>
              <p v-if="selectedEvent.cancellation_reason" class="text-sm text-red-600 bg-red-50 rounded-lg p-3">
                Cancelled: {{ selectedEvent.cancellation_reason }}
              </p>
              <div v-if="selectedEvent.affects_timetable" class="text-sm bg-purple-50 border border-purple-200 rounded-lg p-3 space-y-1">
                <p class="font-semibold text-purple-900">⚡ Affects Timetable Sessions</p>
                <p v-if="selectedEvent.timetable_scope" class="text-purple-700 text-xs">Scope: {{ selectedEvent.timetable_scope }}</p>
                <p class="text-purple-600 text-xs">Regular sessions during this period are shown faded on the calendar.</p>
              </div>
            </template>

            <!-- Holiday/other -->
            <template v-else>
              <div class="info-chip text-sm">
                <p class="info-label">Date</p>
                <p class="info-val">{{ formatDateOnly(selectedEvent.date || selectedEvent.start) }}</p>
              </div>
            </template>

            <!-- Reminder form -->
            <div v-if="showReminderForm" class="border-t border-gray-100 pt-4 space-y-3">
              <h3 class="text-sm font-semibold text-gray-900">Set Reminder</h3>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="label text-xs">Channel</label>
                  <select v-model="reminderForm.channel" class="input text-sm">
                    <option value="email">Email</option>
                    <option value="sms">SMS</option>
                    <option value="both">Email + SMS</option>
                  </select>
                </div>
                <div>
                  <label class="label text-xs">Remind at (optional)</label>
                  <input v-model="reminderForm.scheduled_at" type="datetime-local" class="input text-sm"/>
                </div>
              </div>
              <div class="flex gap-2">
                <button class="btn-secondary text-sm" @click="showReminderForm = false">Cancel</button>
                <button class="btn-primary text-sm" :disabled="sendingReminder" @click="sendReminder">
                  {{ sendingReminder ? "Sending…" : "Set Reminder" }}
                </button>
              </div>
            </div>

            <!-- Cancel form -->
            <div v-if="showCancelForm && isCalendarSource" class="border-t border-gray-100 pt-4 space-y-3">
              <h3 class="text-sm font-semibold text-red-700">Cancel Event</h3>
              <input v-model="cancelReason" class="input text-sm" placeholder="Reason (optional)"/>
              <div class="flex gap-2">
                <button class="btn-secondary text-sm" @click="showCancelForm = false">Back</button>
                <button class="btn-danger text-sm" :disabled="cancelling" @click="cancelSelectedEvent">
                  {{ cancelling ? "Cancelling…" : "Confirm Cancel" }}
                </button>
              </div>
            </div>

            <!-- Actions -->
            <div v-if="!showReminderForm && !showCancelForm" class="border-t border-gray-100 pt-4 flex flex-wrap gap-2">
              <button class="btn-secondary text-sm" @click="showReminderForm = true">
                🔔 Remind Me
              </button>
              <template v-if="canManage && isCalendarSource">
                <button
                  class="btn-secondary text-sm text-blue-600 border-blue-200 hover:bg-blue-50"
                  @click="openEditEvent">
                  Edit Event
                </button>
                <button v-if="!selectedEvent.is_cancelled"
                  class="btn-secondary text-sm text-orange-600 border-orange-200 hover:bg-orange-50"
                  @click="showCancelForm = true">
                  Cancel Event
                </button>
                <button v-else
                  class="btn-secondary text-sm text-green-600 border-green-200 hover:bg-green-50"
                  @click="uncancelSelectedEvent">
                  Restore Event
                </button>
                <button class="btn-danger text-sm ml-auto" :disabled="deleting" @click="deleteSelectedEvent">
                  {{ deleting ? "Deleting…" : "Delete" }}
                </button>
              </template>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
    <!-- ── All Events Modal ─────────────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="showAllEventsModal" class="modal-backdrop" @click.self="showAllEventsModal = false">
        <div class="modal-box w-full max-w-3xl flex flex-col" style="max-height: 85vh;">
          <!-- Header -->
          <div class="modal-header flex-shrink-0">
            <div>
              <h2 class="text-lg font-bold text-gray-900">All Academic Events</h2>
              <p class="text-xs text-gray-400 mt-0.5">{{ filteredEvents.length }} event{{ filteredEvents.length !== 1 ? "s" : "" }}</p>
            </div>
            <button class="modal-close" @click="showAllEventsModal = false">✕</button>
          </div>

          <!-- Search + Filter bar -->
          <div class="px-5 pt-3 pb-2 flex flex-wrap gap-2 border-b border-gray-100 flex-shrink-0">
            <input
              v-model="eventsSearch"
              class="input flex-1 min-w-[160px] text-sm"
              placeholder="Search by title or description…"
            />
            <select v-model="eventsTypeFilter" class="input !w-auto text-sm">
              <option value="all">All types</option>
              <option v-for="(cfg, type) in EVENT_TYPES" :key="type" :value="type">{{ cfg.label }}</option>
            </select>
            <button v-if="canManage" class="btn-primary text-sm flex-shrink-0"
              @click="showAllEventsModal = false; showCreateModal = true">
              + New Event
            </button>
          </div>

          <!-- Events list -->
          <div class="flex-1 overflow-y-auto modal-body !pt-2 space-y-2">
            <div v-if="!filteredEvents.length" class="text-center py-12 text-gray-400 text-sm">
              No events found.
            </div>

            <div
              v-for="evt in filteredEvents"
              :key="evt.id"
              class="flex items-start gap-3 p-3 rounded-xl border transition-colors"
              :class="evt.is_cancelled ? 'border-gray-100 bg-gray-50 opacity-60' : 'border-gray-100 hover:border-gray-200 hover:bg-gray-50'"
            >
              <!-- Type dot -->
              <div
                class="w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0"
                :style="{ backgroundColor: EVENT_TYPES[evt.event_type]?.color || '#6B7280' }"
              ></div>

              <!-- Info -->
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <p class="font-semibold text-gray-900 text-sm" :class="{ 'line-through text-gray-400': evt.is_cancelled }">
                    {{ evt.title }}
                  </p>
                  <span
                    class="text-[10px] px-1.5 py-0.5 rounded-full font-semibold capitalize"
                    :style="{ backgroundColor: (EVENT_TYPES[evt.event_type]?.color || '#6B7280') + '20', color: EVENT_TYPES[evt.event_type]?.color || '#6B7280' }"
                  >{{ (EVENT_TYPES[evt.event_type]?.label || evt.event_type) }}</span>
                  <span v-if="evt.is_cancelled" class="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-200 text-gray-500 font-semibold">CANCELLED</span>
                  <span v-if="evt.affects_timetable" class="text-[10px] px-1.5 py-0.5 rounded-full bg-purple-100 text-purple-700 font-semibold">⚡ TIMETABLE</span>
                </div>
                <p class="text-xs text-gray-500 mt-0.5">
                  {{ formatDate(evt.start) }}
                  <span v-if="evt.end"> → {{ formatDate(evt.end) }}</span>
                  <span v-if="evt.location" class="ml-2 text-gray-400">📍 {{ evt.location }}</span>
                </p>
                <p v-if="evt.description" class="text-xs text-gray-400 mt-0.5 truncate">{{ evt.description }}</p>
              </div>

              <!-- Actions (admin/officer only) -->
              <div v-if="canManage" class="flex items-center gap-1 flex-shrink-0">
                <button
                  class="px-2.5 py-1.5 rounded-lg text-xs font-semibold text-blue-600 hover:bg-blue-50 transition-colors border border-blue-100"
                  @click="openEditFromList(evt)"
                >Edit</button>
                <button
                  class="px-2.5 py-1.5 rounded-lg text-xs font-semibold text-red-500 hover:bg-red-50 transition-colors border border-red-100"
                  :disabled="deletingId === evt.id"
                  @click="deleteEventById(evt.id)"
                >{{ deletingId === evt.id ? "…" : "Delete" }}</button>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="modal-footer flex-shrink-0">
            <button class="btn-secondary" @click="showAllEventsModal = false">Close</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── Edit Event Modal ──────────────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="showEditModal" class="modal-backdrop" @click.self="showEditModal = false">
        <div class="modal-box w-full max-w-lg">
          <div class="modal-header">
            <h2 class="text-lg font-bold text-gray-900">Edit Event</h2>
            <button class="modal-close" @click="showEditModal = false">✕</button>
          </div>
          <div class="modal-body space-y-3">
            <div>
              <label class="label">Event Title</label>
              <input v-model="editEventForm.title" class="input" placeholder="e.g. Mid-semester Exam"/>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="label">Type</label>
                <select v-model="editEventForm.event_type" class="input">
                  <option v-for="(cfg, type) in EVENT_TYPES" :key="type" :value="type">{{ cfg.label }}</option>
                </select>
              </div>
              <div>
                <label class="label">Location</label>
                <input v-model="editEventForm.location" class="input" placeholder="Room / Online"/>
              </div>
              <div>
                <label class="label">Start</label>
                <input v-model="editEventForm.start" type="datetime-local" class="input"/>
              </div>
              <div>
                <label class="label">End</label>
                <input v-model="editEventForm.end" type="datetime-local" class="input"/>
              </div>
            </div>
            <div>
              <label class="label">Description</label>
              <textarea v-model="editEventForm.description" rows="3" class="input" placeholder="Optional…"></textarea>
            </div>
            <div class="flex flex-wrap items-center gap-4">
              <label class="flex items-center gap-2 text-sm cursor-pointer">
                <input v-model="editEventForm.all_day" type="checkbox" class="rounded text-blue-600"/>
                All-day event
              </label>
              <label class="flex items-center gap-2 text-sm cursor-pointer">
                <input v-model="editEventForm.is_public" type="checkbox" class="rounded text-blue-600"/>
                Public
              </label>
              <label class="flex items-center gap-2 text-sm cursor-pointer"
                title="Sessions on this day will appear faded (affected by this event)">
                <input v-model="editEventForm.affects_timetable" type="checkbox" class="rounded text-purple-600"/>
                <span class="text-purple-700 font-medium">Affects timetable</span>
              </label>
            </div>
            <div v-if="editEventForm.affects_timetable">
              <label class="label">Timetable Scope</label>
              <input v-model="editEventForm.timetable_scope" class="input text-sm"
                placeholder="all · department · program · student_group"/>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn-secondary" @click="showEditModal = false">Cancel</button>
            <button class="btn-primary" :disabled="updating" @click="updateEvent">
              {{ updating ? "Saving…" : "Save Changes" }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

  </div>
</template>

<style scoped>
.calendar-container :deep(.fc) { font-family: inherit; }
.calendar-container :deep(.fc-toolbar-title) {
  font-size: 1.125rem; font-weight: 700; color: #111827;
}
.calendar-container :deep(.fc-button) {
  background-color: #f9fafb; border: 1px solid #e5e7eb;
  color: #374151; font-weight: 500; font-size: 0.8125rem;
  padding: 0.375rem 0.75rem; border-radius: 0.5rem;
  transition: all 0.15s; text-transform: capitalize; box-shadow: none !important;
}
.calendar-container :deep(.fc-button:hover) {
  background-color: #f3f4f6; border-color: #d1d5db; color: #111827;
}
.calendar-container :deep(.fc-button-active),
.calendar-container :deep(.fc-button-primary:not(:disabled).fc-button-active) {
  background-color: #2563eb !important; border-color: #1d4ed8 !important; color: #fff !important;
}
.calendar-container :deep(.fc-button-group .fc-button) { border-radius: 0; }
.calendar-container :deep(.fc-button-group .fc-button:first-child) { border-radius: 0.5rem 0 0 0.5rem; }
.calendar-container :deep(.fc-button-group .fc-button:last-child)  { border-radius: 0 0.5rem 0.5rem 0; }
.calendar-container :deep(.fc-daygrid-day.fc-day-today)  { background-color: #eff6ff; }
.calendar-container :deep(.fc-timegrid-col.fc-day-today) { background-color: #eff6ff; }
.calendar-container :deep(.fc-event) {
  border-radius: 4px; font-size: 0.75rem; font-weight: 500; cursor: pointer;
}
.calendar-container :deep(.fc-event-affects-timetable) {
  border-left-width: 3px !important; border-left-color: #7C3AED !important;
}
.calendar-container :deep(.fc-daygrid-event) { padding: 1px 4px; }
.calendar-container :deep(.fc-list-event:hover td) {
  background-color: #f3f4f6; cursor: pointer;
}
.calendar-container :deep(.fc-multimonth-month) { border-color: #e5e7eb; }
.calendar-container :deep(.fc-toolbar) { padding: 1rem 1rem 0; }
.calendar-container :deep(.fc-view-harness) { min-height: 400px; height: auto !important; }

/* Modal */
.modal-backdrop {
  position: fixed; inset: 0; z-index: 50;
  background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center; padding: 1rem;
}
.modal-box {
  background: #fff; border-radius: 1rem;
  box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25);
  overflow: hidden; max-height: 90vh; overflow-y: auto;
}
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 1.25rem 1.25rem 0;
}
.modal-close {
  width: 2rem; height: 2rem; border-radius: 0.5rem;
  display: flex; align-items: center; justify-content: center;
  color: #6b7280; transition: all 0.15s; font-size: 0.875rem;
}
.modal-close:hover { background: #f3f4f6; color: #111827; }
.modal-body   { padding: 1rem 1.25rem; }
.modal-footer {
  padding: 1rem 1.25rem; border-top: 1px solid #f3f4f6;
  display: flex; justify-content: flex-end; gap: 0.5rem; align-items: center;
}
.info-chip  { background: #f9fafb; border-radius: 0.5rem; padding: 0.625rem 0.75rem; }
.info-label { font-size: 0.6875rem; font-weight: 500; color: #9ca3af;
              text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.125rem; }
.info-val   { font-weight: 600; color: #111827; font-size: 0.875rem; }
</style>
