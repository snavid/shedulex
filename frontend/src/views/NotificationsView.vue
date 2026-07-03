<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue"
import { useAuthStore } from "@/stores/auth"
import { notificationApi, resourcesApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"

const auth = useAuthStore()
const toast = useToast()
const loading = ref(true)
const sending = ref(false)
const notifications = ref([])
const activeTab = ref("broadcast")

const departments = ref([])
const programs = ref([])

const form = reactive({
  audience: "students",
  department_id: "",
  program_id: "",
  channel: "sms",
  subject: "",
  body: "",
})

const showFilters = computed(() => ["students", "lecturers", "hod"].includes(form.audience))

async function loadDepartments() {
  if (!auth.user?.university_id) return
  try {
    const { data } = await resourcesApi.departments({ university_id: auth.user.university_id })
    departments.value = data.data || []
  } catch {}
}

watch(() => form.department_id, async (deptId) => {
  programs.value = []
  form.program_id = ""
  if (!deptId) return
  try {
    const { data } = await resourcesApi.programs({ department_id: deptId })
    programs.value = data.data || []
  } catch {}
})

async function loadNotifications() {
  loading.value = true
  try {
    const { data } = await notificationApi.list()
    notifications.value = data.data || []
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load notifications."))
  } finally {
    loading.value = false
  }
}

async function sendBroadcast() {
  if (!form.subject || !form.body) {
    toast.error("Subject and message are required.")
    return
  }
  sending.value = true
  try {
    await notificationApi.broadcast({
      subject: form.subject,
      body: form.body,
      audience: form.audience,
      channel: form.channel,
      department_id: form.department_id || undefined,
      program_id: form.program_id || undefined,
    })
    toast.success("Broadcast queued. Messages will be sent shortly.")
    Object.assign(form, {
      audience: "students",
      department_id: "",
      program_id: "",
      channel: "sms",
      subject: "",
      body: "",
    })
    activeTab.value = "history"
    await loadNotifications()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to queue broadcast."))
  } finally {
    sending.value = false
  }
}

function statusColor(status) {
  const map = {
    sent: "badge-success",
    pending: "badge-warning",
    failed: "badge-error",
  }
  return map[status] || "badge-info"
}

function channelIcon(channel) {
  const map = { email: "📧", sms: "💬", both: "📨" }
  return map[channel] || "📩"
}

function formatDate(dt) {
  if (!dt) return ""
  return new Date(dt).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  })
}

onMounted(async () => {
  await loadDepartments()
  await loadNotifications()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Notifications</h1>
        <p class="text-sm text-gray-500 mt-1">Broadcast SMS and email announcements to your university audience.</p>
      </div>
      <button @click="loadNotifications" class="btn-secondary text-sm" :disabled="loading">
        Refresh
      </button>
    </div>

    <div class="flex border-b border-gray-200 gap-1">
      <button
        v-for="tab in [{ id: 'broadcast', label: 'Broadcast' }, { id: 'history', label: `History (${notifications.length})` }]"
        :key="tab.id"
        @click="activeTab = tab.id"
        :class="[
          'px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
          activeTab === tab.id
            ? 'border-blue-600 text-blue-700'
            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300',
        ]"
      >{{ tab.label }}</button>
    </div>

    <div v-if="activeTab === 'broadcast'" class="card space-y-4">
      <h2 class="font-semibold text-gray-900">Broadcast Announcement</h2>

      <div class="grid md:grid-cols-2 gap-4">
        <div>
          <label class="label">Audience</label>
          <select v-model="form.audience" class="input">
            <option value="students">All Students</option>
            <option value="lecturers">All Lecturers</option>
            <option value="hod">Heads of Department</option>
            <option value="all">All Users</option>
          </select>
        </div>
        <div>
          <label class="label">Channel</label>
          <select v-model="form.channel" class="input">
            <option value="sms">SMS only</option>
            <option value="email">Email only</option>
            <option value="both">Email + SMS</option>
          </select>
        </div>
      </div>

      <div v-if="showFilters" class="grid md:grid-cols-2 gap-4 p-4 bg-gray-50 rounded-xl">
        <div>
          <label class="label">Department (optional filter)</label>
          <select v-model="form.department_id" class="input">
            <option value="">All departments</option>
            <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
        </div>
        <div v-if="form.audience === 'students'">
          <label class="label">Program (optional filter)</label>
          <select v-model="form.program_id" class="input" :disabled="!form.department_id">
            <option value="">All programs</option>
            <option v-for="p in programs" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </div>
      </div>

      <div>
        <label class="label">Subject</label>
        <input v-model="form.subject" class="input" placeholder="e.g. Exam schedule update" />
        <p class="text-xs text-gray-500 mt-1">Used as the email title and prefixed in SMS (e.g. "Exam: Starts Monday").</p>
      </div>

      <div>
        <label class="label">Message</label>
        <textarea v-model="form.body" rows="5" class="input" placeholder="Write your broadcast message…"></textarea>
        <p class="text-xs text-gray-500 mt-1">SMS sends this text; the subject above is added as a prefix when set.</p>
      </div>

      <div class="flex justify-end gap-3">
        <button class="btn-secondary" @click="Object.assign(form, { subject: '', body: '' })">Clear</button>
        <button class="btn-primary" :disabled="sending" @click="sendBroadcast">
          {{ sending ? "Queuing…" : "Broadcast Now" }}
        </button>
      </div>
    </div>

    <div v-if="activeTab === 'history'" class="card">
      <div v-if="loading" class="text-sm text-gray-400 py-8 text-center">Loading history…</div>
      <div v-else-if="!notifications.length" class="text-sm text-gray-400 py-12 text-center">
        <p class="text-4xl mb-3">📭</p>
        <p class="font-medium">No notifications sent yet.</p>
        <p class="mt-1">Use the Broadcast tab to send your first announcement.</p>
      </div>
      <div v-else class="divide-y divide-gray-100">
        <div
          v-for="n in notifications"
          :key="n.id"
          class="py-3.5 flex items-start gap-3 hover:bg-gray-50 -mx-6 px-6 transition-colors"
        >
          <span class="text-xl mt-0.5 flex-shrink-0">{{ channelIcon(n.channel) }}</span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <p class="text-sm font-medium text-gray-900 truncate">{{ n.subject || "(No subject)" }}</p>
              <span :class="['badge text-xs', statusColor(n.status)]">{{ n.status }}</span>
              <span class="text-xs text-gray-400">{{ n.notification_type }}</span>
            </div>
            <p class="text-sm text-gray-600 mt-0.5 line-clamp-2">{{ n.body }}</p>
            <p class="text-xs text-gray-400 mt-1">
              <span v-if="n.recipient_phone">📱 {{ n.recipient_phone }}</span>
              <span v-if="n.recipient_email"> · ✉️ {{ n.recipient_email }}</span>
              · {{ formatDate(n.sent_at || n.created_at) }}
            </p>
            <p v-if="n.error_message" class="text-xs text-red-500 mt-1">{{ n.error_message }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
