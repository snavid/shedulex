<script setup>
import { computed, ref, onMounted } from "vue"
import { useAuthStore } from "@/stores/auth"
import { analyticsApi } from "@/api/client"
import { useRouter } from "vue-router"

const auth = useAuthStore()
const router = useRouter()
const stats = ref(null)
const loading = ref(true)

const quickActions = computed(() => {
  const actions = [
    { label: "AI Assistant", icon: "🤖", to: "/ai-assistant", color: "bg-purple-600" },
    { label: "View Calendar", icon: "🗓️", to: "/calendar", color: "bg-green-600" },
    { label: "Analytics", icon: "📈", to: "/analytics", color: "bg-orange-600" },
  ]
  if (auth.isTimetableOfficer) {
    actions.unshift({ label: "Generate Timetable", icon: "⚡", to: "/generate", color: "bg-blue-600" })
  }
  return actions
})

onMounted(async () => {
  try {
    const { data } = await analyticsApi.overview()
    stats.value = data.data
  } catch {
    stats.value = null
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="space-y-6 animate-fade-in">
    <!-- Header -->
    <div>
      <h1 class="text-2xl font-bold text-gray-900">
        Welcome back, {{ auth.user?.first_name }}! 👋
      </h1>
      <p class="text-gray-500 text-sm mt-1">Here's what's happening in your timetable system.</p>
    </div>

    <!-- Stats Grid -->
    <div v-if="loading" class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div v-for="i in 4" :key="i" class="card animate-pulse">
        <div class="h-4 bg-gray-200 rounded w-3/4 mb-3"></div>
        <div class="h-8 bg-gray-200 rounded w-1/2"></div>
      </div>
    </div>
    <div v-else-if="stats" class="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="card hover:shadow-md transition-shadow">
        <div class="flex items-center justify-between mb-3">
          <span class="text-sm font-medium text-gray-500">Active Timetables</span>
          <span class="text-2xl">📅</span>
        </div>
        <p class="text-3xl font-bold text-gray-900">{{ stats.active_timetables }}</p>
        <p class="text-xs text-gray-400 mt-1">of {{ stats.total_timetables }} total</p>
      </div>
      <div class="card hover:shadow-md transition-shadow">
        <div class="flex items-center justify-between mb-3">
          <span class="text-sm font-medium text-gray-500">Total Courses</span>
          <span class="text-2xl">📚</span>
        </div>
        <p class="text-3xl font-bold text-gray-900">{{ stats.total_courses }}</p>
      </div>
      <div class="card hover:shadow-md transition-shadow">
        <div class="flex items-center justify-between mb-3">
          <span class="text-sm font-medium text-gray-500">Lecturers</span>
          <span class="text-2xl">👨‍🏫</span>
        </div>
        <p class="text-3xl font-bold text-gray-900">{{ stats.total_lecturers }}</p>
      </div>
      <div class="card hover:shadow-md transition-shadow">
        <div class="flex items-center justify-between mb-3">
          <span class="text-sm font-medium text-gray-500">Avg. Fitness Score</span>
          <span class="text-2xl">🎯</span>
        </div>
        <p class="text-3xl font-bold text-gray-900">{{ (stats.average_fitness_score * 100).toFixed(1) }}%</p>
        <span :class="['badge mt-1', stats.optimization_quality === 'Excellent' ? 'badge-success' : stats.optimization_quality === 'Good' ? 'badge-info' : 'badge-warning']">
          {{ stats.optimization_quality }}
        </span>
      </div>
    </div>

    <!-- Quick Actions -->
    <div>
      <h2 class="text-lg font-semibold text-gray-900 mb-4">Quick Actions</h2>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <RouterLink
          v-for="action in quickActions"
          :key="action.to"
          :to="action.to"
          class="card hover:shadow-md transition-all hover:-translate-y-0.5 text-center cursor-pointer"
        >
          <div :class="['w-12 h-12 rounded-xl mx-auto mb-3 flex items-center justify-center text-2xl', action.color]">
            {{ action.icon }}
          </div>
          <p class="text-sm font-medium text-gray-700">{{ action.label }}</p>
        </RouterLink>
      </div>
    </div>

    <!-- System Status -->
    <div class="card">
      <h2 class="text-lg font-semibold text-gray-900 mb-4">System Status</h2>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div v-for="service in ['Auth', 'Timetable Engine', 'AI Assistant', 'Notifications']" :key="service"
          class="flex items-center gap-2 p-3 bg-gray-50 rounded-lg">
          <div class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
          <span class="text-sm text-gray-600">{{ service }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
