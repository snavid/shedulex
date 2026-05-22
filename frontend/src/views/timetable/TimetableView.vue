<script setup>
import { ref, computed, onMounted } from "vue"
import { useTimetableStore } from "@/stores/timetable"
import { useAuthStore } from "@/stores/auth"
import { getErrorMessage } from "@/api/client"

const store = useTimetableStore()
const auth = useAuthStore()
const loading = ref(true)
const statusFilter = ref("")
const search = ref("")
const error = ref("")

onMounted(async () => {
  loading.value = true
  error.value = ""
  try {
    await store.fetchTimetables()
  } catch (e) {
    error.value = getErrorMessage(e, "Failed to load timetables.")
  } finally {
    loading.value = false
  }
})

const STATUS_COLORS = {
  active: "badge-success",
  draft: "badge-warning",
  generating: "badge-info",
  failed: "badge-error",
  archived: "badge bg-gray-100 text-gray-600",
}

const filtered = computed(() => {
  let list = store.timetables
  if (statusFilter.value) list = list.filter((t) => t.status === statusFilter.value)
  if (search.value) {
    const q = search.value.toLowerCase()
    list = list.filter(
      (t) =>
        t.name?.toLowerCase().includes(q) ||
        t.department?.name?.toLowerCase().includes(q) ||
        t.academic_year?.toLowerCase().includes(q),
    )
  }
  return list
})

const counts = computed(() => {
  const all = store.timetables
  return {
    total: all.length,
    active: all.filter((t) => t.status === "active").length,
    draft: all.filter((t) => t.status === "draft").length,
    generating: all.filter((t) => t.status === "generating").length,
  }
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Timetables</h1>
        <p class="text-gray-500 text-sm mt-1">All generated timetables across departments</p>
      </div>
      <RouterLink v-if="auth.isTimetableOfficer" to="/generate" class="btn-primary flex items-center gap-2">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        Generate New
      </RouterLink>
    </div>

    <!-- Stats row -->
    <div v-if="!loading && store.timetables.length" class="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <div class="card py-3 text-center">
        <p class="text-2xl font-bold text-gray-900">{{ counts.total }}</p>
        <p class="text-xs text-gray-500 mt-0.5">Total</p>
      </div>
      <div class="card py-3 text-center">
        <p class="text-2xl font-bold text-green-600">{{ counts.active }}</p>
        <p class="text-xs text-gray-500 mt-0.5">Active</p>
      </div>
      <div class="card py-3 text-center">
        <p class="text-2xl font-bold text-amber-500">{{ counts.draft }}</p>
        <p class="text-xs text-gray-500 mt-0.5">Draft</p>
      </div>
      <div class="card py-3 text-center">
        <p class="text-2xl font-bold text-blue-500">{{ counts.generating }}</p>
        <p class="text-xs text-gray-500 mt-0.5">Generating</p>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3">
      <input
        v-model="search"
        class="input flex-1 min-w-[180px] max-w-xs"
        placeholder="Search by name, department…"
      />
      <select v-model="statusFilter" class="input w-auto">
        <option value="">All statuses</option>
        <option value="active">Active</option>
        <option value="draft">Draft</option>
        <option value="generating">Generating</option>
        <option value="archived">Archived</option>
        <option value="failed">Failed</option>
      </select>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 5" :key="i" class="card animate-pulse flex gap-4 items-center">
        <div class="w-12 h-12 bg-gray-200 rounded-xl flex-shrink-0"></div>
        <div class="flex-1 space-y-2">
          <div class="h-4 bg-gray-200 rounded w-1/3"></div>
          <div class="h-3 bg-gray-200 rounded w-1/4"></div>
        </div>
        <div class="w-20 h-6 bg-gray-200 rounded-full"></div>
      </div>
    </div>

    <div v-else-if="error" class="card border-red-200 bg-red-50 text-red-700 text-sm flex items-center gap-3">
      <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      {{ error }}
    </div>

    <!-- Empty state -->
    <div v-else-if="!store.timetables.length" class="card text-center py-14">
      <div class="w-16 h-16 mx-auto bg-blue-50 rounded-2xl flex items-center justify-center mb-4">
        <svg class="w-8 h-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      </div>
      <h3 class="font-semibold text-gray-900 mb-1">No timetables yet</h3>
      <p class="text-gray-500 text-sm mb-5">Generate your first timetable using the Genetic Algorithm engine.</p>
      <RouterLink v-if="auth.isTimetableOfficer" to="/generate" class="btn-primary inline-flex items-center gap-2">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        Generate First Timetable
      </RouterLink>
    </div>

    <!-- No results from filter -->
    <div v-else-if="!filtered.length" class="card text-center py-10 text-sm text-gray-500">
      No timetables match your filters.
      <button class="text-blue-600 hover:underline ml-1" @click="search = ''; statusFilter = ''">Clear filters</button>
    </div>

    <!-- Timetable list -->
    <div v-else class="space-y-3">
      <RouterLink
        v-for="tt in filtered"
        :key="tt.id"
        :to="`/timetable/${tt.id}`"
        class="card flex items-center gap-4 hover:shadow-md transition-all hover:-translate-y-0.5 cursor-pointer"
      >
        <div class="w-12 h-12 rounded-xl flex-shrink-0 flex items-center justify-center"
          :class="tt.status === 'active' ? 'bg-blue-100' : tt.status === 'failed' ? 'bg-red-100' : 'bg-gray-100'">
          <svg class="w-6 h-6" :class="tt.status === 'active' ? 'text-blue-600' : tt.status === 'failed' ? 'text-red-500' : 'text-gray-400'"
            fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </div>
        <div class="flex-1 min-w-0">
          <h3 class="font-semibold text-gray-900 truncate">{{ tt.name }}</h3>
          <p class="text-sm text-gray-500">
            {{ tt.department?.name || "—" }}
            <span v-if="tt.semester"> · Semester {{ tt.semester }}</span>
            <span v-if="tt.academic_year"> · {{ tt.academic_year }}</span>
          </p>
        </div>
        <div class="flex items-center gap-4 flex-shrink-0">
          <div class="text-right hidden md:block">
            <p class="text-sm font-bold" :class="tt.fitness_score >= 0.8 ? 'text-green-600' : tt.fitness_score >= 0.5 ? 'text-amber-600' : 'text-gray-400'">
              {{ tt.fitness_score ? (tt.fitness_score * 100).toFixed(1) + "%" : "—" }}
            </p>
            <p class="text-xs text-gray-400">fitness</p>
          </div>
          <span :class="STATUS_COLORS[tt.status] || 'badge-info'">{{ tt.status }}</span>
          <svg class="w-4 h-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </RouterLink>
    </div>
  </div>
</template>
