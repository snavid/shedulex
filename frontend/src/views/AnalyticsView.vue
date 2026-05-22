<script setup>
import { onMounted, ref, computed } from "vue"
import { analyticsApi } from "@/api/client"

const loading = ref(true)
const overview = ref(null)
const roomUtilization = ref([])
const lecturerWorkload = ref([])
const error = ref("")

async function loadAnalytics() {
  loading.value = true
  error.value = ""
  try {
    const [overviewRes, roomsRes, lecturersRes] = await Promise.all([
      analyticsApi.overview(),
      analyticsApi.roomUtilization(),
      analyticsApi.lecturerWorkload(),
    ])
    overview.value = overviewRes.data.data
    roomUtilization.value = (roomsRes.data.data || []).sort((a, b) => b.bookings - a.bookings)
    lecturerWorkload.value = (lecturersRes.data.data || []).sort((a, b) => b.utilization_pct - a.utilization_pct)
  } catch (e) {
    error.value = e?.response?.data?.message || "Failed to load analytics."
  } finally {
    loading.value = false
  }
}

const maxBookings = computed(() => Math.max(...roomUtilization.value.map((r) => r.bookings), 1))

function workloadColor(pct) {
  if (pct >= 90) return { bar: "bg-red-500", text: "text-red-700", bg: "bg-red-50" }
  if (pct >= 70) return { bar: "bg-orange-500", text: "text-orange-700", bg: "bg-orange-50" }
  if (pct >= 40) return { bar: "bg-blue-500", text: "text-blue-700", bg: "bg-blue-50" }
  return { bar: "bg-gray-300", text: "text-gray-500", bg: "bg-gray-50" }
}

function roomColor(pct) {
  if (pct >= 80) return "bg-blue-600"
  if (pct >= 50) return "bg-blue-400"
  return "bg-blue-200"
}

