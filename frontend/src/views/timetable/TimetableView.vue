<script setup>
import { ref, onMounted } from "vue"
import { useTimetableStore } from "@/stores/timetable"

const store = useTimetableStore()
const loading = ref(true)
const statusFilter = ref("")

onMounted(async () => {
  await store.fetchTimetables()
  loading.value = false
})

const statusColors = {
  active: "badge-success",
  draft: "badge-warning",
  generating: "badge-info",
  failed: "badge-error",
  archived: "bg-gray-100 text-gray-600 badge",
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Timetables</h1>
        <p class="text-gray-500 text-sm mt-1">All generated timetables across departments</p>
      </div>
      <RouterLink to="/generate" class="btn-primary flex items-center gap-2">
        <span>⚡</span> Generate New
      </RouterLink>
    </div>

    <!-- Filters -->
    <div class="card p-4">
      <select v-model="statusFilter" class="input w-48">
        <option value="">All statuses</option>
        <option value="active">Active</option>
        <option value="draft">Draft</option>
        <option value="generating">Generating</option>
        <option value="archived">Archived</option>
      </select>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 5" :key="i" class="card animate-pulse flex gap-4">
        <div class="w-12 h-12 bg-gray-200 rounded-xl"></div>
        <div class="flex-1 space-y-2">
          <div class="h-4 bg-gray-200 rounded w-1/3"></div>
          <div class="h-3 bg-gray-200 rounded w-1/4"></div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!store.timetables.length" class="card text-center py-12">
      <div class="text-5xl mb-4">📅</div>
      <h3 class="font-semibold text-gray-900 mb-2">No timetables yet</h3>
      <p class="text-gray-500 text-sm mb-4">Generate your first timetable using the Genetic Algorithm engine.</p>
      <RouterLink to="/generate" class="btn-primary inline-flex items-center gap-2">
        <span>⚡</span> Generate First Timetable
      </RouterLink>
    </div>

    <!-- Timetable list -->
    <div v-else class="space-y-3">
      <RouterLink
        v-for="tt in store.timetables.filter(t => !statusFilter || t.status === statusFilter)"
        :key="tt.id"
        :to="`/timetable/${tt.id}`"
        class="card flex items-center gap-4 hover:shadow-md transition-all hover:-translate-y-0.5 cursor-pointer"
      >
        <div class="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center text-2xl flex-shrink-0">📅</div>
        <div class="flex-1 min-w-0">
          <h3 class="font-semibold text-gray-900 truncate">{{ tt.name }}</h3>
          <p class="text-sm text-gray-500">
            {{ tt.department?.name }} · Semester {{ tt.semester }} · {{ tt.academic_year }}
          </p>
        </div>
        <div class="flex items-center gap-4 flex-shrink-0">
          <div class="text-right hidden md:block">
            <p class="text-sm font-medium text-gray-900">{{ tt.fitness_score ? (tt.fitness_score * 100).toFixed(1) + "%" : "—" }}</p>
            <p class="text-xs text-gray-400">fitness score</p>
          </div>
          <span :class="statusColors[tt.status] || 'badge-info'">{{ tt.status }}</span>
        </div>
      </RouterLink>
    </div>
  </div>
</template>
