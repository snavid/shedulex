<script setup>
import { computed, onMounted, ref, watch } from "vue"
import { useRoute } from "vue-router"
import { useToast } from "vue-toastification"
import {
  getErrorMessage,
  getPortalToken,
  portalApi,
  setPortalToken,
  validatePhone,
} from "@/api/client"
import ReminderSheet from "@/components/ReminderSheet.vue"
import {
  buildSessionReminderPayload,
  formatReminderTime,
  leadLabel,
  pendingCountForEntry,
  remindersForEntry,
} from "@/utils/sessionReminders"

const route = useRoute()
const toast = useToast()

const uniCode = computed(() => (route.params.uniCode || "").toUpperCase())
const activeTab = ref("timetable")
const authenticated = ref(!!getPortalToken())
const loading = ref(false)
const portalUser = ref(null)

const loginForm = ref({ registration_number: "", phone_last4: "" })
const subscribeForm = ref({ phone: "", email: "" })
const savingSubscribe = ref(false)

const timetableEntries = ref([])
const commentSessionEntries = ref([])
const availableSemesters = ref([])
const selectedSemester = ref(null)
const selectedTimetableId = ref(null)
const timetableLoading = ref(false)
const comments = ref([])
const commentForm = ref({ entry_id: "", body: "" })
const postingComment = ref(false)

const pendingReminders = ref([])
const loadingReminders = ref(false)
const showReminderSheet = ref(false)
const selectedReminderEntry = ref(null)
const savingReminder = ref(false)
const cancellingReminderId = ref(null)

const tabs = [
  {
    id: "timetable",
    label: "Timetable",
    desc: "Your weekly schedule",
    icon: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
  },
  {
    id: "notifications",
    label: "Reminders",
    desc: "Class alerts & contact",
    icon: "M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9",
  },
  {
    id: "comments",
    label: "Feedback",
    desc: "Comments on classes",
    icon: "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z",
  },
]

const DAY_THEME = {
  Monday: { stripe: "border-l-violet-500", badge: "bg-violet-100 text-violet-700", dot: "bg-violet-500" },
  Tuesday: { stripe: "border-l-blue-500", badge: "bg-blue-100 text-blue-700", dot: "bg-blue-500" },
  Wednesday: { stripe: "border-l-emerald-500", badge: "bg-emerald-100 text-emerald-700", dot: "bg-emerald-500" },
  Thursday: { stripe: "border-l-amber-500", badge: "bg-amber-100 text-amber-700", dot: "bg-amber-500" },
  Friday: { stripe: "border-l-rose-500", badge: "bg-rose-100 text-rose-700", dot: "bg-rose-500" },
  Saturday: { stripe: "border-l-indigo-500", badge: "bg-indigo-100 text-indigo-700", dot: "bg-indigo-500" },
}

const selectedSemesterMeta = computed(() =>
  availableSemesters.value.find((s) => s.timetable_id === selectedTimetableId.value)
    || availableSemesters.value.find((s) => s.semester === selectedSemester.value)
)

const canSwitchSemester = computed(() => availableSemesters.value.length > 1)

const userInitials = computed(() => {
  const first = portalUser.value?.first_name?.[0] || ""
  const last = portalUser.value?.last_name?.[0] || ""
  return (first + last).toUpperCase() || "ST"
})

const todayName = computed(() =>
  new Date().toLocaleDateString("en-US", { weekday: "long" })
)

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 12) return "Good morning"
  if (hour < 17) return "Good afternoon"
  return "Good evening"
})

const formattedDate = computed(() =>
  new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  })
)

const totalSessions = computed(() => timetableEntries.value.length)

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

const groupedTimetable = computed(() => {
  const map = {}
  for (const day of DAYS) map[day] = []
  for (const entry of timetableEntries.value) {
    const day = entry.time_slot?.day
    if (day && map[day]) map[day].push(entry)
  }
  for (const day of DAYS) {
    map[day].sort((a, b) => (a.time_slot?.start_time || "").localeCompare(b.time_slot?.start_time || ""))
  }
  return map
})

const activeDays = computed(() => DAYS.filter((day) => groupedTimetable.value[day]?.length))

const todaySessions = computed(() => groupedTimetable.value[todayName.value] || [])

