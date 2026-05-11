<script setup>
import { onMounted, ref } from "vue"
import { analyticsApi } from "@/api/client"

const loading = ref(true)
const overview = ref(null)
const roomUtilization = ref([])
const lecturerWorkload = ref([])

async function loadAnalytics() {
  loading.value = true
  try {
    const [overviewRes, roomsRes, lecturersRes] = await Promise.all([
      analyticsApi.overview(),
      analyticsApi.roomUtilization(),
      analyticsApi.lecturerWorkload(),
    ])
    overview.value = overviewRes.data.data
    roomUtilization.value = roomsRes.data.data || []
    lecturerWorkload.value = lecturersRes.data.data || []
  } finally {
    loading.value = false
  }
}

onMounted(loadAnalytics)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Analytics</h1>
      <p class="text-sm text-gray-500 mt-1">Scheduling efficiency, resource utilization, and workload insights.</p>
    </div>

    <div v-if="loading" class="text-sm text-gray-500">Loading analytics...</div>

    <template v-else>
      <div class="grid md:grid-cols-3 gap-4">
        <div class="card">
          <p class="text-sm text-gray-500">Active Timetables</p>
          <p class="text-3xl font-bold">{{ overview?.active_timetables ?? 0 }}</p>
        </div>
        <div class="card">
          <p class="text-sm text-gray-500">Average Fitness</p>
          <p class="text-3xl font-bold">{{ ((overview?.average_fitness_score ?? 0) * 100).toFixed(1) }}%</p>
        </div>
        <div class="card">
          <p class="text-sm text-gray-500">Optimization Quality</p>
          <p class="text-2xl font-semibold">{{ overview?.optimization_quality ?? "N/A" }}</p>
        </div>
      </div>

      <div class="grid lg:grid-cols-2 gap-4">
        <div class="card">
          <h2 class="font-semibold mb-3">Room Utilization</h2>
          <div v-if="!roomUtilization.length" class="text-sm text-gray-500">No room data.</div>
          <div v-else class="space-y-2">
            <div v-for="room in roomUtilization" :key="room.name" class="p-2 border border-gray-200 rounded text-sm flex justify-between">
              <span>{{ room.name }} (cap {{ room.capacity }})</span>
              <span class="font-semibold">{{ room.bookings }} bookings</span>
            </div>
          </div>
        </div>

        <div class="card">
          <h2 class="font-semibold mb-3">Lecturer Workload</h2>
          <div v-if="!lecturerWorkload.length" class="text-sm text-gray-500">No lecturer data.</div>
          <div v-else class="space-y-2">
            <div v-for="lec in lecturerWorkload" :key="lec.name" class="p-2 border border-gray-200 rounded text-sm flex justify-between">
              <span>{{ lec.name }}</span>
              <span class="font-semibold">{{ lec.hours }}h / {{ lec.max }}h ({{ lec.utilization_pct }}%)</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
