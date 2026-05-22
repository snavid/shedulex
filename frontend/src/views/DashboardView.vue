<script setup>
import { computed, ref, onMounted } from "vue"
import { useAuthStore } from "@/stores/auth"
import { analyticsApi, calendarApi, timetableApi } from "@/api/client"
import { RouterLink } from "vue-router"

const auth = useAuthStore()
const stats = ref(null)
const upcomingEvents = ref([])
const recentTimetables = ref([])
const loading = ref(true)

const quickActions = computed(() => {
  const actions = [
    { label: "Academic Calendar", icon: "📅", to: "/calendar", color: "from-emerald-500 to-emerald-600", desc: "Events & schedule" },
    { label: "AI Assistant", icon: "🤖", to: "/ai-assistant", color: "from-violet-500 to-violet-600", desc: "Smart scheduling" },
    { label: "Analytics", icon: "📊", to: "/analytics", color: "from-orange-500 to-orange-600", desc: "Reports & insights" },
    { label: "Notifications", icon: "🔔", to: "/notifications", color: "from-pink-500 to-pink-600", desc: "Send & track" },
  ]
  if (auth.isTimetableOfficer) {
    actions.unshift({ label: "Generate Timetable", icon: "⚡", to: "/generate", color: "from-blue-500 to-blue-600", desc: "GA scheduling" })
  }
  return actions.slice(0, 4)
})

const todayFormatted = computed(() => {
  return new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" })
})

const greetingTime = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return "Good morning"
  if (h < 17) return "Good afternoon"
  return "Good evening"
})

function eventTypeColor(type) {
  const map = {
    exam: "bg-orange-100 text-orange-700",
    holiday: "bg-red-100 text-red-700",
    deadline: "bg-yellow-100 text-yellow-700",
    meeting: "bg-purple-100 text-purple-700",
    event: "bg-emerald-100 text-emerald-700",
    makeup: "bg-pink-100 text-pink-700",
    semester_break: "bg-teal-100 text-teal-700",
    announcement: "bg-gray-100 text-gray-700",
  }
  return map[type] || "bg-gray-100 text-gray-700"
}

