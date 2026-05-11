<script setup>
import { onMounted, ref } from "vue"
import { auditApi } from "@/api/client"

const loading = ref(true)
const logs = ref([])
const stats = ref(null)

async function loadAudit() {
  loading.value = true
  try {
    const [logsRes, statsRes] = await Promise.all([
      auditApi.list({ per_page: 100 }),
      auditApi.stats(),
    ])
    logs.value = logsRes.data.data || []
    stats.value = statsRes.data.data || {}
  } finally {
    loading.value = false
  }
}

onMounted(loadAudit)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Audit Logs</h1>
      <p class="text-sm text-gray-500 mt-1">Security events and administrative activity traceability.</p>
    </div>

    <div class="grid md:grid-cols-3 gap-4">
      <div class="card">
        <p class="text-sm text-gray-500">Total Events</p>
        <p class="text-3xl font-bold">{{ stats?.total ?? 0 }}</p>
      </div>
      <div class="card md:col-span-2">
        <p class="text-sm text-gray-500 mb-2">Events by Service</p>
        <div class="flex flex-wrap gap-2">
          <span v-for="(count, service) in stats?.by_service || {}" :key="service" class="badge-info">
            {{ service || "unknown" }}: {{ count }}
          </span>
        </div>
      </div>
    </div>

    <div class="card">
      <h2 class="font-semibold mb-3">Recent Activity</h2>
      <div v-if="loading" class="text-sm text-gray-500">Loading logs...</div>
      <div v-else-if="!logs.length" class="text-sm text-gray-500">No logs found.</div>
      <div v-else class="space-y-2">
        <div v-for="log in logs" :key="log.id" class="p-3 border border-gray-200 rounded-lg">
          <div class="flex items-center justify-between gap-2">
            <p class="font-medium">{{ log.action }}</p>
            <span :class="log.status === 'success' ? 'badge-success' : 'badge-error'">{{ log.status }}</span>
          </div>
          <p class="text-xs text-gray-500 mt-1">{{ log.service }} | {{ log.created_at }}</p>
          <p class="text-sm mt-2">{{ log.description || "No description" }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
