<script setup>
import { onMounted, ref, reactive } from "vue"
import { notificationApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const sending = ref(false)
const notifications = ref([])
const activeTab = ref("send")

const form = reactive({
  recipient_id: "",
  email: "",
  phone: "",
  channel: "email",
  subject: "",
  body: "",
  notification_type: "general",
  scheduled_at: "",
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

async function sendNotification() {
  if (!form.subject || !form.body) {
    toast.error("Subject and message are required.")
    return
  }
  sending.value = true
  try {
    await notificationApi.send({
      ...form,
      scheduled_at: form.scheduled_at || undefined,
    })
    toast.success("Notification sent.")
    Object.assign(form, { recipient_id: "", email: "", phone: "", channel: "email", subject: "", body: "", notification_type: "general", scheduled_at: "" })
    activeTab.value = "history"
    await loadNotifications()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to send notification."))
  } finally {
    sending.value = false
  }
}

function statusColor(status) {
  const map = {
    sent: "badge-success",
    delivered: "badge-success",
    pending: "badge-warning",
    failed: "badge-error",
    scheduled: "badge-info",
  }
  return map[status] || "badge-info"
}

function channelIcon(channel) {
  const map = { email: "📧", sms: "💬", both: "📨", push: "🔔" }
  return map[channel] || "📩"
}

function formatDate(dt) {
  if (!dt) return ""
  return new Date(dt).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  })
}

onMounted(loadNotifications)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Notifications</h1>
        <p class="text-sm text-gray-500 mt-1">Send reminders, announcements, and track delivery history.</p>
      </div>
      <button @click="loadNotifications" class="btn-secondary text-sm" :disabled="loading">
        Refresh
      </button>
    </div>

    <!-- Tabs -->
    <div class="flex border-b border-gray-200 gap-1">
      <button
        v-for="tab in [{ id: 'send', label: 'Send Notification' }, { id: 'history', label: `History (${notifications.length})` }]"
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

    <!-- Send tab -->
    <div v-if="activeTab === 'send'" class="card space-y-4">
      <h2 class="font-semibold text-gray-900">Compose Notification</h2>

      <div class="grid md:grid-cols-2 gap-4">
        <div>
          <label class="label">Notification Type</label>
          <select v-model="form.notification_type" class="input">
            <option value="general">General</option>
            <option value="reminder">Reminder</option>
            <option value="announcement">Announcement</option>
            <option value="alert">Alert</option>
            <option value="class_update">Class Update</option>
          </select>
        </div>
        <div>
          <label class="label">Channel</label>
          <select v-model="form.channel" class="input">
            <option value="email">📧 Email only</option>
            <option value="sms">💬 SMS only</option>
            <option value="both">📨 Email + SMS</option>
          </select>
        </div>
      </div>

      <div class="p-4 bg-gray-50 rounded-xl space-y-3">
        <h3 class="text-sm font-semibold text-gray-700">Recipient</h3>
        <div class="grid md:grid-cols-2 gap-3">
          <div>
            <label class="label text-xs">Email address</label>
            <input v-model="form.email" class="input" placeholder="recipient@example.com" type="email" />
          </div>
          <div>
            <label class="label text-xs">Phone number (for SMS)</label>
            <input v-model="form.phone" class="input" placeholder="+254 7XX XXX XXX" />
          </div>
          <div class="md:col-span-2">
            <label class="label text-xs">User ID (optional)</label>
            <input v-model="form.recipient_id" class="input" placeholder="Leave blank for anonymous send" />
          </div>
        </div>
      </div>

      <div>
        <label class="label">Subject</label>
        <input v-model="form.subject" class="input" placeholder="e.g. Reminder: Data Structures class at 10am" />
      </div>

      <div>
        <label class="label">Message</label>
        <textarea v-model="form.body" rows="5" class="input" placeholder="Write your message here…"></textarea>
      </div>

      <div>
        <label class="label">Schedule for later (optional)</label>
        <input v-model="form.scheduled_at" type="datetime-local" class="input" />
        <p class="text-xs text-gray-400 mt-1">Leave blank to send immediately.</p>
      </div>

      <div class="flex justify-end gap-3">
        <button class="btn-secondary" @click="Object.assign(form, { email: '', phone: '', subject: '', body: '' })">
          Clear
        </button>
        <button class="btn-primary" :disabled="sending" @click="sendNotification">
          {{ sending ? "Sending…" : form.scheduled_at ? "Schedule" : "Send Now" }}
        </button>
      </div>
    </div>

    <!-- History tab -->
    <div v-if="activeTab === 'history'" class="card">
      <div v-if="loading" class="text-sm text-gray-400 py-8 text-center">Loading history…</div>
      <div v-else-if="!notifications.length" class="text-sm text-gray-400 py-12 text-center">
        <p class="text-4xl mb-3">📭</p>
        <p class="font-medium">No notifications sent yet.</p>
        <p class="mt-1">Use the Send tab to deliver your first notification.</p>
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
            </div>
            <p class="text-xs text-gray-500 mt-0.5 truncate">{{ n.body }}</p>
            <div class="flex items-center gap-3 mt-1 text-xs text-gray-400">
              <span>{{ n.notification_type }}</span>
              <span>·</span>
              <span>{{ n.channel }}</span>
              <span>·</span>
              <span>{{ formatDate(n.created_at) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
