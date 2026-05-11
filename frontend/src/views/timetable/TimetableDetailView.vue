<script setup>
import { ref, onMounted, computed } from "vue"
import { useRoute } from "vue-router"
import { useTimetableStore } from "@/stores/timetable"
import { documentApi } from "@/api/client"
import { useToast } from "vue-toastification"

const route = useRoute()
const store = useTimetableStore()
const toast = useToast()
const loading = ref(true)
const conflictsLoading = ref(false)

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

onMounted(async () => {
  await store.fetchTimetable(route.params.id)
  loading.value = false
})

const timetableGrid = computed(() => {
  if (!store.currentTimetable?.entries) return {}
  const grid = {}
  for (const entry of store.currentTimetable.entries) {
    const slot = entry.time_slot
    if (!slot) continue
    const key = `${slot.day}__${slot.start_time}`
    grid[key] = entry
  }
  return grid
})

const timeSlots = computed(() => {
  if (!store.currentTimetable?.entries) return []
  const seen = new Set()
  const slots = []
  for (const e of store.currentTimetable.entries) {
    const s = e.time_slot
    if (!s) continue
    const key = `${s.start_time}__${s.slot_index}`
    if (!seen.has(key)) { seen.add(key); slots.push(s) }
  }
  return slots.sort((a, b) => (a.slot_index || 0) - (b.slot_index || 0))
})

async function detectConflicts() {
  conflictsLoading.value = true
  try {
    const conflicts = await store.detectConflicts(route.params.id)
    if (conflicts.length === 0) {
      toast.success("No conflicts detected! ✅")
    } else {
      toast.warning(`${conflicts.length} conflict(s) found.`)
    }
  } finally {
    conflictsLoading.value = false
  }
}

function downloadPdf() { window.open(documentApi.downloadPdf(route.params.id), "_blank") }
function downloadExcel() { window.open(documentApi.downloadExcel(route.params.id), "_blank") }
function downloadCsv() { window.open(documentApi.downloadCsv(route.params.id), "_blank") }

const entryColors = [
  "bg-blue-600", "bg-purple-600", "bg-green-600", "bg-orange-500",
  "bg-pink-600", "bg-teal-600", "bg-red-600", "bg-indigo-600",
]
const colorCache = {}
function getEntryColor(courseId) {
  if (!colorCache[courseId]) {
    colorCache[courseId] = entryColors[Object.keys(colorCache).length % entryColors.length]
  }
  return colorCache[courseId]
}
</script>

