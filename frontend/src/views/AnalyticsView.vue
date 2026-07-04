<script setup>
import { onMounted, ref, computed, watch } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"
import { analyticsApi, timetableApi } from "@/api/client"

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const metricsLoading = ref(false)
const overview = ref(null)
const roomUtilization = ref([])
const lecturerWorkload = ref([])
const timetables = ref([])
const selectedTimetableId = ref("")
const timetableMetrics = ref(null)
const error = ref("")
const lastUpdated = ref(null)
const activeTab = ref("overview")
const roomSearch = ref("")
const lecturerSearch = ref("")
const roomSort = ref("bookings")
const lecturerSort = ref("utilization")

const TAB_IDS = ["overview", "rooms", "workload", "timetable"]

const tabs = computed(() => [
  { id: "overview", label: "Overview", icon: "📊" },
  { id: "rooms", label: "Rooms", icon: "🏛️", count: roomUtilization.value.length },
  { id: "workload", label: "Workload", icon: "👥", count: lecturerWorkload.value.length },
  { id: "timetable", label: "Timetable", icon: "📅", count: timetables.value.length },
])

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

async function loadAnalytics() {
  loading.value = true
  error.value = ""
  try {
    const [overviewRes, roomsRes, lecturersRes, ttRes] = await Promise.all([
      analyticsApi.overview(),
      analyticsApi.roomUtilization(),
      analyticsApi.lecturerWorkload(),
      timetableApi.list({ status: "active" }),
    ])
    overview.value = overviewRes.data.data
    roomUtilization.value = (roomsRes.data.data || []).sort((a, b) => b.bookings - a.bookings)
    lecturerWorkload.value = (lecturersRes.data.data || []).sort((a, b) => b.utilization_pct - a.utilization_pct)
    timetables.value = ttRes.data.data || []
    if (!selectedTimetableId.value && timetables.value.length) {
      selectedTimetableId.value = timetables.value[0].id
    }
    lastUpdated.value = new Date()
    if (activeTab.value === "timetable" && selectedTimetableId.value) {
      await loadTimetableMetrics()
    }
  } catch (e) {
    error.value = e?.response?.data?.message || "Failed to load analytics."
  } finally {
    loading.value = false
  }
}

function setActiveTab(id) {
  activeTab.value = id
  router.replace({ query: { ...route.query, tab: id === "overview" ? undefined : id } })
}

async function loadTimetableMetrics() {
  if (!selectedTimetableId.value) {
    timetableMetrics.value = null
    return
  }
  metricsLoading.value = true
  try {
    const { data } = await analyticsApi.timetableMetrics(selectedTimetableId.value)
    timetableMetrics.value = data.data
  } catch {
    timetableMetrics.value = null
  } finally {
    metricsLoading.value = false
  }
}

watch(selectedTimetableId, loadTimetableMetrics)

const maxBookings = computed(() => Math.max(...roomUtilization.value.map((r) => r.bookings), 1))
const totalSessions = computed(() => roomUtilization.value.reduce((s, r) => s + r.bookings, 0))
const avgRoomBookings = computed(() =>
  roomUtilization.value.length ? (totalSessions.value / roomUtilization.value.length).toFixed(1) : "0"
)

const filteredRooms = computed(() => {
  let list = [...roomUtilization.value]
  const q = roomSearch.value.trim().toLowerCase()
  if (q) list = list.filter((r) => r.name?.toLowerCase().includes(q))
  if (roomSort.value === "name") list.sort((a, b) => (a.name || "").localeCompare(b.name || ""))
  else if (roomSort.value === "capacity") list.sort((a, b) => (b.capacity || 0) - (a.capacity || 0))
  else list.sort((a, b) => b.bookings - a.bookings)
  return list
})

const filteredLecturers = computed(() => {
  let list = [...lecturerWorkload.value]
  const q = lecturerSearch.value.trim().toLowerCase()
  if (q) list = list.filter((l) => l.name?.toLowerCase().includes(q) || l.email?.toLowerCase().includes(q))
  if (lecturerSort.value === "name") list.sort((a, b) => (a.name || "").localeCompare(b.name || ""))
  else if (lecturerSort.value === "hours") list.sort((a, b) => b.hours - a.hours)
  else list.sort((a, b) => b.utilization_pct - a.utilization_pct)
  return list
})

const overloadedCount = computed(() => lecturerWorkload.value.filter((l) => l.utilization_pct >= 90).length)
const highLoadCount = computed(() => lecturerWorkload.value.filter((l) => l.utilization_pct >= 70 && l.utilization_pct < 90).length)
const balancedCount = computed(() => lecturerWorkload.value.filter((l) => l.utilization_pct >= 40 && l.utilization_pct < 70).length)
const lightLoadCount = computed(() => lecturerWorkload.value.filter((l) => l.utilization_pct < 40).length)

