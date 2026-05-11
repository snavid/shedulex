<script setup>
import { onMounted, ref } from "vue"
import { notificationApi } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const notifications = ref([])
const form = ref({
  recipient_id: "",
  email: "",
  phone: "",
  channel: "email",
  subject: "",
  body: "",
  type: "general",
})

async function loadNotifications() {
  loading.value = true
  try {
    const { data } = await notificationApi.list()
    notifications.value = data.data || []
  } finally {
    loading.value = false
  }
}

async function sendNotification() {
  await notificationApi.send(form.value)
  toast.success("Notification sent.")
  form.value = { recipient_id: "", email: "", phone: "", channel: "email", subject: "", body: "", type: "general" }
  await loadNotifications()
}

onMounted(loadNotifications)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Notifications Center</h1>
      <p class="text-sm text-gray-500 mt-1">Send reminders and track delivery history.</p>
    </div>

    <div class="card space-y-3">
      <h2 class="font-semibold">Send Notification</h2>
      <div class="grid md:grid-cols-2 gap-3">
        <input v-model="form.recipient_id" class="input" placeholder="Recipient user ID (optional)" />
        <select v-model="form.channel" class="input">
          <option value="email">Email</option>
          <option value="sms">SMS</option>
          <option value="both">Both</option>
        </select>
        <input v-model="form.email" class="input" placeholder="Recipient email" />
        <input v-model="form.phone" class="input" placeholder="Recipient phone" />
        <input v-model="form.subject" class="input" placeholder="Subject" />
      </div>
      <textarea v-model="form.body" rows="4" class="input" placeholder="Message" />
      <button class="btn-primary" @click="sendNotification">Send</button>
    </div>

    <div class="card">
      <h2 class="font-semibold mb-3">Recent Notifications</h2>
      <div v-if="loading" class="text-sm text-gray-500">Loading...</div>
      <div v-else-if="!notifications.length" class="text-sm text-gray-500">No notifications found.</div>
      <div v-else class="space-y-2">
        <div v-for="n in notifications" :key="n.id" class="p-3 border border-gray-200 rounded-lg">
          <div class="flex items-center justify-between gap-2">
            <p class="font-medium">{{ n.subject || "(No subject)" }}</p>
            <span class="badge-info">{{ n.status }}</span>
          </div>
          <p class="text-xs text-gray-500 mt-1">{{ n.channel }} | {{ n.notification_type }} | {{ n.created_at }}</p>
          <p class="text-sm mt-2">{{ n.body }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