<template>
  <div class="space-y-6">
    <!-- Loading -->
    <div v-if="loading" class="animate-pulse space-y-4">
      <div class="h-8 bg-gray-200 rounded w-1/3"></div>
      <div class="card h-96 bg-gray-200 rounded"></div>
    </div>

    <template v-else-if="store.currentTimetable">
      <!-- Header -->
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 class="text-2xl font-bold text-gray-900">{{ store.currentTimetable.name }}</h1>
          <p class="text-gray-500 text-sm">
            {{ store.currentTimetable.department?.name }} ·
            Semester {{ store.currentTimetable.semester }} ·
            {{ store.currentTimetable.academic_year }}
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <button @click="detectConflicts" :disabled="conflictsLoading" class="btn-secondary flex items-center gap-2">
            🔍 {{ conflictsLoading ? "Checking…" : "Check Conflicts" }}
          </button>
          <RouterLink to="/ai-assistant" class="btn-secondary flex items-center gap-2">🤖 AI Adjust</RouterLink>
          <div class="relative group">
            <button class="btn-primary flex items-center gap-2">📥 Export ▼</button>
            <div class="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10 hidden group-hover:block min-w-[160px]">
              <button @click="downloadPdf" class="w-full text-left px-4 py-2 text-sm hover:bg-gray-50">📄 PDF</button>
              <button @click="downloadExcel" class="w-full text-left px-4 py-2 text-sm hover:bg-gray-50">📊 Excel</button>
              <button @click="downloadCsv" class="w-full text-left px-4 py-2 text-sm hover:bg-gray-50">📋 CSV</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Stats bar -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="card text-center">
          <p class="text-2xl font-bold text-blue-600">{{ (store.currentTimetable.fitness_score * 100).toFixed(1) }}%</p>
          <p class="text-xs text-gray-500 mt-1">Fitness Score</p>
        </div>
        <div class="card text-center">
          <p class="text-2xl font-bold text-gray-900">{{ store.currentTimetable.entries?.length || 0 }}</p>
          <p class="text-xs text-gray-500 mt-1">Total Sessions</p>
        </div>
        <div class="card text-center">
          <p class="text-2xl font-bold text-gray-900">{{ store.currentTimetable.generations_run }}</p>
          <p class="text-xs text-gray-500 mt-1">GA Generations</p>
        </div>
        <div class="card text-center">
          <p class="text-2xl font-bold text-gray-900">{{ store.currentTimetable.generation_time_seconds?.toFixed(1) }}s</p>
          <p class="text-xs text-gray-500 mt-1">Generation Time</p>
        </div>
      </div>

      <!-- Conflicts -->
      <div v-if="store.conflicts.length" class="card border-red-200 bg-red-50">
        <h3 class="font-semibold text-red-900 mb-3">⚠️ {{ store.conflicts.length }} Conflict(s) Detected</h3>
        <ul class="space-y-2">
          <li v-for="(c, i) in store.conflicts" :key="i" class="text-sm text-red-700 bg-white rounded-lg p-2 border border-red-200">
            <strong>{{ c.type?.replace("_", " ").toUpperCase() }}:</strong> {{ c.message }}
          </li>
        </ul>
        <RouterLink to="/ai-assistant" class="mt-3 inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 font-medium">
          🤖 Ask AI to resolve conflicts →
        </RouterLink>
      </div>

      <!-- Timetable Grid -->
      <div class="card overflow-hidden p-0">
        <div class="p-4 border-b border-gray-200">
          <h2 class="font-semibold text-gray-900">Weekly Schedule Grid</h2>
          <p class="text-xs text-gray-500 mt-1">Drag entries to rearrange (click to select, then click target slot)</p>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full border-collapse min-w-[700px]">
            <thead>
              <tr>
                <th class="bg-gray-50 border border-gray-200 p-3 text-left text-xs font-semibold text-gray-600 w-28">Time</th>
                <th v-for="day in DAYS" :key="day" class="bg-gray-50 border border-gray-200 p-3 text-center text-xs font-semibold text-gray-600">
                  {{ day }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="slot in timeSlots" :key="slot.id" :class="slot.is_break ? 'bg-yellow-50' : ''">
                <td class="border border-gray-200 p-2 text-xs font-medium text-gray-600 whitespace-nowrap">
                  {{ slot.start_time }} – {{ slot.end_time }}
                  <span v-if="slot.is_break" class="block text-yellow-600 font-semibold">BREAK</span>
                </td>
                <td v-for="day in DAYS" :key="day" class="timetable-cell">
                  <div
                    v-if="timetableGrid[`${day}__${slot.start_time}`]"
                    :class="['timetable-entry', getEntryColor(timetableGrid[`${day}__${slot.start_time}`]?.course?.id)]"
                  >
                    <p class="font-bold truncate">{{ timetableGrid[`${day}__${slot.start_time}`]?.course?.code }}</p>
                    <p class="truncate opacity-90">{{ timetableGrid[`${day}__${slot.start_time}`]?.course?.name }}</p>
                    <p class="opacity-75 truncate">🚪 {{ timetableGrid[`${day}__${slot.start_time}`]?.room?.code }}</p>
                    <p class="opacity-75 truncate">👤 {{ timetableGrid[`${day}__${slot.start_time}`]?.lecturer?.name?.split(" ")[0] }}</p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