const nextSessionToday = computed(() => {
  const now = new Date()
  const nowStr = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`
  return todaySessions.value.find((e) => (e.time_slot?.start_time || "") >= nowStr) || null
})

const semesterEndDate = computed(() => selectedSemesterMeta.value?.end_date || null)

const portalContact = computed(() => ({
  phone: portalUser.value?.phone || subscribeForm.value.phone || "",
  email: portalUser.value?.email || subscribeForm.value.email || "",
}))

const sheetExistingReminders = computed(() => {
  if (!selectedReminderEntry.value) return []
  return remindersForEntry(pendingReminders.value, selectedReminderEntry.value.id)
})

const sortedPendingReminders = computed(() =>
  [...pendingReminders.value]
    .filter(r => r.status === "pending")
    .sort((a, b) => new Date(a.scheduled_at) - new Date(b.scheduled_at))
)

function reminderCount(entryId) {
  return pendingCountForEntry(pendingReminders.value, entryId)
}

function reminderApiError(e, fallback) {
  if (e?.response?.status === 404) {
    return "Reminder service not available. Backend may need a restart."
  }
  return getErrorMessage(e, fallback)
}

async function loadPendingReminders() {
  if (!getPortalToken()) return
  loadingReminders.value = true
  try {
    const { data } = await portalApi.reminders.list({ status: "pending" })
    pendingReminders.value = data.data || []
  } catch (e) {
    pendingReminders.value = []
    if (e?.response?.status === 404) {
      toast.warning("Reminder service not available. Backend may need a restart.")
    }
  } finally {
    loadingReminders.value = false
  }
}

function openReminderSheet(entry) {
  selectedReminderEntry.value = entry
  showReminderSheet.value = true
}

async function handleReminderSave({ channel, leadTimes, phone, occurrence, repeatWeeklyUntil }) {
  if (!selectedReminderEntry.value || !occurrence) return

  savingReminder.value = true
  try {
    if (phone && !portalUser.value?.phone?.trim()) {
      const phoneError = validatePhone(phone)
      if (phoneError) {
        toast.error(phoneError)
        return
      }
      const { data } = await portalApi.subscribe({ phone })
      portalUser.value = { ...portalUser.value, ...data.data }
      subscribeForm.value.phone = data.data.phone || phone
    }

    const payload = buildSessionReminderPayload(selectedReminderEntry.value, {
      channel,
      leadTimes,
      occurrenceDate: occurrence,
      repeatWeeklyUntil,
    })
    const { data } = await portalApi.reminders.create(payload)
    toast.success(data.message || "Reminder(s) scheduled.")
    showReminderSheet.value = false
    await loadPendingReminders()
  } catch (e) {
    toast.error(reminderApiError(e, "Failed to set reminder."))
  } finally {
    savingReminder.value = false
  }
}

async function cancelReminder(reminderId) {
  cancellingReminderId.value = reminderId
  try {
    await portalApi.reminders.cancel(reminderId)
    pendingReminders.value = pendingReminders.value.filter(r => r.id !== reminderId)
    toast.success("Reminder cancelled.")
  } catch (e) {
    toast.error(reminderApiError(e, "Failed to cancel reminder."))
  } finally {
    cancellingReminderId.value = null
  }
}

function goToAlertsTab() {
  showReminderSheet.value = false
  activeTab.value = "notifications"
}

async function login() {
  if (!loginForm.value.registration_number?.trim() || loginForm.value.phone_last4?.length !== 4) {
    toast.error("Enter your registration number and the last 4 digits of your phone.")
    return
  }
  loading.value = true
  try {
    const { data } = await portalApi.session({
      university_code: uniCode.value,
      registration_number: loginForm.value.registration_number.trim(),
      phone_last4: loginForm.value.phone_last4.trim(),
    })
    setPortalToken(data.data.access_token)
    portalUser.value = data.data.user
    authenticated.value = true
    subscribeForm.value.phone = portalUser.value.phone || ""
    subscribeForm.value.email = portalUser.value.email || ""
    await loadPortalData()
    toast.success(`Welcome, ${portalUser.value.first_name}!`)
  } catch (e) {
    toast.error(getErrorMessage(e, "Login failed. Check your details and try again."))
  } finally {
    loading.value = false
  }
}

function logout() {
  setPortalToken(null)
  authenticated.value = false
  portalUser.value = null
  timetableEntries.value = []
  commentSessionEntries.value = []
  availableSemesters.value = []
  selectedSemester.value = null
  selectedTimetableId.value = null
  comments.value = []
  pendingReminders.value = []
}

async function loadTimetableForSelection(timetableId) {
  const meta = availableSemesters.value.find((s) => s.timetable_id === timetableId)
  const params = { timetable_id: timetableId }
  if (meta?.semester != null) params.semester = meta.semester
  const { data } = await portalApi.timetable(params)
  timetableEntries.value = data.data || []
  if (meta) selectedSemester.value = meta.semester
}

async function switchSemester(timetableId) {
  if (!timetableId || selectedTimetableId.value === timetableId) return
  selectedTimetableId.value = timetableId
  timetableLoading.value = true
  try {
    await loadTimetableForSelection(timetableId)
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load timetable."))
  } finally {
    timetableLoading.value = false
  }
}

async function loadAllCommentSessions() {
  if (!availableSemesters.value.length) {
    commentSessionEntries.value = []
    return
  }
  const results = await Promise.all(
    availableSemesters.value.map((s) =>
      portalApi.timetable({ timetable_id: s.timetable_id, semester: s.semester })
    )
  )
  commentSessionEntries.value = results.flatMap((res) => res.data.data || [])
}

async function portalApiWithRetry(fn, retries = 1) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn()
    } catch (e) {
      const status = e?.response?.status
      const retryable = [502, 503, 504].includes(status)
      if (!retryable || attempt >= retries) throw e
      await new Promise(r => setTimeout(r, 1500))
    }
  }
}

async function loadCommentsOptional() {
  try {
    const { data } = await portalApiWithRetry(() => portalApi.comments())
    comments.value = data.data || []
  } catch {
    comments.value = []
  }
}

async function loadPortalData() {
  if (!getPortalToken()) return
  loading.value = true
  try {
    const semRes = await portalApiWithRetry(() => portalApi.timetableSemesters())
    availableSemesters.value = semRes.data.data || []

    if (availableSemesters.value.length) {
      const current = selectedTimetableId.value
      const stillValid = availableSemesters.value.some((s) => s.timetable_id === current)
      selectedTimetableId.value = stillValid
        ? current
        : availableSemesters.value[0].timetable_id
      await loadTimetableForSelection(selectedTimetableId.value)
      loadAllCommentSessions().catch(() => { commentSessionEntries.value = [] })
      loadPendingReminders()
      loadCommentsOptional()
    } else {
      timetableEntries.value = []
      commentSessionEntries.value = []
      selectedSemester.value = null
      selectedTimetableId.value = null
      loadCommentsOptional()
      loadPendingReminders()
    }
  } catch (e) {
    if (e?.response?.status === 401) logout()
    else if ([502, 503, 504].includes(e?.response?.status)) {
      toast.error("Timetable service is restarting. Wait a moment and refresh.")
    } else {
      toast.error(getErrorMessage(e, "Failed to load portal data."))
    }
  } finally {
    loading.value = false
  }
}

async function saveSubscribe() {
  const phoneError = subscribeForm.value.phone ? validatePhone(subscribeForm.value.phone) : null
  if (phoneError) {
    toast.error(phoneError)
    return
  }
  savingSubscribe.value = true
  try {
    const payload = {}
    if (subscribeForm.value.phone?.trim()) payload.phone = subscribeForm.value.phone.trim()
    if (subscribeForm.value.email?.trim()) payload.email = subscribeForm.value.email.trim()
    const { data } = await portalApi.subscribe(payload)
    portalUser.value = { ...portalUser.value, ...data.data }
    toast.success("Notification preferences updated.")
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to update preferences."))
  } finally {
    savingSubscribe.value = false
  }
}

async function submitComment() {
  if (!commentForm.value.entry_id) {
    toast.error("Select a class session.")
    return
  }
  if (!commentForm.value.body?.trim()) {
    toast.error("Enter your comment.")
    return
  }
  postingComment.value = true
  try {
    const { data } = await portalApi.createComment({
      entry_id: commentForm.value.entry_id,
      body: commentForm.value.body.trim(),
    })
    comments.value.unshift(data.data)
    commentForm.value = { entry_id: "", body: "" }
    toast.success("Comment submitted.")
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to submit comment."))
  } finally {
    postingComment.value = false
  }
}

function sessionLabel(entry) {
  const slot = entry.time_slot
  const course = entry.course?.name || entry.course?.code || "Class"
  const sem = entry.semester ? `Sem ${entry.semester} · ` : ""
  return `${sem}${slot?.day || "?"} ${slot?.start_time || ""} — ${course}`
}

function semesterLabel(sem) {
  const parts = [`Semester ${sem.semester}`]
  if (sem.academic_year) parts.push(sem.academic_year)
  if (sem.name) parts.push(sem.name)
  return parts.join(" · ")
}

function shortSemesterLabel(sem) {
  return sem.name || `Semester ${sem.semester}`
}

function dayTheme(day) {
  return DAY_THEME[day] || DAY_THEME.Monday
}

watch(activeTab, (tab) => {
  if (authenticated.value && tab === "notifications") loadPendingReminders()
})

onMounted(() => {
  if (authenticated.value) loadPortalData()
})
</script>

<template>
  <div class="portal-page min-h-screen bg-slate-50 text-slate-900">
    <div class="portal-decor" aria-hidden="true">
      <div class="portal-decor-blob portal-decor-blob-a" />
      <div class="portal-decor-blob portal-decor-blob-b" />
    </div>

    <!-- Header -->
    <header class="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 backdrop-blur-md">
      <div class="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3.5 sm:px-6">
        <div class="flex min-w-0 items-center gap-3">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-lg text-white shadow-md shadow-blue-600/25">
            📅
          </div>
          <div class="min-w-0">
            <p class="text-[10px] font-bold uppercase tracking-[0.18em] text-blue-600">Shedulex</p>
            <h1 class="truncate text-base font-bold text-slate-900 sm:text-lg">{{ uniCode }} · Student Portal</h1>
          </div>
        </div>

        <button
          v-if="authenticated"
          class="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 shadow-sm transition hover:border-slate-300 hover:text-slate-900"
          @click="logout"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          <span class="hidden sm:inline">Sign out</span>
        </button>
      </div>
    </header>

    <main class="relative mx-auto max-w-5xl px-4 pb-28 pt-6 sm:px-6 sm:pb-10 sm:pt-8">
      <!-- ── Login ── -->
      <section v-if="!authenticated" class="mx-auto max-w-4xl">
        <div class="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl shadow-slate-200/60 lg:grid lg:grid-cols-5">
          <!-- Brand panel -->
          <div class="relative overflow-hidden bg-gradient-to-br from-blue-600 via-blue-700 to-indigo-800 px-8 py-10 text-white lg:col-span-2">
            <div class="absolute -right-8 -top-8 h-40 w-40 rounded-full bg-white/10 blur-2xl" />
            <div class="absolute -bottom-12 -left-8 h-48 w-48 rounded-full bg-indigo-400/20 blur-3xl" />
            <div class="relative">
              <div class="mb-6 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-white/15 text-3xl ring-1 ring-white/25 backdrop-blur">
                🎓
              </div>
              <h2 class="text-2xl font-bold leading-tight">{{ uniCode }} University</h2>
              <p class="mt-3 text-sm leading-relaxed text-blue-100">
                Access your class timetable, manage alerts, and send feedback — all in one place.
              </p>
              <ul class="mt-8 space-y-3 text-sm text-blue-50">
                <li class="flex items-center gap-2.5">
                  <span class="flex h-6 w-6 items-center justify-center rounded-full bg-white/15 text-xs">✓</span>
                  View weekly schedule by semester
                </li>
                <li class="flex items-center gap-2.5">
                  <span class="flex h-6 w-6 items-center justify-center rounded-full bg-white/15 text-xs">✓</span>
                  Get SMS & email announcements
                </li>
                <li class="flex items-center gap-2.5">
                  <span class="flex h-6 w-6 items-center justify-center rounded-full bg-white/15 text-xs">✓</span>
                  Share feedback on class sessions
                </li>
              </ul>
            </div>
          </div>

          <!-- Form panel -->
          <div class="px-6 py-8 sm:px-10 sm:py-10 lg:col-span-3">
            <div class="mx-auto max-w-sm">
              <h3 class="text-xl font-bold text-slate-900">Sign in</h3>
              <p class="mt-1.5 text-sm text-slate-500">
                Use your registration number and the last 4 digits of your phone on file.
              </p>

              <form class="mt-8 space-y-5" @submit.prevent="login">
                <div>
                  <label class="label">Registration number</label>
                  <div class="relative">
                    <span class="pointer-events-none absolute inset-y-0 left-3.5 flex items-center text-slate-400">
                      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M10 6H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V8a2 2 0 00-2-2h-5m-4 0V5a2 2 0 114 0v1m-4 0a2 2 0 104 0" />
                      </svg>
                    </span>
                    <input
                      v-model="loginForm.registration_number"
                      class="input pl-10"
                      placeholder="REG2026001"
                      autocomplete="username"
                    />
                  </div>
                </div>

                <div>
                  <label class="label">Phone — last 4 digits</label>
                  <div class="relative">
                    <span class="pointer-events-none absolute inset-y-0 left-3.5 flex items-center text-slate-400">
                      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
                      </svg>
                    </span>
                    <input
                      v-model="loginForm.phone_last4"
                      maxlength="4"
                      inputmode="numeric"
                      class="input pl-10 tracking-[0.3em] font-medium"
                      placeholder="••••"
                      autocomplete="one-time-code"
                    />
                  </div>
                  <p class="mt-1.5 text-xs text-slate-400">The same number your university registered for you.</p>
                </div>

                <button type="submit" class="btn-primary flex w-full items-center justify-center gap-2 py-3" :disabled="loading">
                  <svg v-if="loading" class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  {{ loading ? "Signing in…" : "Continue to portal" }}
                </button>
              </form>
            </div>
          </div>
        </div>
      </section>

      <!-- ── Authenticated ── -->
      <section v-else class="space-y-6">
        <!-- Welcome hero -->
        <div class="welcome-hero overflow-hidden rounded-2xl border border-blue-100 bg-gradient-to-r from-blue-50 via-white to-indigo-50 p-5 shadow-sm sm:p-6">
          <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div class="flex items-center gap-4">
              <div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-lg font-bold text-white shadow-lg shadow-blue-600/30">
                {{ userInitials }}
              </div>
              <div>
                <p class="text-sm font-medium text-blue-600">{{ formattedDate }}</p>
                <h2 class="text-xl font-bold text-slate-900 sm:text-2xl">
                  {{ greeting }}, {{ portalUser?.first_name }}!
                </h2>
                <p class="mt-0.5 text-sm text-slate-500">{{ portalUser?.registration_number }}</p>
              </div>
            </div>

            <div v-if="activeTab === 'timetable' && nextSessionToday" class="rounded-xl border border-blue-200 bg-white/80 px-4 py-3 shadow-sm">
              <div class="flex items-start justify-between gap-3">
                <div>
                  <p class="text-[11px] font-semibold uppercase tracking-wider text-blue-600">Up next today</p>
                  <p class="mt-0.5 font-semibold text-slate-900">
                    {{ nextSessionToday.course?.name || nextSessionToday.course?.code }}
                  </p>
                  <p class="text-xs text-slate-500">
                    {{ nextSessionToday.time_slot?.start_time }} – {{ nextSessionToday.time_slot?.end_time }}
                    · {{ nextSessionToday.room?.name || "TBA" }}
                  </p>
                </div>
                <button
                  type="button"
                  class="shrink-0 rounded-xl bg-blue-600 px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700"
                  @click="openReminderSheet(nextSessionToday)"
                >
                  Remind me
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Desktop navigation -->
        <nav class="hidden gap-3 sm:grid sm:grid-cols-3">
          <button
            v-for="tab in tabs"
            :key="tab.id"
            class="group rounded-2xl border p-4 text-left transition"
            :class="activeTab === tab.id
              ? 'border-blue-200 bg-white shadow-md shadow-blue-100/80 ring-1 ring-blue-100'
              : 'border-slate-200 bg-white/70 hover:border-slate-300 hover:bg-white hover:shadow-sm'"
            @click="activeTab = tab.id"
          >
            <div class="flex items-center gap-3">
              <span
                class="flex h-10 w-10 items-center justify-center rounded-xl transition"
                :class="activeTab === tab.id ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-500 group-hover:bg-blue-50 group-hover:text-blue-600'"
              >
                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" :d="tab.icon" />
                </svg>
              </span>
              <div>
                <p class="font-semibold text-slate-900">{{ tab.label }}</p>
                <p class="text-xs text-slate-500">{{ tab.desc }}</p>
              </div>
            </div>
          </button>
        </nav>

        <!-- Loading skeleton -->
        <div v-if="loading" class="space-y-4">
          <div class="grid gap-3 sm:grid-cols-3">
            <div v-for="i in 3" :key="i" class="h-20 animate-pulse rounded-2xl bg-white ring-1 ring-slate-200" />
          </div>
          <div class="space-y-3">
            <div v-for="i in 3" :key="i" class="h-28 animate-pulse rounded-2xl bg-white ring-1 ring-slate-200" />
          </div>
        </div>

        <!-- Timetable -->
        <div v-else-if="activeTab === 'timetable'" class="space-y-5">
          <!-- Stats -->
          <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div class="stat-card">
              <p class="stat-label">Sessions</p>
              <p class="stat-value text-blue-600">{{ totalSessions }}</p>
            </div>
            <div class="stat-card">
              <p class="stat-label">Days</p>
              <p class="stat-value text-indigo-600">{{ activeDays.length }}</p>
            </div>
            <div class="stat-card">
              <p class="stat-label">Today</p>
              <p class="stat-value text-emerald-600">{{ todaySessions.length }}</p>
            </div>
            <div class="stat-card col-span-2 sm:col-span-1">
              <p class="stat-label">Semester</p>
              <p class="stat-value truncate text-sm sm:text-2xl sm:font-bold">
                {{ selectedSemesterMeta ? shortSemesterLabel(selectedSemesterMeta) : "—" }}
              </p>
            </div>
          </div>

          <!-- Semester switcher -->
          <div
            v-if="availableSemesters.length"
            class="sticky top-[52px] z-20 overflow-hidden rounded-2xl border border-blue-100 bg-white shadow-md shadow-blue-100/50"
          >
            <div class="flex flex-col gap-3 border-b border-slate-100 bg-gradient-to-r from-blue-50 to-indigo-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
              <div class="flex items-center gap-2">
                <svg class="h-5 w-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <div>
                  <p class="text-sm font-semibold text-slate-900">
                    {{ canSwitchSemester ? "Switch semester" : "Your timetable" }}
                  </p>
                  <p v-if="selectedSemesterMeta" class="text-xs text-slate-500">
                    {{ semesterLabel(selectedSemesterMeta) }}
                  </p>
                </div>
              </div>

              <div v-if="canSwitchSemester" class="flex flex-col gap-2 sm:flex-row sm:items-center">
                <select
                  class="input max-w-full sm:min-w-[220px]"
                  :value="selectedTimetableId"
                  @change="switchSemester($event.target.value)"
                >
                  <option
                    v-for="sem in availableSemesters"
                    :key="sem.timetable_id"
                    :value="sem.timetable_id"
                  >
                    {{ semesterLabel(sem) }}
                  </option>
                </select>
              </div>
            </div>

            <div v-if="canSwitchSemester" class="flex flex-wrap gap-2 px-4 py-3 sm:px-5">
              <button
                v-for="sem in availableSemesters"
                :key="sem.timetable_id"
                class="rounded-full px-4 py-2 text-sm font-semibold transition"
                :class="selectedTimetableId === sem.timetable_id
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-600/25'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'"
                :disabled="timetableLoading"
                @click="switchSemester(sem.timetable_id)"
              >
                {{ shortSemesterLabel(sem) }}
              </button>
              <span v-if="timetableLoading" class="inline-flex items-center gap-1.5 self-center text-xs text-slate-500">
                <svg class="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Loading…
              </span>
            </div>
          </div>

          <!-- Empty state -->
          <div v-if="!timetableLoading && !timetableEntries.length" class="card py-16 text-center">
            <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 text-3xl">
              📭
            </div>
            <h3 class="text-lg font-semibold text-slate-900">No classes scheduled</h3>
            <p class="mx-auto mt-2 max-w-sm text-sm text-slate-500">
              There is no active timetable for your group
              <span v-if="selectedSemester"> in semester {{ selectedSemester }}</span>.
              Check back later or contact your department.
            </p>
          </div>

          <!-- Day sections -->
          <div
            v-if="timetableLoading"
            class="space-y-3"
          >
            <div v-for="i in 3" :key="i" class="h-28 animate-pulse rounded-2xl bg-white ring-1 ring-slate-200" />
          </div>

          <template v-else>
            <div
              v-for="day in activeDays"
              :key="day"
              class="overflow-hidden rounded-2xl border bg-white shadow-sm"
              :class="day === todayName ? 'border-blue-200 ring-2 ring-blue-100' : 'border-slate-200'"
            >
            <div class="flex items-center justify-between border-b px-5 py-4" :class="day === todayName ? 'border-blue-100 bg-blue-50/50' : 'border-slate-100 bg-slate-50/50'">
              <div class="flex items-center gap-3">
                <span class="h-2.5 w-2.5 rounded-full" :class="dayTheme(day).dot" />
                <div>
                  <h3 class="font-semibold text-slate-900">{{ day }}</h3>
                  <p class="text-xs text-slate-500">
                    {{ groupedTimetable[day].length }} class{{ groupedTimetable[day].length === 1 ? "" : "es" }}
                  </p>
                </div>
              </div>
              <span
                v-if="day === todayName"
                class="rounded-full bg-blue-600 px-3 py-1 text-xs font-semibold text-white"
              >
                Today
              </span>
            </div>

            <div class="divide-y divide-slate-100">
              <article
                v-for="entry in groupedTimetable[day]"
                :key="entry.id"
                class="flex gap-4 border-l-4 px-5 py-4 transition hover:bg-slate-50/80"
                :class="dayTheme(day).stripe"
              >
                <div class="hidden w-24 shrink-0 sm:block">
                  <p class="text-sm font-bold text-slate-900">{{ entry.time_slot?.start_time }}</p>
                  <p class="text-xs text-slate-400">{{ entry.time_slot?.end_time }}</p>
                </div>

                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <span class="mb-1.5 inline-flex rounded-md px-2 py-0.5 text-[11px] font-semibold sm:hidden" :class="dayTheme(day).badge">
                        {{ entry.time_slot?.start_time }} – {{ entry.time_slot?.end_time }}
                      </span>
                      <h4 class="text-base font-semibold text-slate-900">
                        {{ entry.course?.name || entry.course?.code }}
                      </h4>
                      <p v-if="entry.course?.code && entry.course?.name" class="text-xs font-medium text-slate-400">
                        {{ entry.course.code }}
                      </p>
                    </div>
                    <button
                      type="button"
                      class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border transition"
                      :class="reminderCount(entry.id)
                        ? 'border-blue-300 bg-blue-50 text-blue-600'
                        : 'border-slate-200 bg-white text-slate-400 hover:border-blue-200 hover:text-blue-600'"
                      :title="reminderCount(entry.id) ? 'Reminders set' : 'Set reminder'"
                      @click="openReminderSheet(entry)"
                    >
                      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                      </svg>
                    </button>
                  </div>

                  <div class="mt-3 flex flex-wrap gap-2">
                    <span class="meta-chip">
                      <svg class="h-3.5 w-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                      </svg>
                      {{ entry.lecturer?.name || "TBA" }}
                    </span>
                    <span class="meta-chip">
                      <svg class="h-3.5 w-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                      </svg>
                      {{ entry.room?.name || "TBA" }}
                    </span>
                  </div>
                </div>
              </article>
            </div>
          </div>
          </template>
        </div>

        <!-- Reminders & Alerts -->
        <div v-else-if="activeTab === 'notifications'" class="mx-auto max-w-xl space-y-5">
          <div class="card">
            <div class="mb-6 flex items-start gap-4">
              <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-amber-100 text-2xl">
                🔔
              </div>
              <div>
                <h2 class="text-lg font-bold text-slate-900">Reminders &amp; Alerts</h2>
                <p class="mt-1 text-sm text-slate-500">
                  Set class reminders and keep your SMS/email contact up to date.
                </p>
              </div>
            </div>

            <div class="mb-6 grid grid-cols-2 gap-3">
              <div class="rounded-xl border border-slate-200 bg-slate-50 p-3 text-center">
                <p class="text-xs font-medium text-slate-500">SMS</p>
                <p class="mt-1 text-sm font-semibold" :class="subscribeForm.phone ? 'text-emerald-600' : 'text-slate-400'">
                  {{ subscribeForm.phone ? "Configured" : "Not set" }}
                </p>
              </div>
              <div class="rounded-xl border border-slate-200 bg-slate-50 p-3 text-center">
                <p class="text-xs font-medium text-slate-500">Email</p>
                <p class="mt-1 text-sm font-semibold" :class="subscribeForm.email ? 'text-emerald-600' : 'text-slate-400'">
                  {{ subscribeForm.email ? "Configured" : "Not set" }}
                </p>
              </div>
            </div>

            <div class="space-y-4">
              <div>
                <label class="label">Phone (SMS)</label>
                <div class="relative">
                  <span class="pointer-events-none absolute inset-y-0 left-3.5 flex items-center text-slate-400">
                    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                    </svg>
                  </span>
                  <input v-model="subscribeForm.phone" class="input pl-10" placeholder="+255749300606" />
                </div>
              </div>

              <div>
                <label class="label">Email (optional)</label>
                <div class="relative">
                  <span class="pointer-events-none absolute inset-y-0 left-3.5 flex items-center text-slate-400">
                    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                  </span>
                  <input v-model="subscribeForm.email" type="email" class="input pl-10" placeholder="you@university.ac" />
                </div>
              </div>

              <button class="btn-primary" :disabled="savingSubscribe" @click="saveSubscribe">
                {{ savingSubscribe ? "Saving…" : "Save preferences" }}
              </button>
            </div>
          </div>

          <div class="card">
            <div class="mb-4 flex items-center justify-between gap-3">
              <div>
                <h3 class="font-bold text-slate-900">Your upcoming reminders</h3>
                <p class="text-sm text-slate-500">Scheduled alerts before your classes.</p>
              </div>
              <span v-if="sortedPendingReminders.length" class="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-semibold text-blue-700">
                {{ sortedPendingReminders.length }}
              </span>
            </div>

            <div v-if="loadingReminders" class="py-8 text-center text-sm text-slate-500">Loading reminders…</div>

            <div v-else-if="sortedPendingReminders.length" class="space-y-2">
              <div
                v-for="rem in sortedPendingReminders"
                :key="rem.id"
                class="flex items-start justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50/80 px-4 py-3"
              >
                <div class="min-w-0">
                  <p class="truncate font-semibold text-slate-900">{{ rem.event_title }}</p>
                  <p class="mt-0.5 text-xs text-slate-500">
                    {{ leadLabel(rem.lead_minutes) }} · {{ rem.channel?.toUpperCase() }}
                  </p>
                  <p class="mt-1 text-xs text-slate-400">{{ formatReminderTime(rem.scheduled_at) }}</p>
                </div>
                <button
                  type="button"
                  class="shrink-0 text-xs font-semibold text-red-600 hover:underline"
                  :disabled="cancellingReminderId === rem.id"
                  @click="cancelReminder(rem.id)"
                >
                  {{ cancellingReminderId === rem.id ? "…" : "Cancel" }}
                </button>
              </div>
            </div>

            <div v-else class="py-10 text-center">
              <div class="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-2xl">⏰</div>
              <p class="font-medium text-slate-700">No reminders yet</p>
              <p class="mt-1 text-sm text-slate-500">Tap the bell on any class in your timetable to get reminded.</p>
            </div>
          </div>
        </div>

        <!-- Comments -->
        <div v-else-if="activeTab === 'comments'" class="space-y-5 lg:grid lg:grid-cols-5 lg:gap-6 lg:space-y-0">
          <div class="card lg:col-span-2 lg:h-fit">
            <div class="mb-5 flex items-start gap-3">
              <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-violet-100 text-xl">
                💬
              </div>
              <div>
                <h2 class="font-bold text-slate-900">New feedback</h2>
                <p class="text-sm text-slate-500">Pick a session and share your thoughts.</p>
              </div>
            </div>

            <div class="space-y-4">
              <div>
                <label class="label">Class session</label>
                <select v-model="commentForm.entry_id" class="input">
                  <option value="">Select a session…</option>
                  <option v-for="entry in commentSessionEntries" :key="entry.id" :value="entry.id">
                    {{ sessionLabel(entry) }}
                  </option>
                </select>
              </div>

              <div>
                <label class="label">Your comment</label>
                <textarea
                  v-model="commentForm.body"
                  rows="4"
                  maxlength="500"
                  class="input resize-none"
                  placeholder="What would you like us to know about this class?"
                />
                <p class="mt-1 text-right text-xs text-slate-400">{{ commentForm.body.length }}/500</p>
              </div>

              <button class="btn-primary w-full" :disabled="postingComment" @click="submitComment">
                {{ postingComment ? "Submitting…" : "Submit feedback" }}
              </button>
            </div>
          </div>

          <div class="lg:col-span-3">
            <h3 class="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">
              Your comments ({{ comments.length }})
            </h3>

            <div v-if="comments.length" class="space-y-3">
              <article
                v-for="comment in comments"
                :key="comment.id"
                class="card !p-5"
              >
                <div class="flex gap-3">
                  <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-700">
                    {{ userInitials }}
                  </div>
                  <div class="min-w-0 flex-1">
                    <p class="text-sm leading-relaxed text-slate-800">{{ comment.body }}</p>
                    <div class="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-400">
                      <span class="rounded-md bg-slate-100 px-2 py-0.5 font-medium text-slate-600">
                        {{ comment.entry?.course?.name || "Class" }}
                      </span>
                      <span>{{ new Date(comment.created_at).toLocaleString() }}</span>
                    </div>

                    <div
                      v-if="comment.admin_reply"
                      class="mt-4 rounded-xl border border-blue-100 bg-blue-50 p-4"
                    >
                      <div class="mb-1 flex items-center gap-1.5 text-xs font-semibold text-blue-700">
                        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                        </svg>
                        Admin reply
                      </div>
                      <p class="text-sm text-slate-700">{{ comment.admin_reply }}</p>
                    </div>
                  </div>
                </div>
              </article>
            </div>

            <div v-else class="card py-14 text-center">
              <div class="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-2xl">
                ✍️
              </div>
              <p class="font-medium text-slate-700">No feedback yet</p>
              <p class="mt-1 text-sm text-slate-500">Your submitted comments will appear here.</p>
            </div>
          </div>
        </div>
      </section>
    </main>

    <!-- Mobile bottom nav -->
    <nav
      v-if="authenticated"
      class="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 px-2 py-1.5 shadow-[0_-4px_20px_rgba(0,0,0,0.06)] backdrop-blur-md sm:hidden"
    >
      <div class="mx-auto flex max-w-md justify-around">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="flex flex-1 flex-col items-center gap-0.5 rounded-xl px-2 py-1.5 text-[10px] font-semibold transition"
          :class="activeTab === tab.id ? 'text-blue-600' : 'text-slate-400'"
          @click="activeTab = tab.id"
        >
          <span
            class="flex h-9 w-9 items-center justify-center rounded-xl transition"
            :class="activeTab === tab.id ? 'bg-blue-600 text-white shadow-md shadow-blue-600/30' : ''"
          >
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" :d="tab.icon" />
            </svg>
          </span>
          {{ tab.label }}
        </button>
      </div>
    </nav>

    <ReminderSheet
      :open="showReminderSheet"
      :entry="selectedReminderEntry"
      :contact="portalContact"
      :semester-end="semesterEndDate"
      :existing-reminders="sheetExistingReminders"
      :saving="savingReminder"
      @close="showReminderSheet = false"
      @save="handleReminderSave"
      @cancel-reminder="cancelReminder"
      @go-to-alerts="goToAlertsTab"
    />
  </div>
</template>

<style scoped>
.portal-page {
  position: relative;
  overflow-x: hidden;
}

.portal-decor {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}

.portal-decor-blob {
  position: absolute;
  border-radius: 9999px;
  filter: blur(80px);
}

.portal-decor-blob-a {
  top: -6rem;
  right: -4rem;
  width: 28rem;
  height: 28rem;
  background: rgba(59, 130, 246, 0.08);
}

.portal-decor-blob-b {
  bottom: 10%;
  left: -6rem;
  width: 24rem;
  height: 24rem;
  background: rgba(99, 102, 241, 0.06);
}

.portal-page > header,
.portal-page > main,
.portal-page > nav {
  position: relative;
  z-index: 1;
}

.welcome-hero {
  animation: fade-up 0.4s ease-out;
}

.stat-card {
  border-radius: 1rem;
  border: 1px solid rgb(226 232 240);
  background: white;
  padding: 1rem 1.125rem;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.stat-label {
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgb(100 116 139);
}

.stat-value {
  margin-top: 0.25rem;
  font-size: 1.5rem;
  font-weight: 700;
  color: rgb(15 23 42);
}

.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  border-radius: 9999px;
  border: 1px solid rgb(226 232 240);
  background: rgb(248 250 252);
  padding: 0.375rem 0.75rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: rgb(71 85 105);
}

@keyframes fade-up {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