const idleRoomsCount = computed(() => roomUtilization.value.filter((r) => r.bookings === 0).length)
const busyRoomsCount = computed(() => roomUtilization.value.filter((r) => r.bookings > 0).length)

const fitnessPct = computed(() => ((overview.value?.average_fitness_score ?? 0) * 100).toFixed(1))
const selectedTimetable = computed(() => timetables.value.find((t) => t.id === selectedTimetableId.value))

const dayChartMax = computed(() => {
  const dist = timetableMetrics.value?.day_distribution || {}
  return Math.max(...DAYS.map((d) => dist[d] || 0), 1)
})

const ttRoomUtil = computed(() =>
  [...(timetableMetrics.value?.room_utilization || [])].sort((a, b) => b.count - a.count)
)
const ttLecturerLoad = computed(() =>
  [...(timetableMetrics.value?.lecturer_workload || [])].sort((a, b) => b.hours - a.hours)
)
const ttMaxRoomCount = computed(() => Math.max(...ttRoomUtil.value.map((r) => r.count), 1))

const healthScore = computed(() => {
  if (!overview.value?.active_timetables) return null
  const fitness = (overview.value.average_fitness_score ?? 0) * 100
  const overloadPenalty = lecturerWorkload.value.length
    ? (overloadedCount.value / lecturerWorkload.value.length) * 25
    : 0
  const idlePenalty = roomUtilization.value.length
    ? (idleRoomsCount.value / roomUtilization.value.length) * 15
    : 0
  return Math.max(0, Math.min(100, Math.round(fitness - overloadPenalty - idlePenalty)))
})

function conflictSeverityClass(severity) {
  if (severity === "high") return "border-red-200 bg-red-50 text-red-800"
  if (severity === "medium") return "border-amber-200 bg-amber-50 text-amber-800"
  return "border-gray-200 bg-gray-50 text-gray-700"
}

function conflictTypeLabel(type) {
  const map = {
    lecturer_clash: "Lecturer clash",
    room_clash: "Room clash",
    student_group_clash: "Group clash",
    room_over_capacity: "Over capacity",
    break_slot_violation: "Break violation",
  }
  return map[type] || type?.replace(/_/g, " ") || "Conflict"
}

const kpis = computed(() => [
  {
    label: "Active Timetables",
    value: overview.value?.active_timetables ?? 0,
    sub: `${overview.value?.total_timetables ?? 0} total published`,
    icon: "📅",
    accent: "from-blue-500 to-blue-700",
    ring: "ring-blue-100",
  },
  {
    label: "Optimization Score",
    value: `${fitnessPct.value}%`,
    sub: overview.value?.optimization_quality ?? "N/A",
    icon: "✨",
    accent: "from-emerald-500 to-teal-600",
    ring: "ring-emerald-100",
    badge: overview.value?.optimization_quality,
  },
  {
    label: "Scheduled Sessions",
    value: totalSessions.value,
    sub: `${busyRoomsCount.value} rooms in use`,
    icon: "🗓️",
    accent: "from-blue-400 to-blue-600",
    ring: "ring-blue-100",
  },
  {
    label: "Lecturers",
    value: overview.value?.total_lecturers ?? 0,
    sub: overloadedCount.value ? `${overloadedCount.value} over 90% load` : "Teaching staff",
    icon: "👤",
    accent: "from-amber-500 to-orange-600",
    ring: "ring-amber-100",
    warn: overloadedCount.value > 0,
  },
  {
    label: "Rooms",
    value: overview.value?.total_rooms ?? 0,
    sub: idleRoomsCount.value ? `${idleRoomsCount.value} unused` : "Campus venues",
    icon: "🏛️",
    accent: "from-cyan-500 to-blue-600",
    ring: "ring-cyan-100",
  },
  {
    label: "Courses",
    value: overview.value?.total_courses ?? 0,
    sub: "Active modules",
    icon: "📚",
    accent: "from-rose-500 to-pink-600",
    ring: "ring-rose-100",
  },
])

function workloadColor(pct) {
  if (pct >= 90) return { bar: "bg-gradient-to-r from-red-500 to-rose-500", text: "text-red-700", bg: "bg-red-50 border-red-100", label: "Critical" }
  if (pct >= 70) return { bar: "bg-gradient-to-r from-orange-400 to-amber-500", text: "text-orange-700", bg: "bg-orange-50 border-orange-100", label: "High" }
  if (pct >= 40) return { bar: "bg-gradient-to-r from-blue-400 to-blue-600", text: "text-blue-700", bg: "bg-blue-50 border-blue-100", label: "Balanced" }
  return { bar: "bg-gradient-to-r from-slate-300 to-slate-400", text: "text-slate-600", bg: "bg-slate-50 border-slate-100", label: "Light" }
}

