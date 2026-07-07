<script setup>
import { computed, onMounted, ref, watch } from "vue"
import { useToast } from "vue-toastification"
import { requestsApi, getErrorMessage } from "@/api/client"

const toast = useToast()
const loading = ref(true)
const requests = ref([])
const deciding = ref(null)
const noteDrafts = ref({})
const activeTab = ref("pending_admin") // pending_admin | approved | rejected

const CATEGORY_LABELS = {
  schedule_change: "Schedule Change",
  substitution_leave: "Substitution / Leave",
  room_issue: "Room Issue",
  other: "Other",
}
const TAB_LABELS = {
  pending_admin: "Pending Admin",
  approved: "Approved",
  rejected: "Rejected",
}

async function load() {
  loading.value = true
  try {
    const { data } = await requestsApi.list({ status: activeTab.value })
    requests.value = data.data || []
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load requests."))
  } finally {
    loading.value = false
  }
}

async function decide(req, decision) {
  deciding.value = req.id
  try {
    await requestsApi.adminDecide(req.id, { decision, note: noteDrafts.value[req.id] || "" })
    toast.success(decision === "approve" ? "Request approved." : "Request rejected.")
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to record decision."))
  } finally {
    deciding.value = null
  }
}

watch(activeTab, load)
onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Requests</h1>
      <p class="text-sm text-gray-500 mt-1">Lecturer requests already cleared by their department HOD.</p>
    </div>

    <div class="flex gap-1 p-1 bg-gray-100 rounded-xl w-fit">
      <button
        v-for="key in ['pending_admin', 'approved', 'rejected']"
        :key="key"
        @click="activeTab = key"
        :class="activeTab === key ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
        class="px-4 py-2 rounded-lg text-sm font-semibold transition-all"
      >
        {{ TAB_LABELS[key] }}
      </button>
    </div>

    <div v-if="loading" class="card animate-pulse space-y-3">
      <div v-for="i in 3" :key="i" class="h-20 bg-gray-100 rounded-lg"></div>
    </div>

    <div v-else-if="!requests.length" class="card text-center py-14">
      <p class="text-sm text-gray-500">No requests in this category.</p>
    </div>

    <div v-else class="space-y-4">
      <div v-for="r in requests" :key="r.id" class="card space-y-3">
        <div class="flex items-start justify-between gap-2">
          <div>
            <p class="text-sm font-semibold text-gray-900">{{ r.lecturer_name || "Lecturer" }}</p>
            <p class="text-xs text-gray-500">{{ r.department?.name || "" }}</p>
            <span class="inline-block mt-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
              {{ CATEGORY_LABELS[r.category] || r.category }}
            </span>
          </div>
          <span class="text-xs text-gray-400">{{ new Date(r.created_at).toLocaleString() }}</span>
        </div>
        <p class="text-sm text-gray-700">{{ r.message }}</p>
        <p v-if="r.hod_note" class="text-xs text-gray-500">HOD note: {{ r.hod_note }}</p>

        <template v-if="activeTab === 'pending_admin'">
          <div>
            <label class="label">Note (optional)</label>
            <input v-model="noteDrafts[r.id]" class="input" placeholder="Add a note…" />
          </div>
          <div class="flex gap-2">
            <button
              class="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm font-semibold transition-colors disabled:opacity-50"
              :disabled="deciding === r.id"
              @click="decide(r, 'approve')"
            >
              Approve
            </button>
            <button
              class="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 text-sm font-semibold transition-colors disabled:opacity-50"
              :disabled="deciding === r.id"
              @click="decide(r, 'reject')"
            >
              Reject
            </button>
          </div>
        </template>
        <p v-else-if="r.admin_note" class="text-xs text-gray-500">Admin note: {{ r.admin_note }}</p>
      </div>
    </div>
  </div>
</template>
