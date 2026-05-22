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

// Data
const academicEvents = ref([])
const publicHolidays = ref([])
const timetableEntries = ref([])
const timetableList = ref([])
const semesters = ref([])
const loading = ref(true)
const holidaysLoading = ref(false)
const institutionalHolidays = ref([])
const showInstitutionalHolidays = ref(true)
const showSemesterBreaks = ref(true)

// Overlay toggles
const showTimetableSessions = ref(true)
const showHolidays = ref(true)
const selectedTimetable = ref("")
const countryCode = ref("KE")
const currentYear = new Date().getFullYear()

// Active type filters
const EVENT_TYPES = {
  event: { label: "Event", color: "#10B981" },
  exam: { label: "Exam", color: "#F97316" },
  holiday: { label: "Holiday", color: "#EF4444" },
  deadline: { label: "Deadline", color: "#EAB308" },
  class: { label: "Class", color: "#3B82F6" },
  meeting: { label: "Meeting", color: "#8B5CF6" },
  announcement: { label: "Announcement", color: "#6B7280" },
  makeup: { label: "Make-up", color: "#EC4899" },
  semester_break: { label: "Semester Break", color: "#14B8A6" },
}
const activeFilters = ref(new Set(Object.keys(EVENT_TYPES)))

// Day of week map (FullCalendar: 0=Sun, 1=Mon..6=Sat)
const DAY_MAP = { Monday: 1, Tuesday: 2, Wednesday: 3, Thursday: 4, Friday: 5, Saturday: 6, Sunday: 0 }

// Country list (top academic countries in Africa + common ones)
const COUNTRIES = [
  { code: "KE", name: "Kenya" }, { code: "NG", name: "Nigeria" }, { code: "ZA", name: "South Africa" },
  { code: "GH", name: "Ghana" }, { code: "TZ", name: "Tanzania" }, { code: "UG", name: "Uganda" },
  { code: "ET", name: "Ethiopia" }, { code: "MA", name: "Morocco" }, { code: "EG", name: "Egypt" },
  { code: "GB", name: "United Kingdom" }, { code: "US", name: "United States" }, { code: "IN", name: "India" },
]

// Modals
const showCreateModal = ref(false)
const showDetailModal = ref(false)
const showSidebar = ref(true)
const selectedEvent = ref(null)
const showReminderForm = ref(false)
const showCancelForm = ref(false)
const saving = ref(false)
const sendingReminder = ref(false)
const deleting = ref(false)
const cancelling = ref(false)

const createForm = reactive({
  title: "", description: "", event_type: "event",
  start: "", end: "", location: "", all_day: false,
  color: "#10B981", is_public: true,
  affects_timetable: false, timetable_scope: "",
})

const reminderForm = reactive({ channel: "email", scheduled_at: "" })
const cancelReason = ref("")

// ─── Event building ───────────────────────────────────────────────────────────
const currentSemester = computed(() => semesters.value.find((s) => s.is_current) || semesters.value[0])