onMounted(loadAnalytics)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Analytics</h1>
        <p class="text-sm text-gray-500 mt-1">Scheduling efficiency, resource utilization, and workload insights.</p>
      </div>
      <button @click="loadAnalytics" class="btn-secondary text-sm" :disabled="loading">
        {{ loading ? "Loading…" : "Refresh" }}
      </button>
    </div>

    <div v-if="error" class="card border-red-200 bg-red-50 text-red-700 text-sm">{{ error }}</div>

    <!-- Loading skeleton -->
    <template v-if="loading">
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" class="card animate-pulse">
          <div class="h-3 bg-gray-200 rounded w-2/3 mb-3"></div>
          <div class="h-8 bg-gray-200 rounded w-1/2"></div>
        </div>
      </div>
    </template>

    <template v-else>
      <!-- KPI cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div class="card">
          <div class="flex items-center justify-between mb-3">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Active Timetables</p>
            <span class="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center">
              <svg class="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </span>
          </div>
          <p class="text-3xl font-bold text-gray-900">{{ overview?.active_timetables ?? 0 }}</p>
          <p class="text-xs text-gray-400 mt-1">of {{ overview?.total_timetables ?? 0 }} total</p>
        </div>

        <div class="card">
          <div class="flex items-center justify-between mb-3">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Avg. Fitness</p>
            <span class="w-8 h-8 rounded-lg bg-green-100 flex items-center justify-center">
              <svg class="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </span>
          </div>
          <p class="text-3xl font-bold text-gray-900">{{ ((overview?.average_fitness_score ?? 0) * 100).toFixed(1) }}%</p>
          <span :class="['badge mt-1', overview?.optimization_quality === 'Excellent' ? 'badge-success' : overview?.optimization_quality === 'Good' ? 'badge-info' : 'badge-warning']">
            {{ overview?.optimization_quality ?? "N/A" }}
          </span>
        </div>

        <div class="card">
          <div class="flex items-center justify-between mb-3">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Total Lecturers</p>
            <span class="w-8 h-8 rounded-lg bg-purple-100 flex items-center justify-center">
              <svg class="w-4 h-4 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </span>
          </div>
          <p class="text-3xl font-bold text-gray-900">{{ overview?.total_lecturers ?? 0 }}</p>
          <p class="text-xs text-gray-400 mt-1">teaching staff</p>
        </div>

        <div class="card">
          <div class="flex items-center justify-between mb-3">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Total Courses</p>
            <span class="w-8 h-8 rounded-lg bg-orange-100 flex items-center justify-center">
              <svg class="w-4 h-4 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </span>
          </div>
          <p class="text-3xl font-bold text-gray-900">{{ overview?.total_courses ?? 0 }}</p>
          <p class="text-xs text-gray-400 mt-1">active modules</p>
        </div>
      </div>

      <!-- Charts row -->
      <div class="grid lg:grid-cols-2 gap-6">

        <!-- Room Utilization -->
        <div class="card space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h2 class="font-semibold text-gray-900">Room Utilization</h2>
              <p class="text-xs text-gray-400">Bookings across active timetables</p>
            </div>
            <span class="text-xs text-gray-400">{{ roomUtilization.length }} rooms</span>
          </div>

          <div v-if="!roomUtilization.length" class="text-sm text-gray-400 py-8 text-center">
            No room data available. Generate a timetable first.
          </div>
          <div v-else class="space-y-3 max-h-96 overflow-y-auto pr-1">
            <div v-for="room in roomUtilization" :key="room.name" class="space-y-1.5">
              <div class="flex items-center justify-between text-sm">
                <div class="flex items-center gap-2 min-w-0">
                  <span class="font-medium text-gray-900 truncate">{{ room.name }}</span>
                  <span class="text-xs text-gray-400 flex-shrink-0">cap {{ room.capacity }}</span>
                </div>
                <span class="text-sm font-semibold text-gray-700 flex-shrink-0 ml-2">
                  {{ room.bookings }} sessions
                </span>
              </div>
              <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  :class="['h-full rounded-full transition-all duration-500', roomColor((room.bookings / maxBookings) * 100)]"
                  :style="{ width: `${Math.max((room.bookings / maxBookings) * 100, 2)}%` }"
                ></div>
              </div>
            </div>
          </div>
        </div>

        <!-- Lecturer Workload -->
        <div class="card space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <h2 class="font-semibold text-gray-900">Lecturer Workload</h2>
              <p class="text-xs text-gray-400">Hours assigned vs. maximum capacity</p>
            </div>
            <div class="flex items-center gap-3 text-xs text-gray-400">
              <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-red-500 inline-block"></span>Over 90%</span>
              <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-orange-500 inline-block"></span>70–90%</span>
              <span class="flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-blue-500 inline-block"></span>Below 70%</span>
            </div>
          </div>

          <div v-if="!lecturerWorkload.length" class="text-sm text-gray-400 py-8 text-center">
            No workload data. Generate a timetable first.
          </div>
          <div v-else class="space-y-3 max-h-96 overflow-y-auto pr-1">
            <div v-for="lec in lecturerWorkload" :key="lec.name" class="space-y-1.5">
              <div class="flex items-center justify-between text-sm">
                <span class="font-medium text-gray-900 truncate min-w-0">{{ lec.name }}</span>
                <div class="flex items-center gap-2 flex-shrink-0 ml-2">
                  <span :class="['text-xs font-semibold', workloadColor(lec.utilization_pct).text]">
                    {{ lec.utilization_pct }}%
                  </span>
                  <span class="text-xs text-gray-400">{{ lec.hours }}h / {{ lec.max }}h</span>
                </div>
              </div>
              <div class="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  :class="['h-full rounded-full transition-all duration-500', workloadColor(lec.utilization_pct).bar]"
                  :style="{ width: `${Math.min(lec.utilization_pct, 100)}%` }"
                ></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Empty state: no timetables -->
      <div v-if="!overview?.active_timetables" class="card bg-blue-50 border-blue-200">
        <div class="flex items-start gap-4">
          <div class="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
            <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <h3 class="font-semibold text-blue-900">No active timetables</h3>
            <p class="text-sm text-blue-700 mt-1">Generate a timetable from the Generate page to see room utilization and lecturer workload analytics.</p>
            <RouterLink to="/generate" class="inline-flex items-center gap-2 mt-3 text-sm font-medium text-blue-700 hover:text-blue-900">
              Go to Generate →
            </RouterLink>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