function formatEventDate(dt) {
  if (!dt) return ""
  const d = new Date(dt)
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

function daysUntil(dt) {
  if (!dt) return null
  const diff = new Date(dt) - new Date()
  const days = Math.ceil(diff / (1000 * 60 * 60 * 24))
  if (days < 0) return null
  if (days === 0) return "Today"
  if (days === 1) return "Tomorrow"
  return `In ${days} days`
}

onMounted(async () => {
  try {
    const [statsRes, eventsRes, timetablesRes] = await Promise.allSettled([
      analyticsApi.overview(),
      calendarApi.events({ limit: 6 }),
      timetableApi.list({}),
    ])
    if (statsRes.status === "fulfilled") stats.value = statsRes.value.data.data
    if (eventsRes.status === "fulfilled") {
      const now = new Date()
      upcomingEvents.value = (eventsRes.value.data.data || [])
        .filter((e) => !e.is_cancelled && new Date(e.start) >= now)
        .sort((a, b) => new Date(a.start) - new Date(b.start))
        .slice(0, 5)
    }
    if (timetablesRes.status === "fulfilled") {
      recentTimetables.value = (timetablesRes.value.data.data || []).slice(0, 4)
    }
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="space-y-6">
    <!-- ── Welcome header ────────────────────────────────────────────────── -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">
          {{ greetingTime }}, {{ auth.user?.first_name }}!
        </h1>
        <p class="text-sm text-gray-500 mt-0.5">{{ todayFormatted }}</p>
      </div>
      <RouterLink v-if="auth.isTimetableOfficer" to="/generate" class="btn-primary text-sm self-start sm:self-auto">
        ⚡ Generate Timetable
      </RouterLink>
    </div>

    <!-- ── KPI stats ─────────────────────────────────────────────────────── -->
    <div v-if="loading" class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div v-for="i in 4" :key="i" class="card animate-pulse">
        <div class="h-3 bg-gray-200 rounded w-2/3 mb-3"></div>
        <div class="h-8 bg-gray-200 rounded w-1/2 mb-2"></div>
        <div class="h-2 bg-gray-100 rounded w-1/3"></div>
      </div>
    </div>

    <div v-else-if="stats" class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="card hover:shadow-md transition-shadow group">
        <div class="flex items-center justify-between mb-3">
          <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Active Timetables</p>
          <div class="w-9 h-9 rounded-xl bg-blue-100 flex items-center justify-center group-hover:bg-blue-200 transition-colors">
            <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        </div>
        <p class="text-3xl font-bold text-gray-900">{{ stats.active_timetables }}</p>
        <p class="text-xs text-gray-400 mt-1">of {{ stats.total_timetables }} total</p>
      </div>

      <div class="card hover:shadow-md transition-shadow group">
        <div class="flex items-center justify-between mb-3">
          <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Total Courses</p>
          <div class="w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center group-hover:bg-emerald-200 transition-colors">
            <svg class="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          </div>
        </div>
        <p class="text-3xl font-bold text-gray-900">{{ stats.total_courses }}</p>
        <p class="text-xs text-gray-400 mt-1">active modules</p>
      </div>

      <div class="card hover:shadow-md transition-shadow group">
        <div class="flex items-center justify-between mb-3">
          <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Lecturers</p>
          <div class="w-9 h-9 rounded-xl bg-purple-100 flex items-center justify-center group-hover:bg-purple-200 transition-colors">
            <svg class="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
        </div>
        <p class="text-3xl font-bold text-gray-900">{{ stats.total_lecturers }}</p>
        <p class="text-xs text-gray-400 mt-1">teaching staff</p>
      </div>

      <div class="card hover:shadow-md transition-shadow group">
        <div class="flex items-center justify-between mb-3">
          <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Avg. Fitness</p>
          <div class="w-9 h-9 rounded-xl bg-orange-100 flex items-center justify-center group-hover:bg-orange-200 transition-colors">
            <svg class="w-5 h-5 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
        </div>
        <p class="text-3xl font-bold text-gray-900">{{ (stats.average_fitness_score * 100).toFixed(1) }}%</p>
        <span :class="['badge mt-1', stats.optimization_quality === 'Excellent' ? 'badge-success' : stats.optimization_quality === 'Good' ? 'badge-info' : 'badge-warning']">
          {{ stats.optimization_quality }}
        </span>
      </div>
    </div>

    <!-- ── Quick actions ──────────────────────────────────────────────────── -->
    <div>
      <h2 class="text-base font-semibold text-gray-900 mb-3">Quick Actions</h2>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <RouterLink
          v-for="action in quickActions"
          :key="action.to"
          :to="action.to"
          class="group rounded-xl p-4 hover:shadow-md transition-all hover:-translate-y-0.5 bg-white border border-gray-200 cursor-pointer"
        >
          <div :class="['w-10 h-10 rounded-xl mb-3 flex items-center justify-center text-xl bg-gradient-to-br', action.color]">
            {{ action.icon }}
          </div>
          <p class="text-sm font-semibold text-gray-900">{{ action.label }}</p>
          <p class="text-xs text-gray-400 mt-0.5">{{ action.desc }}</p>
        </RouterLink>
      </div>
    </div>

    <!-- ── 2-column grid: upcoming events + recent timetables ──────────── -->
    <div class="grid lg:grid-cols-2 gap-6">

      <!-- Upcoming Events -->
      <div class="card space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold text-gray-900">Upcoming Events</h2>
          <RouterLink to="/calendar" class="text-xs text-blue-600 hover:text-blue-700 font-medium">View calendar →</RouterLink>
        </div>
        <div v-if="!upcomingEvents.length && !loading" class="text-sm text-gray-400 py-6 text-center">
          No upcoming events. <RouterLink to="/calendar" class="text-blue-600">Create one</RouterLink>
        </div>
        <ul class="space-y-2">
          <li
            v-for="evt in upcomingEvents"
            :key="evt.id"
            class="flex items-center gap-3 p-2.5 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <div class="w-10 h-10 rounded-lg bg-gray-100 flex flex-col items-center justify-center text-center flex-shrink-0">
              <p class="text-xs font-bold text-gray-700">{{ formatEventDate(evt.start).split(" ")[0] }}</p>
              <p class="text-sm font-bold text-blue-600">{{ formatEventDate(evt.start).split(" ")[1] }}</p>
            </div>
            <div class="min-w-0 flex-1">
              <p class="text-sm font-medium text-gray-900 truncate">{{ evt.title }}</p>
              <div class="flex items-center gap-2 mt-0.5">
                <span :class="['text-xs px-1.5 py-0.5 rounded font-medium', eventTypeColor(evt.event_type)]">
                  {{ evt.event_type }}
                </span>
                <span v-if="daysUntil(evt.start)" class="text-xs text-gray-400">{{ daysUntil(evt.start) }}</span>
              </div>
            </div>
          </li>
        </ul>
      </div>

      <!-- Recent Timetables -->
      <div class="card space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold text-gray-900">Recent Timetables</h2>
          <RouterLink to="/timetable" class="text-xs text-blue-600 hover:text-blue-700 font-medium">View all →</RouterLink>
        </div>
        <div v-if="!recentTimetables.length && !loading" class="text-sm text-gray-400 py-6 text-center">
          No timetables yet. <RouterLink v-if="auth.isTimetableOfficer" to="/generate" class="text-blue-600">Generate one</RouterLink>
        </div>
        <ul class="space-y-2">
          <li v-for="tt in recentTimetables" :key="tt.id">
            <RouterLink :to="`/timetable/${tt.id}`" class="flex items-center gap-3 p-2.5 rounded-lg hover:bg-gray-50 transition-colors group">
              <div class="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0 group-hover:bg-blue-100 transition-colors">
                <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
              <div class="min-w-0 flex-1">
                <p class="text-sm font-medium text-gray-900 truncate">{{ tt.name }}</p>
                <p class="text-xs text-gray-400 mt-0.5 truncate">
                  {{ tt.department?.name }} · Sem {{ tt.semester }} · {{ tt.academic_year }}
                </p>
              </div>
              <div class="text-right flex-shrink-0">
                <p class="text-sm font-bold text-blue-600">{{ (tt.fitness_score * 100).toFixed(0) }}%</p>
                <span :class="['text-xs px-1.5 py-0.5 rounded font-medium', tt.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600']">
                  {{ tt.status || "draft" }}
                </span>
              </div>
            </RouterLink>
          </li>
        </ul>
      </div>
    </div>

    <!-- System Status -->
    <div class="card">
      <h2 class="font-semibold text-gray-900 mb-4">System Status</h2>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div v-for="service in [
          { name: 'Auth Service', ok: true },
          { name: 'Timetable Engine', ok: true },
          { name: 'AI Assistant', ok: true },
          { name: 'Notifications', ok: true },
        ]" :key="service.name"
          class="flex items-center gap-2.5 p-3 bg-gray-50 rounded-xl"
        >
          <div :class="['w-2.5 h-2.5 rounded-full flex-shrink-0', service.ok ? 'bg-green-500' : 'bg-red-500']">
            <div :class="['w-full h-full rounded-full animate-ping opacity-75', service.ok ? 'bg-green-500' : 'bg-red-500']"></div>
          </div>
          <span class="text-sm text-gray-700 font-medium">{{ service.name }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
