<script setup>
import { computed, onMounted, ref } from "vue"
import { auditApi, usersApi } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const logs = ref([])
const stats = ref(null)
const users = ref([])
const meta = ref({ page: 1, per_page: 50, total: 0, pages: 0 })

const filters = ref({
  user_id: "",
  service: "",
  action: "",
  status: "",
  search: "",
  from_date: "",
  to_date: "",
})

const serviceOptions = computed(() => {
  const keys = Object.keys(stats.value?.by_service || {})
  return keys.filter(Boolean).sort()
})

function buildParams(page = 1) {
  const params = { page, per_page: 50 }
  for (const [key, value] of Object.entries(filters.value)) {
    if (value) params[key] = value
  }
  return params
}

function formatTime(iso) {
  if (!iso) return "—"
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

function formatAction(action) {
  return (action || "").replace(":", " · ").replace(/\./g, " ")
}

async function loadUsers() {
  try {
    const { data } = await usersApi.list({ per_page: 200 })
    users.value = data.data || []
  } catch {
    users.value = []
  }
}

async function loadAudit(page = 1) {
  loading.value = true
  const params = buildParams(page)
  try {
    const [logsRes, statsRes] = await Promise.all([
      auditApi.list(params),
      auditApi.stats(params),
    ])
    logs.value = logsRes.data.data || []
    stats.value = statsRes.data.data || {}
    meta.value = logsRes.data.meta || { page: 1, per_page: 50, total: 0, pages: 0 }
  } catch (e) {
    toast.error("Failed to load audit logs.")
    logs.value = []
    stats.value = { total: 0, by_service: {}, by_action: {} }
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  loadAudit(1)
}

function clearFilters() {
  filters.value = {
    user_id: "",
    service: "",
    action: "",
    status: "",
    search: "",
    from_date: "",
    to_date: "",
  }
  loadAudit(1)
}

function goToPage(page) {
  if (page < 1 || page > meta.value.pages) return
  loadAudit(page)
}

onMounted(async () => {
  await loadUsers()
  await loadAudit()
})
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Audit Logs</h1>
      <p class="text-sm text-gray-500 mt-1">
        Track who did what, when, and from where across your university.
      </p>
    </div>

    <div class="grid md:grid-cols-3 gap-4">
      <div class="card">
        <p class="text-sm text-gray-500">Matching Events</p>
        <p class="text-3xl font-bold">{{ stats?.total ?? 0 }}</p>
      </div>
      <div class="card md:col-span-2">
        <p class="text-sm text-gray-500 mb-2">Events by Service</p>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="(count, service) in stats?.by_service || {}"
            :key="service"
            class="badge-info cursor-pointer"
            @click="filters.service = service; applyFilters()"
          >
            {{ service || "unknown" }}: {{ count }}
          </span>
          <span v-if="!Object.keys(stats?.by_service || {}).length" class="text-sm text-gray-400">
            No events for current filters
          </span>
        </div>
      </div>
    </div>

    <!-- Filters -->
    <div class="card space-y-4">
      <div class="flex flex-wrap items-end gap-3">
        <div class="min-w-[180px] flex-1">
          <label class="label">User</label>
          <select v-model="filters.user_id" class="input">
            <option value="">All users</option>
            <option v-for="u in users" :key="u.id" :value="u.id">
              {{ u.first_name }} {{ u.last_name }} ({{ u.email }})
            </option>
          </select>
        </div>
        <div class="min-w-[140px]">
          <label class="label">From date</label>
          <input v-model="filters.from_date" type="date" class="input" />
        </div>
        <div class="min-w-[140px]">
          <label class="label">To date</label>
          <input v-model="filters.to_date" type="date" class="input" />
        </div>
        <div class="min-w-[140px]">
          <label class="label">Service</label>
          <select v-model="filters.service" class="input">
            <option value="">All services</option>
            <option v-for="svc in serviceOptions" :key="svc" :value="svc">{{ svc }}</option>
            <option value="auth-service">auth-service</option>
            <option value="timetable-engine">timetable-engine</option>
          </select>
        </div>
        <div class="min-w-[120px]">
          <label class="label">Status</label>
          <select v-model="filters.status" class="input">
            <option value="">All</option>
            <option value="success">Success</option>
            <option value="failure">Failure</option>
          </select>
        </div>
      </div>

      <div class="flex flex-wrap items-end gap-3">
        <div class="min-w-[180px] flex-1">
          <label class="label">Action contains</label>
          <input v-model="filters.action" class="input" placeholder="e.g. auth.login, post:users" />
        </div>
        <div class="min-w-[180px] flex-1">
          <label class="label">Search</label>
          <input v-model="filters.search" class="input" placeholder="Description, email, name…" />
        </div>
        <button class="btn-primary" @click="applyFilters">Apply filters</button>
        <button class="btn-secondary" @click="clearFilters">Clear</button>
      </div>
    </div>

    <!-- Log table -->
    <div class="card overflow-hidden !p-0">
      <div class="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
        <h2 class="font-semibold">Activity log</h2>
        <p class="text-xs text-gray-500">
          {{ meta.total }} event{{ meta.total === 1 ? "" : "s" }}
        </p>
      </div>

      <div v-if="loading" class="p-6 text-sm text-gray-500">Loading logs…</div>
      <div v-else-if="!logs.length" class="p-10 text-center text-sm text-gray-500">
        No logs match your filters. Try clearing filters or perform an admin action.
      </div>

      <div v-else class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead class="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th class="px-4 py-3 font-semibold">Time</th>
              <th class="px-4 py-3 font-semibold">User</th>
              <th class="px-4 py-3 font-semibold">Action</th>
              <th class="px-4 py-3 font-semibold">Service</th>
              <th class="px-4 py-3 font-semibold">Details</th>
              <th class="px-4 py-3 font-semibold">Status</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="log in logs" :key="log.id" class="hover:bg-gray-50/80">
              <td class="px-4 py-3 whitespace-nowrap text-gray-600">
                {{ formatTime(log.created_at) }}
              </td>
              <td class="px-4 py-3">
                <p class="font-medium text-gray-900">{{ log.display_user || "System" }}</p>
                <p v-if="log.user_email && log.user_email !== log.display_user" class="text-xs text-gray-500">
                  {{ log.user_email }}
                </p>
              </td>
              <td class="px-4 py-3">
                <span class="font-medium text-gray-800">{{ formatAction(log.action) }}</span>
                <p v-if="log.resource_type" class="text-xs text-gray-500 mt-0.5">
                  {{ log.resource_type }}<span v-if="log.resource_id"> · {{ log.resource_id.slice(0, 8) }}…</span>
                </p>
              </td>
              <td class="px-4 py-3 text-gray-600">{{ log.service || "—" }}</td>
              <td class="px-4 py-3 max-w-xs">
                <p class="text-gray-700 truncate" :title="log.description">{{ log.description || "—" }}</p>
                <p v-if="log.ip_address" class="text-xs text-gray-400 mt-0.5">IP {{ log.ip_address }}</p>
              </td>
              <td class="px-4 py-3">
                <span :class="log.status === 'success' ? 'badge-success' : 'badge-error'">
                  {{ log.status }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div
        v-if="meta.pages > 1"
        class="flex items-center justify-between border-t border-gray-200 px-4 py-3 text-sm"
      >
        <button
          class="btn-secondary text-xs"
          :disabled="meta.page <= 1"
          @click="goToPage(meta.page - 1)"
        >
          Previous
        </button>
        <span class="text-gray-500">Page {{ meta.page }} of {{ meta.pages }}</span>
        <button
          class="btn-secondary text-xs"
          :disabled="meta.page >= meta.pages"
          @click="goToPage(meta.page + 1)"
        >
          Next
        </button>
      </div>
    </div>
  </div>
</template>