const allEvents = computed(() => {
  const events = []

  // Academic events from calendar-service
  for (const evt of academicEvents.value) {
    if (!activeFilters.value.has(evt.event_type)) continue
    const typeColor = EVENT_TYPES[evt.event_type]?.color || evt.color || "#10B981"
    const affectsBorder = evt.affects_timetable ? "#7C3AED" : (evt.is_cancelled ? "#6B7280" : typeColor)
    events.push({
      id: evt.id,
      title: evt.is_cancelled ? `✗ ${evt.title}` : (evt.affects_timetable ? `⚡ ${evt.title}` : evt.title),
      start: evt.start,
      end: evt.end || undefined,
      allDay: evt.all_day,
      backgroundColor: evt.is_cancelled ? "#9CA3AF" : typeColor,
      borderColor: affectsBorder,
      borderWidth: evt.affects_timetable ? 3 : 1,
      textColor: "#ffffff",
      extendedProps: { _source: "calendar", ...evt },
      classNames: [
        ...(evt.is_cancelled ? ["fc-event-cancelled"] : []),
        ...(evt.affects_timetable ? ["fc-event-affects-timetable"] : []),
      ],
    })
  }

  // Public holidays (from Nager.Date)
  if (showHolidays.value && activeFilters.value.has("holiday")) {
    for (const h of publicHolidays.value) {
      events.push({
        id: `holiday-${h.date}`,
        title: `🎌 ${h.localName || h.name}`,
        start: h.date,
        allDay: true,
        display: "background",
        backgroundColor: "#FEE2E2",
        borderColor: "#EF4444",
        extendedProps: { _source: "holiday", name: h.name, date: h.date },
      })
    }
  }

  // Institutional holidays (from AcademicHoliday API)
  if (showInstitutionalHolidays.value && activeFilters.value.has("holiday")) {
    for (const h of institutionalHolidays.value) {
      events.push({
        id: `inst-holiday-${h.id}`,
        title: `🏛 ${h.name}`,
        start: h.date,
        end: h.end_date || undefined,
        allDay: true,
        display: "background",
        backgroundColor: "#FDE68A",
        borderColor: "#F59E0B",
        extendedProps: { _source: "inst-holiday", ...h },
      })
    }
  }

  // Semester break and exam period background events
  if (showSemesterBreaks.value) {
    for (const sem of semesters.value) {
      if (sem.break_start && sem.break_end) {
        events.push({
          id: `break-${sem.id}`,
          title: `📅 ${sem.name} Break`,
          start: sem.break_start,
          end: sem.break_end,
          allDay: true,
          display: "background",
          backgroundColor: "#D1FAE5",
          borderColor: "#10B981",
          extendedProps: { _source: "sem-break", semester: sem },
        })
      }
    }
  }

  // Timetable sessions (recurring weekly)
  if (showTimetableSessions.value) {
    const semStart = currentSemester.value?.start_date || `${currentYear}-01-01`
    const semEnd = currentSemester.value?.end_date || `${currentYear}-12-31`
    for (const entry of timetableEntries.value) {
      const slot = entry.time_slot
      if (!slot || slot.is_break) continue
      events.push({
        id: `session-${entry.id}`,
        title: `${entry.course?.code || "?"} · ${entry.room?.code || "TBD"}`,
        daysOfWeek: [DAY_MAP[slot.day] ?? 1],
        startTime: slot.start_time,
        endTime: slot.end_time,
        startRecur: semStart,
        endRecur: semEnd,
        backgroundColor: "#1D4ED8",
        borderColor: "#1E40AF",
        textColor: "#ffffff",
        extendedProps: {
          _source: "session",
          course: entry.course,
          lecturer: entry.lecturer,
          room: entry.room,
          student_group: entry.student_group,
          time_slot: slot,
        },
      })
    }
  }

  return events
})

// FullCalendar options
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
    listWeek: { buttonText: "List" },
    timeGridDay: { buttonText: "Day" },
    timeGridWeek: { buttonText: "Week" },
    dayGridMonth: { buttonText: "Month" },
  },
  nowIndicator: true,
  weekNumbers: false,
  dayMaxEvents: 3,
  moreLinkClick: "popover",
  navLinks: true,
  selectable: auth.isAdmin || auth.isTimetableOfficer,
  selectMirror: true,
  editable: false,
  height: "auto",
  events: [],
  eventClick: handleEventClick,
  select: handleDateSelect,
  eventDidMount(info) {
    if (info.event.extendedProps.is_cancelled) {
      info.el.style.opacity = "0.55"
      const title = info.el.querySelector(".fc-event-title")
      if (title) title.style.textDecoration = "line-through"
    }
  },
})

// Keep events reactive
watchEffect(() => { calendarOptions.events = allEvents.value })

// ─── Data loading ─────────────────────────────────────────────────────────────
async function loadAcademicEvents() {
  try {
    const { data } = await calendarApi.events()
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
    const active = timetableList.value.find((t) => t.status === "active") || timetableList.value[0]
    if (active) {
      selectedTimetable.value = active.id
    }
  } catch { timetableList.value = [] }
}