function roomBarColor(pct) {
  if (pct >= 80) return "bg-gradient-to-r from-blue-600 to-blue-700"
  if (pct >= 50) return "bg-gradient-to-r from-blue-500 to-blue-600"
  if (pct >= 20) return "bg-gradient-to-r from-blue-400 to-blue-500"
  return "bg-gradient-to-r from-blue-200 to-blue-300"
}

function qualityBadgeClass(q) {
  if (q === "Excellent") return "badge-success"
  if (q === "Good") return "badge-info"
  return "badge-warning"
}

function formatTime(d) {
  if (!d) return ""
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
}

onMounted(async () => {
  const tab = route.query.tab
  if (typeof tab === "string" && TAB_IDS.includes(tab)) {
    activeTab.value = tab
  }
  await loadAnalytics()
  await loadTimetableMetrics()
})
</script>

<template>
  <div class="space-y-6 pb-8">
    <!-- Hero -->
    <div class="rounded-2xl bg-white border border-gray-200 shadow-[0_4px_12px_0_rgba(0,0,0,0.01)]">
      <div class="px-6 py-8 sm:px-8 sm:py-10">
        <div class="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6">
          <div>
            <p class="text-blue-600 text-sm font-semibold tracking-wide uppercase">Insights & Reports</p>
            <h1 class="text-3xl sm:text-4xl font-bold mt-1 tracking-tight text-gray-900">Analytics Dashboard</h1>
            <p class="text-gray-500 mt-2 max-w-xl text-sm sm:text-base">
              Scheduling efficiency, room utilization, lecturer workload, and per-timetable deep dives — updated live from your active timetables.
            </p>
            <p v-if="lastUpdated" class="text-xs text-gray-400 mt-3">
              Last refreshed {{ formatTime(lastUpdated) }}
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-3">
            <RouterLink to="/generate" class="btn-secondary inline-flex items-center gap-2 text-sm">
              ⚡ Generate Timetable
            </RouterLink>
            <button
              @click="loadAnalytics"
              :disabled="loading"
              class="btn-primary inline-flex items-center gap-2 text-sm"
            >
              <svg :class="['w-4 h-4', loading && 'animate-spin']" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {{ loading ? "Refreshing…" : "Refresh data" }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="flex flex-wrap gap-1 p-1 bg-gray-100 rounded-xl w-full sm:w-fit">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        @click="setActiveTab(tab.id)"
        :class="[
          'flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all',
          activeTab === tab.id
            ? 'bg-white text-gray-900 shadow-sm'
            : 'text-gray-500 hover:text-gray-700 hover:bg-white/50',
        ]"
      >
        <span>{{ tab.icon }}</span>
        {{ tab.label }}
        <span
          v-if="tab.count != null && !loading"
          :class="[
            'text-[10px] font-bold px-1.5 py-0.5 rounded-full tabular-nums',
            activeTab === tab.id ? 'bg-blue-100 text-blue-700' : 'bg-gray-200 text-gray-600',
          ]"
        >{{ tab.count }}</span>
      </button>
    </div>

    <div v-if="error" class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-red-700 text-sm flex items-center gap-2">
      <span>⚠️</span> {{ error }}
    </div>

    <!-- Loading -->
    <template v-if="loading">
      <div class="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <div v-for="i in 6" :key="i" class="rounded-xl border border-gray-200 bg-white p-5 animate-pulse">
          <div class="h-3 bg-gray-200 rounded w-2/3 mb-4"></div>
          <div class="h-9 bg-gray-200 rounded w-1/2 mb-2"></div>
          <div class="h-2 bg-gray-100 rounded w-3/4"></div>
        </div>
      </div>
      <div class="grid lg:grid-cols-2 gap-6">
        <div v-for="i in 2" :key="i" class="card h-80 animate-pulse bg-gray-50"></div>
      </div>
    </template>

    <template v-else>
      <!-- KPI grid (always visible on overview, compact elsewhere) -->
      <div v-show="activeTab === 'overview'" class="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <div
          v-for="kpi in kpis"
          :key="kpi.label"
          :class="['rounded-xl border bg-white p-5 shadow-sm hover:shadow-md transition-shadow ring-1', kpi.ring]"
        >
          <div class="flex items-start justify-between gap-2">
            <p class="text-[11px] font-semibold text-gray-500 uppercase tracking-wider leading-tight">{{ kpi.label }}</p>
            <span :class="['w-9 h-9 rounded-lg flex items-center justify-center text-lg bg-gradient-to-br text-white shadow-sm', kpi.accent]">
              {{ kpi.icon }}
            </span>
          </div>
          <p class="text-2xl sm:text-3xl font-bold text-gray-900 mt-3 tabular-nums">{{ kpi.value }}</p>
          <p :class="['text-xs mt-1.5', kpi.warn ? 'text-red-600 font-medium' : 'text-gray-400']">{{ kpi.sub }}</p>
          <span v-if="kpi.badge" :class="['badge mt-2', qualityBadgeClass(kpi.badge)]">{{ kpi.badge }}</span>
        </div>
      </div>

      <!-- OVERVIEW TAB -->
      <div v-show="activeTab === 'overview'" class="space-y-6">
        <!-- Scheduling health -->
        <div v-if="healthScore != null" class="card !p-0 overflow-hidden">
          <div class="flex flex-col sm:flex-row sm:items-center gap-6 p-6">
            <div class="relative w-28 h-28 flex-shrink-0 mx-auto sm:mx-0">
              <svg class="w-full h-full -rotate-90" viewBox="0 0 36 36">
                <circle cx="18" cy="18" r="15.5" fill="none" stroke="#e5e7eb" stroke-width="3" />
                <circle
                  cx="18" cy="18" r="15.5" fill="none"
                  :stroke="healthScore >= 80 ? '#10b981' : healthScore >= 60 ? '#3b82f6' : '#f59e0b'"
                  stroke-width="3"
                  stroke-linecap="round"
                  :stroke-dasharray="`${healthScore * 0.97} 100`"
                />
              </svg>
              <div class="absolute inset-0 flex flex-col items-center justify-center">
                <span class="text-2xl font-bold text-gray-900">{{ healthScore }}</span>
                <span class="text-[10px] text-gray-400 uppercase font-semibold">Health</span>
              </div>
            </div>
            <div class="flex-1 text-center sm:text-left">
              <h2 class="font-semibold text-gray-900 text-lg">Scheduling Health Score</h2>
              <p class="text-sm text-gray-500 mt-1 max-w-lg">
                Composite score from optimization quality, lecturer overload, and idle room usage across active timetables.
              </p>
              <div class="flex flex-wrap justify-center sm:justify-start gap-3 mt-4 text-xs">
                <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-100">
                  ✨ {{ fitnessPct }}% avg fitness
                </span>
                <span v-if="overloadedCount" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-50 text-red-700 border border-red-100">
                  ⚠️ {{ overloadedCount }} overloaded
                </span>
                <span v-if="idleRoomsCount" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                  🏛️ {{ idleRoomsCount }} idle rooms
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Insight cards -->
        <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div class="rounded-xl border border-red-100 bg-gradient-to-br from-red-50 to-white p-5">
            <p class="text-xs font-semibold text-red-600 uppercase tracking-wide">Overloaded lecturers</p>
            <p class="text-3xl font-bold text-red-700 mt-2">{{ overloadedCount }}</p>
            <p class="text-xs text-red-500/80 mt-1">≥ 90% of weekly capacity</p>
          </div>
          <div class="rounded-xl border border-orange-100 bg-gradient-to-br from-orange-50 to-white p-5">
            <p class="text-xs font-semibold text-orange-600 uppercase tracking-wide">High workload</p>
            <p class="text-3xl font-bold text-orange-700 mt-2">{{ highLoadCount }}</p>
            <p class="text-xs text-orange-500/80 mt-1">70–89% utilization</p>
          </div>
          <div class="rounded-xl border border-emerald-100 bg-gradient-to-br from-emerald-50 to-white p-5">
            <p class="text-xs font-semibold text-emerald-600 uppercase tracking-wide">Balanced load</p>
            <p class="text-3xl font-bold text-emerald-700 mt-2">{{ balancedCount }}</p>
            <p class="text-xs text-emerald-500/80 mt-1">40–69% — healthy range</p>
          </div>
          <div class="rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-5">
            <p class="text-xs font-semibold text-slate-600 uppercase tracking-wide">Idle rooms</p>
            <p class="text-3xl font-bold text-slate-700 mt-2">{{ idleRoomsCount }}</p>
            <p class="text-xs text-slate-500 mt-1">No sessions scheduled</p>
          </div>
        </div>

        <!-- Preview panels -->
        <div class="grid lg:grid-cols-2 gap-6">
          <!-- Top rooms preview -->
          <div class="card !p-0 overflow-hidden">
            <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h2 class="font-semibold text-gray-900">Top Rooms</h2>
                <p class="text-xs text-gray-400">Avg {{ avgRoomBookings }} sessions per room</p>
              </div>
              <button @click="setActiveTab('rooms')" class="text-xs font-medium text-blue-600 hover:text-blue-800">View all →</button>
            </div>
            <div class="p-6 space-y-4">
              <div v-if="!roomUtilization.length" class="text-sm text-gray-400 text-center py-6">No room data yet.</div>
              <div v-for="room in roomUtilization.slice(0, 5)" :key="room.name" class="space-y-1.5">
                <div class="flex justify-between text-sm">
                  <span class="font-medium text-gray-800 truncate">{{ room.name }}</span>
                  <span class="text-gray-500 tabular-nums">{{ room.bookings }} sessions</span>
                </div>
                <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    :class="['h-full rounded-full transition-all duration-700', roomBarColor((room.bookings / maxBookings) * 100)]"
                    :style="{ width: `${Math.max((room.bookings / maxBookings) * 100, 3)}%` }"
                  ></div>
                </div>
              </div>
            </div>
          </div>

          <!-- Top lecturers preview -->
          <div class="card !p-0 overflow-hidden">
            <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h2 class="font-semibold text-gray-900">Highest Workload</h2>
                <p class="text-xs text-gray-400">Sorted by utilization %</p>
              </div>
              <button @click="setActiveTab('workload')" class="text-xs font-medium text-blue-600 hover:text-blue-800">View all →</button>
            </div>
            <div class="p-6 space-y-3">
              <div v-if="!lecturerWorkload.length" class="text-sm text-gray-400 text-center py-6">No workload data yet.</div>
              <div
                v-for="lec in lecturerWorkload.slice(0, 5)"
                :key="lec.name"
                :class="['rounded-lg border px-4 py-3', workloadColor(lec.utilization_pct).bg]"
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="font-medium text-gray-900 text-sm truncate">{{ lec.name }}</span>
                  <span :class="['text-xs font-bold px-2 py-0.5 rounded-full', workloadColor(lec.utilization_pct).text, workloadColor(lec.utilization_pct).bg]">
                    {{ lec.utilization_pct }}%
                  </span>
                </div>
                <p class="text-xs text-gray-500 mt-1">{{ lec.hours }}h / {{ lec.max }}h weekly</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Workload distribution bar -->
        <div class="card">
          <h2 class="font-semibold text-gray-900 mb-1">Workload Distribution</h2>
          <p class="text-xs text-gray-400 mb-5">How lecturers are spread across load bands</p>
          <div v-if="!lecturerWorkload.length" class="text-sm text-gray-400 py-4 text-center">No data</div>
          <div v-else class="space-y-3">
            <div class="flex h-4 rounded-full overflow-hidden bg-gray-100">
              <div v-if="overloadedCount" class="bg-red-500 transition-all" :style="{ width: `${(overloadedCount / lecturerWorkload.length) * 100}%` }" title="Critical"></div>
              <div v-if="highLoadCount" class="bg-orange-400 transition-all" :style="{ width: `${(highLoadCount / lecturerWorkload.length) * 100}%` }" title="High"></div>
              <div v-if="balancedCount" class="bg-blue-500 transition-all" :style="{ width: `${(balancedCount / lecturerWorkload.length) * 100}%` }" title="Balanced"></div>
              <div v-if="lightLoadCount" class="bg-slate-300 transition-all" :style="{ width: `${(lightLoadCount / lecturerWorkload.length) * 100}%` }" title="Light"></div>
            </div>
            <div class="flex flex-wrap gap-4 text-xs text-gray-600">
              <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-red-500"></span>Critical ({{ overloadedCount }})</span>
              <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-orange-400"></span>High ({{ highLoadCount }})</span>
              <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-blue-500"></span>Balanced ({{ balancedCount }})</span>
              <span class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-slate-300"></span>Light ({{ lightLoadCount }})</span>
            </div>
          </div>
        </div>
      </div>

      <!-- ROOMS TAB -->
      <div v-show="activeTab === 'rooms'" class="card space-y-5">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 class="text-lg font-semibold text-gray-900">Room Utilization</h2>
            <p class="text-sm text-gray-500">{{ roomUtilization.length }} rooms · {{ totalSessions }} total sessions</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <input v-model="roomSearch" type="search" placeholder="Search rooms…" class="input !py-2 !text-sm w-full sm:w-48" />
            <select v-model="roomSort" class="input !py-2 !text-sm w-full sm:w-36">
              <option value="bookings">Most used</option>
              <option value="capacity">Largest capacity</option>
              <option value="name">Name A–Z</option>
            </select>
          </div>
        </div>

        <div v-if="!filteredRooms.length" class="text-center py-16 text-gray-400">
          <p class="text-4xl mb-3">🏛️</p>
          <p class="font-medium">No rooms match your search</p>
          <p class="text-sm mt-1">Generate a timetable to populate room analytics.</p>
        </div>

        <div v-else class="grid gap-3 max-h-[32rem] overflow-y-auto pr-1">
          <div
            v-for="(room, idx) in filteredRooms"
            :key="room.name"
            class="group flex items-center gap-4 p-4 rounded-xl border border-gray-100 hover:border-blue-200 hover:bg-blue-50/30 transition-colors"
          >
            <div class="w-8 h-8 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-bold flex-shrink-0">
              {{ idx + 1 }}
            </div>
            <div class="flex-1 min-w-0 space-y-2">
              <div class="flex items-center justify-between gap-2">
                <div class="min-w-0">
                  <p class="font-semibold text-gray-900 truncate">{{ room.name }}</p>
                  <p class="text-xs text-gray-400">Capacity {{ room.capacity ?? "—" }}</p>
                </div>
                <div class="text-right flex-shrink-0">
                  <p class="text-lg font-bold text-gray-900 tabular-nums">{{ room.bookings }}</p>
                  <p class="text-[10px] text-gray-400 uppercase">sessions</p>
                </div>
              </div>
              <div class="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  :class="['h-full rounded-full transition-all duration-700', roomBarColor((room.bookings / maxBookings) * 100)]"
                  :style="{ width: `${Math.max((room.bookings / maxBookings) * 100, room.bookings ? 4 : 0)}%` }"
                ></div>
              </div>
            </div>
            <span
              v-if="room.bookings === 0"
              class="text-[10px] font-semibold uppercase tracking-wide text-slate-500 bg-slate-100 px-2 py-1 rounded-full flex-shrink-0"
            >Idle</span>
            <span
              v-else-if="(room.bookings / maxBookings) >= 0.8"
              class="text-[10px] font-semibold uppercase tracking-wide text-blue-700 bg-blue-100 px-2 py-1 rounded-full flex-shrink-0"
            >Hot</span>
          </div>
        </div>
      </div>

      <!-- WORKLOAD TAB -->
      <div v-show="activeTab === 'workload'" class="card space-y-5">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 class="text-lg font-semibold text-gray-900">Lecturer Workload</h2>
            <p class="text-sm text-gray-500">{{ lecturerWorkload.length }} lecturers tracked</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <input v-model="lecturerSearch" type="search" placeholder="Search lecturers…" class="input !py-2 !text-sm w-full sm:w-48" />
            <select v-model="lecturerSort" class="input !py-2 !text-sm w-full sm:w-40">
              <option value="utilization">Highest load</option>
              <option value="hours">Most hours</option>
              <option value="name">Name A–Z</option>
            </select>
          </div>
        </div>

        <div v-if="!filteredLecturers.length" class="text-center py-16 text-gray-400">
          <p class="text-4xl mb-3">👥</p>
          <p class="font-medium">No lecturers match your search</p>
        </div>

        <div v-else class="grid sm:grid-cols-2 gap-3 max-h-[32rem] overflow-y-auto pr-1">
          <div
            v-for="lec in filteredLecturers"
            :key="lec.name + lec.email"
            :class="['rounded-xl border p-4 transition-shadow hover:shadow-md', workloadColor(lec.utilization_pct).bg]"
          >
            <div class="flex items-start justify-between gap-2 mb-3">
              <div class="min-w-0">
                <p class="font-semibold text-gray-900 truncate">{{ lec.name }}</p>
                <p v-if="lec.email" class="text-xs text-gray-500 truncate">{{ lec.email }}</p>
              </div>
              <span :class="['text-xs font-bold px-2.5 py-1 rounded-full border', workloadColor(lec.utilization_pct).text, workloadColor(lec.utilization_pct).bg]">
                {{ workloadColor(lec.utilization_pct).label }}
              </span>
            </div>
            <div class="flex items-baseline justify-between mb-2">
              <span :class="['text-2xl font-bold tabular-nums', workloadColor(lec.utilization_pct).text]">{{ lec.utilization_pct }}%</span>
              <span class="text-sm text-gray-500">{{ lec.hours }}h / {{ lec.max }}h</span>
            </div>
            <div class="h-2.5 bg-white/60 rounded-full overflow-hidden border border-white/80">
              <div
                :class="['h-full rounded-full transition-all duration-700', workloadColor(lec.utilization_pct).bar]"
                :style="{ width: `${Math.min(lec.utilization_pct, 100)}%` }"
              ></div>
            </div>
          </div>
        </div>
      </div>

      <!-- TIMETABLE TAB -->
      <div v-show="activeTab === 'timetable'" class="space-y-6">
        <div class="card">
          <div class="flex flex-col sm:flex-row sm:items-end gap-4">
            <div class="flex-1">
              <label class="label">Select timetable</label>
              <select v-model="selectedTimetableId" class="input max-w-md">
                <option value="">— Choose a timetable —</option>
                <option v-for="tt in timetables" :key="tt.id" :value="tt.id">
                  {{ tt.name }} ({{ ((tt.fitness_score ?? 0) * 100).toFixed(0) }}% fit)
                </option>
              </select>
            </div>
            <RouterLink
              v-if="selectedTimetableId"
              :to="`/timetable/${selectedTimetableId}`"
              class="btn-secondary text-sm inline-flex items-center gap-1"
            >
              Open timetable →
            </RouterLink>
          </div>
        </div>

        <div v-if="!timetables.length" class="card bg-blue-50 border-blue-200 text-center py-12">
          <p class="text-4xl mb-3">📅</p>
          <h3 class="font-semibold text-blue-900">No active timetables</h3>
          <p class="text-sm text-blue-700 mt-2 max-w-md mx-auto">Generate and publish a timetable to unlock day-by-day breakdowns, conflict counts, and GA performance metrics.</p>
          <RouterLink to="/generate" class="btn-primary inline-flex mt-4 text-sm">Go to Generate</RouterLink>
        </div>

        <template v-else-if="selectedTimetableId">
          <div v-if="metricsLoading" class="grid lg:grid-cols-3 gap-4">
            <div v-for="i in 3" :key="i" class="card h-28 animate-pulse bg-gray-50"></div>
          </div>

          <template v-else-if="timetableMetrics">
            <!-- Timetable KPIs -->
            <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div class="rounded-xl border bg-white p-5 shadow-sm">
                <p class="text-xs font-semibold text-gray-500 uppercase">Fitness score</p>
                <p class="text-3xl font-bold text-emerald-600 mt-2">{{ ((timetableMetrics.fitness_score ?? 0) * 100).toFixed(1) }}%</p>
              </div>
              <div class="rounded-xl border bg-white p-5 shadow-sm">
                <p class="text-xs font-semibold text-gray-500 uppercase">Sessions</p>
                <p class="text-3xl font-bold text-gray-900 mt-2">{{ timetableMetrics.total_entries ?? 0 }}</p>
              </div>
              <div class="rounded-xl border bg-white p-5 shadow-sm">
                <p class="text-xs font-semibold text-gray-500 uppercase">Conflicts</p>
                <p :class="['text-3xl font-bold mt-2', timetableMetrics.total_conflicts ? 'text-red-600' : 'text-emerald-600']">
                  {{ timetableMetrics.total_conflicts ?? 0 }}
                </p>
              </div>
              <div class="rounded-xl border bg-white p-5 shadow-sm">
                <p class="text-xs font-semibold text-gray-500 uppercase">GA generations</p>
                <p class="text-3xl font-bold text-gray-900 mt-2">{{ timetableMetrics.generations_run ?? "—" }}</p>
                <p v-if="timetableMetrics.generation_time" class="text-xs text-gray-400 mt-1">{{ timetableMetrics.generation_time }}s runtime</p>
              </div>
            </div>

            <!-- Day distribution -->
            <div class="card">
              <h2 class="font-semibold text-gray-900">Sessions by Day</h2>
              <p class="text-xs text-gray-400 mb-6">{{ selectedTimetable?.name }}</p>
              <div class="flex items-end justify-between gap-2 sm:gap-3 h-44">
                <div v-for="day in DAYS" :key="day" class="flex-1 flex flex-col items-center gap-2 h-full justify-end min-w-0">
                  <span class="text-xs font-semibold text-gray-700 tabular-nums">
                    {{ timetableMetrics.day_distribution?.[day] ?? 0 }}
                  </span>
                  <div class="w-full max-w-[3.5rem] flex-1 flex items-end">
                    <div
                      class="w-full rounded-t-lg bg-gradient-to-t from-blue-600 to-blue-400 transition-all duration-700 min-h-[4px] hover:from-blue-500 hover:to-blue-300"
                      :style="{ height: `${Math.max(((timetableMetrics.day_distribution?.[day] ?? 0) / dayChartMax) * 100, 2)}%` }"
                      :title="`${day}: ${timetableMetrics.day_distribution?.[day] ?? 0} sessions`"
                    ></div>
                  </div>
                  <span class="text-[10px] text-gray-500 font-medium truncate w-full text-center">{{ day.slice(0, 3) }}</span>
                </div>
              </div>
            </div>

            <!-- Per-timetable breakdown -->
            <div class="grid lg:grid-cols-2 gap-6">
              <div class="card !p-0 overflow-hidden">
                <div class="px-6 py-4 border-b border-gray-100">
                  <h2 class="font-semibold text-gray-900">Rooms in this timetable</h2>
                  <p class="text-xs text-gray-400">{{ ttRoomUtil.length }} rooms used</p>
                </div>
                <div class="p-6 space-y-3 max-h-64 overflow-y-auto">
                  <div v-if="!ttRoomUtil.length" class="text-sm text-gray-400 text-center py-4">No room data.</div>
                  <div v-for="room in ttRoomUtil.slice(0, 8)" :key="room.name" class="space-y-1">
                    <div class="flex justify-between text-sm">
                      <span class="font-medium text-gray-800 truncate">{{ room.name }}</span>
                      <span class="text-gray-500 tabular-nums">{{ room.count }} sessions</span>
                    </div>
                    <div class="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        class="h-full rounded-full bg-gradient-to-r from-blue-500 to-blue-700"
                        :style="{ width: `${Math.max((room.count / ttMaxRoomCount) * 100, 4)}%` }"
                      ></div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="card !p-0 overflow-hidden">
                <div class="px-6 py-4 border-b border-gray-100">
                  <h2 class="font-semibold text-gray-900">Lecturers in this timetable</h2>
                  <p class="text-xs text-gray-400">{{ ttLecturerLoad.length }} lecturers assigned</p>
                </div>
                <div class="p-6 space-y-2 max-h-64 overflow-y-auto">
                  <div v-if="!ttLecturerLoad.length" class="text-sm text-gray-400 text-center py-4">No lecturer data.</div>
                  <div
                    v-for="lec in ttLecturerLoad.slice(0, 8)"
                    :key="lec.name"
                    class="flex items-center justify-between gap-3 py-2 border-b border-gray-50 last:border-0"
                  >
                    <span class="text-sm font-medium text-gray-800 truncate">{{ lec.name }}</span>
                    <span class="text-sm font-bold text-blue-600 tabular-nums flex-shrink-0">{{ lec.hours }}h</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Conflicts list -->
            <div v-if="timetableMetrics.total_conflicts > 0" class="card border-red-100 bg-red-50/50">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                <div>
                  <h2 class="font-semibold text-red-900 flex items-center gap-2">
                    ⚠️ {{ timetableMetrics.total_conflicts }} scheduling conflict{{ timetableMetrics.total_conflicts === 1 ? '' : 's' }}
                  </h2>
                  <p class="text-sm text-red-700 mt-1">Resolve in the timetable editor or with Sora AI assistance.</p>
                </div>
                <RouterLink :to="`/timetable/${selectedTimetableId}`" class="btn-secondary text-sm !border-red-200 !text-red-700 hover:!bg-red-100 inline-flex items-center gap-1 self-start">
                  Fix in editor →
                </RouterLink>
              </div>
              <ul class="space-y-2 max-h-56 overflow-y-auto">
                <li
                  v-for="(c, i) in (timetableMetrics.conflicts || []).slice(0, 12)"
                  :key="i"
                  :class="['text-sm rounded-lg px-3 py-2.5 border', conflictSeverityClass(c.severity)]"
                >
                  <div class="flex flex-wrap items-center gap-2 mb-1">
                    <span class="text-[10px] font-bold uppercase tracking-wide opacity-80">{{ conflictTypeLabel(c.type) }}</span>
                    <span v-if="c.rule" class="text-[10px] px-1.5 py-0.5 rounded bg-white/60 font-medium">{{ c.rule }}</span>
                  </div>
                  <p>{{ c.message || c.description }}</p>
                </li>
              </ul>
              <p v-if="timetableMetrics.total_conflicts > 12" class="text-xs text-red-600 mt-3">
                + {{ timetableMetrics.total_conflicts - 12 }} more — open the timetable to see all.
              </p>
            </div>

            <div v-else class="rounded-xl border border-emerald-200 bg-emerald-50/80 px-5 py-4 flex items-center gap-3">
              <span class="text-2xl">✅</span>
              <div>
                <p class="font-semibold text-emerald-900">No conflicts detected</p>
                <p class="text-sm text-emerald-700">This timetable passes all hard constraint checks.</p>
              </div>
            </div>
          </template>
        </template>
      </div>

      <!-- Empty state when no active timetables (overview only) -->
      <div
        v-if="activeTab === 'overview' && !overview?.active_timetables"
        class="rounded-xl border border-dashed border-blue-200 bg-blue-50/50 p-8 text-center"
      >
        <p class="text-4xl mb-3">📊</p>
        <h3 class="font-semibold text-blue-900 text-lg">Analytics will appear after your first timetable</h3>
        <p class="text-sm text-blue-700 mt-2 max-w-lg mx-auto">
          Room utilization, lecturer workload, and optimization scores are computed from active published timetables.
        </p>
        <RouterLink to="/generate" class="btn-primary inline-flex mt-5 text-sm">Generate your first timetable</RouterLink>
      </div>
    </template>
  </div>
</template>