async function loadTimetableEntries(id) {
  if (!id) { timetableEntries.value = []; return }
  try {
    const { data } = await timetableApi.get(id)
    timetableEntries.value = data.data?.entries || []
  } catch { timetableEntries.value = [] }
}

async function loadPublicHolidays() {
  holidaysLoading.value = true
  try {
    const years = [currentYear - 1, currentYear, currentYear + 1]
    const results = await Promise.allSettled(
      years.map((y) =>
        fetch(`https://date.nager.at/api/v3/PublicHolidays/${y}/${countryCode.value}`)
          .then((r) => (r.ok ? r.json() : []))
          .catch(() => [])
      )
    )
    publicHolidays.value = results
      .filter((r) => r.status === "fulfilled")
      .flatMap((r) => r.value)
      .filter((h) => Array.isArray(h.types) && h.types.includes("Public"))
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

// ─── Event handlers ───────────────────────────────────────────────────────────
function handleEventClick(info) {
  const ep = info.event.extendedProps
  selectedEvent.value = {
    id: info.event.id,
    title: info.event.title.replace(/^✗ /, ""),
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
  createForm.end = info.endStr.slice(0, 16)
  createForm.all_day = info.allDay
  showCreateModal.value = true
}

// ─── CRUD actions ─────────────────────────────────────────────────────────────
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

// ─── Helpers ──────────────────────────────────────────────────────────────────
function closeCreateModal() {
  showCreateModal.value = false
  Object.assign(createForm, {
    title: "", description: "", event_type: "event",
    start: "", end: "", location: "", all_day: false, color: "#10B981", is_public: true,
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
  return new Date(dt).toLocaleDateString(undefined, {
    weekday: "short", month: "long", day: "numeric", year: "numeric",
  })
}

const isCalendarSource = computed(() => selectedEvent.value?._source === "calendar")
const isSessionSource = computed(() => selectedEvent.value?._source === "session")
const canManage = computed(() => auth.isAdmin || auth.isTimetableOfficer)

// ─── Watchers ─────────────────────────────────────────────────────────────────
watch(countryCode, loadPublicHolidays)
watch(selectedTimetable, loadTimetableEntries)

onMounted(async () => {
  loading.value = true
  await Promise.all([loadAcademicEvents(), loadSemesters(), loadTimetables(), loadPublicHolidays(), loadInstitutionalHolidays()])
  loading.value = false
})
</script>

<template>
  <div class="flex flex-col h-full gap-0">
    <!-- ── Page header ─────────────────────────────────────────────────── -->
    <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Academic Calendar</h1>
        <p class="text-sm text-gray-500 mt-0.5">
          <span v-if="currentSemester">
            {{ currentSemester.name }} · {{ currentSemester.academic_year }}
          </span>
          <span v-else>All academic events, sessions, and holidays</span>
        </p>
      </div>
      <div class="flex items-center gap-2">
        <button class="btn-secondary text-sm" @click="showSidebar = !showSidebar">
          {{ showSidebar ? "Hide" : "Show" }} Panel
        </button>
        <a :href="calendarApi.exportIcs()" target="_blank" class="btn-secondary text-sm">Export ICS</a>
        <button v-if="canManage" class="btn-primary text-sm" @click="showCreateModal = true">
          + Create Event
        </button>
      </div>
    </div>

    <!-- ── Main layout ────────────────────────────────────────────────── -->
    <div class="flex gap-4 flex-1 min-h-0">

      <!-- Sidebar -->
      <aside v-if="showSidebar" class="w-64 flex-shrink-0 space-y-4 overflow-y-auto pb-4">

        <!-- Timetable overlay -->
        <div class="card p-4 space-y-3">
          <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Timetable Overlay</h3>
          <label class="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" v-model="showTimetableSessions" class="rounded text-blue-600" />
            <span class="text-gray-700">Show class sessions</span>
          </label>
          <div v-if="showTimetableSessions">
            <label class="label text-xs">Active Timetable</label>
            <select v-model="selectedTimetable" class="input text-sm mt-1">
              <option value="">None</option>
              <option v-for="tt in timetableList" :key="tt.id" :value="tt.id">{{ tt.name }}</option>
            </select>
          </div>
        </div>

        <!-- Public holidays -->
        <div class="card p-4 space-y-3">
          <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Holidays &amp; Breaks</h3>
          <label class="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" v-model="showHolidays" class="rounded text-red-500" />
            <span class="text-gray-700">National holidays</span>
            <span v-if="holidaysLoading" class="text-xs text-gray-400">...</span>
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
            <span class="text-gray-700">Semester breaks</span>
          </label>
        </div>

        <!-- Event type filters -->
        <div class="card p-4 space-y-2">
          <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Event Types</h3>
          <button
            v-for="(cfg, type) in EVENT_TYPES" :key="type"
            class="flex items-center gap-2 w-full text-left rounded-lg px-2 py-1.5 text-sm transition-colors"
            :class="activeFilters.has(type) ? 'opacity-100' : 'opacity-40'"
            @click="toggleFilter(type)"
          >
            <span class="w-3 h-3 rounded-full flex-shrink-0" :style="{ backgroundColor: cfg.color }"></span>
            <span class="text-gray-700">{{ cfg.label }}</span>
            <svg v-if="activeFilters.has(type)" class="ml-auto w-3.5 h-3.5 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
          </button>
          <div class="mt-1 pt-2 border-t border-gray-100 flex gap-2">
            <span class="w-3 h-3 rounded-sm bg-blue-800 inline-block mt-0.5 flex-shrink-0"></span>
            <span class="text-sm text-gray-700">Class sessions</span>
          </div>
        </div>

        <!-- Semester info -->
        <div class="card p-4 space-y-2">
          <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wider">Semesters</h3>
          <div v-if="currentSemester" class="space-y-2">
            <div class="flex items-center gap-1.5">
              <span class="w-2 h-2 rounded-full bg-green-500 flex-shrink-0"></span>
              <p class="text-sm font-semibold text-gray-900 truncate">{{ currentSemester.name }}</p>
            </div>
            <div class="text-xs text-gray-500 space-y-0.5 pl-3.5">
              <p>{{ formatDateOnly(currentSemester.start_date) }}</p>
              <p class="text-gray-400">→ {{ formatDateOnly(currentSemester.end_date) }}</p>
              <div v-if="currentSemester.break_start" class="mt-1.5 pt-1.5 border-t border-gray-100 space-y-0.5">
                <p class="font-medium text-teal-600">Mid-sem Break</p>
                <p>{{ formatDateOnly(currentSemester.break_start) }}</p>
                <p class="text-gray-400">→ {{ formatDateOnly(currentSemester.break_end) }}</p>
              </div>
            </div>
          </div>
          <p v-else class="text-xs text-gray-400">No active semester</p>
          <div class="pt-1 border-t border-gray-100 space-y-1">
            <p v-for="sem in semesters.filter(s => !s.is_current).slice(0, 2)" :key="sem.id"
              class="text-xs text-gray-400 pl-3.5 truncate">
              {{ sem.name }} ({{ sem.academic_year }})
            </p>
          </div>
        </div>
      </aside>

      <!-- Calendar -->
      <div class="flex-1 min-w-0 bg-white rounded-xl border border-gray-200 overflow-hidden calendar-container">
        <div v-if="loading" class="flex items-center justify-center h-96 text-gray-400 text-sm">
          Loading calendar…
        </div>
        <FullCalendar v-else ref="calendarRef" :options="calendarOptions" class="h-full" />
      </div>
    </div>

    <!-- ── Create Event Modal ───────────────────────────────────────────── -->
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
              <input v-model="createForm.title" class="input" placeholder="e.g. Mid-semester Exam" />
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
                <input v-model="createForm.location" class="input" placeholder="Room / Online" />
              </div>
              <div>
                <label class="label">Start</label>
                <input v-model="createForm.start" type="datetime-local" class="input" />
              </div>
              <div>
                <label class="label">End</label>
                <input v-model="createForm.end" type="datetime-local" class="input" />
              </div>
            </div>
            <div>
              <label class="label">Description</label>
              <textarea v-model="createForm.description" rows="3" class="input" placeholder="Optional description…"></textarea>
            </div>
            <div class="flex flex-wrap items-center gap-4">
              <label class="flex items-center gap-2 text-sm cursor-pointer">
                <input v-model="createForm.all_day" type="checkbox" class="rounded text-blue-600" />
                All-day event
              </label>
              <label class="flex items-center gap-2 text-sm cursor-pointer">
                <input v-model="createForm.is_public" type="checkbox" class="rounded text-blue-600" />
                Public
              </label>
              <label class="flex items-center gap-2 text-sm cursor-pointer" title="Mark if this event suppresses regular timetable sessions (e.g. exam period)">
                <input v-model="createForm.affects_timetable" type="checkbox" class="rounded text-purple-600" />
                <span class="text-purple-700 font-medium">Affects timetable</span>
              </label>
            </div>
            <div v-if="createForm.affects_timetable">
              <label class="label">Timetable Scope <span class="text-xs text-gray-400">(department, program, or all)</span></label>
              <input v-model="createForm.timetable_scope" class="input text-sm" placeholder="e.g. all, CS Department, BSc CS" />
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

    <!-- ── Event Detail Modal ──────────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="showDetailModal && selectedEvent" class="modal-backdrop" @click.self="closeDetailModal">
        <div class="modal-box w-full max-w-lg">

          <!-- Header strip coloured by type -->
          <div
            class="px-5 py-4 text-white rounded-t-2xl"
            :style="{ backgroundColor: selectedEvent._source === 'session' ? '#1D4ED8' : (EVENT_TYPES[selectedEvent.event_type]?.color || '#3B82F6') }"
          >
            <div class="flex items-start justify-between gap-2">
              <div>
                <p class="text-xs opacity-75 font-medium uppercase tracking-wide flex flex-wrap items-center gap-1.5">
                  <span>{{ selectedEvent._source === 'session' ? 'Class Session' : (selectedEvent.event_type || 'Event') }}</span>
                  <span v-if="selectedEvent.is_cancelled" class="bg-white/20 rounded px-1.5">CANCELLED</span>
                  <span v-if="selectedEvent.affects_timetable" class="bg-purple-500/80 rounded px-1.5 text-white">⚡ AFFECTS TIMETABLE</span>
                </p>
                <h2 class="text-xl font-bold mt-0.5">{{ selectedEvent.title }}</h2>
              </div>
              <button @click="closeDetailModal" class="text-white opacity-75 hover:opacity-100 text-2xl leading-none">✕</button>
            </div>
          </div>

          <div class="p-5 space-y-4">

            <!-- Session details -->
            <template v-if="isSessionSource">
              <div class="grid grid-cols-2 gap-3 text-sm">
                <div class="info-chip">
                  <p class="info-label">Course</p>
                  <p class="info-val">{{ selectedEvent.course?.name }}</p>
                  <p class="text-xs text-gray-400">{{ selectedEvent.course?.code }}</p>
                </div>
                <div class="info-chip">
                  <p class="info-label">Time</p>
                  <p class="info-val">{{ selectedEvent.time_slot?.day }}</p>
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
                Cancellation reason: {{ selectedEvent.cancellation_reason }}
              </p>
              <div v-if="selectedEvent.affects_timetable" class="text-sm bg-purple-50 border border-purple-200 rounded-lg p-3 space-y-1">
                <p class="font-semibold text-purple-900 flex items-center gap-1.5">
                  <span>⚡</span> Affects Timetable Sessions
                </p>
                <p v-if="selectedEvent.timetable_scope" class="text-purple-700 text-xs">
                  Scope: {{ selectedEvent.timetable_scope }}
                </p>
                <p class="text-purple-600 text-xs">Regular sessions during this event are suppressed and displayed as cancelled.</p>
              </div>
            </template>

            <!-- Holiday details -->
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
                  <input v-model="reminderForm.scheduled_at" type="datetime-local" class="input text-sm" />
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
              <input v-model="cancelReason" class="input text-sm" placeholder="Reason for cancellation (optional)" />
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
                <button v-if="!selectedEvent.is_cancelled" class="btn-secondary text-sm text-orange-600 border-orange-200 hover:bg-orange-50" @click="showCancelForm = true">
                  Cancel Event
                </button>
                <button v-else class="btn-secondary text-sm text-green-600 border-green-200 hover:bg-green-50" @click="uncancelSelectedEvent">
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
  </div>
</template>

<style scoped>
/* FullCalendar overrides */
.calendar-container :deep(.fc) {
  font-family: inherit;
}
.calendar-container :deep(.fc-toolbar-title) {
  font-size: 1.125rem;
  font-weight: 700;
  color: #111827;
}
.calendar-container :deep(.fc-button) {
  background-color: #f9fafb;
  border: 1px solid #e5e7eb;
  color: #374151;
  font-weight: 500;
  font-size: 0.8125rem;
  padding: 0.375rem 0.75rem;
  border-radius: 0.5rem;
  transition: all 0.15s;
  text-transform: capitalize;
  box-shadow: none !important;
}
.calendar-container :deep(.fc-button:hover) {
  background-color: #f3f4f6;
  border-color: #d1d5db;
  color: #111827;
}
.calendar-container :deep(.fc-button-active),
.calendar-container :deep(.fc-button-primary:not(:disabled).fc-button-active) {
  background-color: #2563eb !important;
  border-color: #1d4ed8 !important;
  color: #fff !important;
}
.calendar-container :deep(.fc-button-group .fc-button) {
  border-radius: 0;
}
.calendar-container :deep(.fc-button-group .fc-button:first-child) {
  border-radius: 0.5rem 0 0 0.5rem;
}
.calendar-container :deep(.fc-button-group .fc-button:last-child) {
  border-radius: 0 0.5rem 0.5rem 0;
}
.calendar-container :deep(.fc-daygrid-day.fc-day-today) {
  background-color: #eff6ff;
}
.calendar-container :deep(.fc-timegrid-col.fc-day-today) {
  background-color: #eff6ff;
}
.calendar-container :deep(.fc-event) {
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
}
.calendar-container :deep(.fc-event-affects-timetable) {
  border-left-width: 3px !important;
  border-left-color: #7C3AED !important;
}
.calendar-container :deep(.fc-daygrid-event) {
  padding: 1px 4px;
}
.calendar-container :deep(.fc-list-event:hover td) {
  background-color: #f3f4f6;
  cursor: pointer;
}
.calendar-container :deep(.fc-multimonth-month) {
  border-color: #e5e7eb;
}
.calendar-container :deep(.fc-toolbar) {
  padding: 1rem 1rem 0;
}
.calendar-container :deep(.fc-view-harness) {
  min-height: 500px;
}

/* Modal styles */
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}
.modal-box {
  background: #fff;
  border-radius: 1rem;
  box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25);
  overflow: hidden;
  max-height: 90vh;
  overflow-y: auto;
}
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.25rem 1.25rem 0;
}
.modal-close {
  width: 2rem;
  height: 2rem;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  transition: all 0.15s;
  font-size: 0.875rem;
}
.modal-close:hover { background: #f3f4f6; color: #111827; }
.modal-body { padding: 1rem 1.25rem; }
.modal-footer {
  padding: 1rem 1.25rem;
  border-top: 1px solid #f3f4f6;
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
.info-chip {
  background: #f9fafb;
  border-radius: 0.5rem;
  padding: 0.625rem 0.75rem;
}
.info-label {
  font-size: 0.6875rem;
  font-weight: 500;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.125rem;
}
.info-val {
  font-weight: 600;
  color: #111827;
  font-size: 0.875rem;
}
</style>
