<script setup>
import { onMounted, ref } from "vue"
import { calendarApi } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const events = ref([])
const form = ref({
  title: "",
  description: "",
  event_type: "event",
  start: "",
  end: "",
  location: "",
  all_day: false,
})

async function loadEvents() {
  loading.value = true
  try {
    const { data } = await calendarApi.events()
    events.value = data.data || []
  } finally {
    loading.value = false
  }
}

async function createEvent() {
  if (!form.value.title || !form.value.start) {
    toast.error("Title and start datetime are required.")
    return
  }
  await calendarApi.createEvent(form.value)
  toast.success("Event created.")
  form.value = { title: "", description: "", event_type: "event", start: "", end: "", location: "", all_day: false }
  await loadEvents()
}

async function removeEvent(id) {
  await calendarApi.deleteEvent(id)
  toast.success("Event deleted.")
  await loadEvents()
}

onMounted(loadEvents)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between gap-2">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Academic Calendar</h1>
        <p class="text-sm text-gray-500 mt-1">Events, deadlines, exams, and semester activities.</p>
      </div>
      <a :href="calendarApi.exportIcs()" target="_blank" class="btn-secondary">Export ICS</a>
    </div>

    <div class="card space-y-3">
      <h2 class="font-semibold">Create Event</h2>
      <div class="grid md:grid-cols-2 gap-3">
        <input v-model="form.title" class="input" placeholder="Event title" />
        <select v-model="form.event_type" class="input">
          <option value="event">Event</option>
          <option value="holiday">Holiday</option>
          <option value="exam">Exam</option>
          <option value="deadline">Deadline</option>
        </select>
        <input v-model="form.start" type="datetime-local" class="input" />
        <input v-model="form.end" type="datetime-local" class="input" />
        <input v-model="form.location" class="input" placeholder="Location" />
      </div>
      <textarea v-model="form.description" rows="3" class="input" placeholder="Description" />
      <label class="flex items-center gap-2 text-sm">
        <input v-model="form.all_day" type="checkbox" />
        All day event
      </label>
      <button class="btn-primary" @click="createEvent">Create</button>
    </div>

    <div class="card">
      <h2 class="font-semibold mb-3">Upcoming Events</h2>
      <div v-if="loading" class="text-sm text-gray-500">Loading...</div>
      <div v-else-if="!events.length" class="text-sm text-gray-500">No events found.</div>
      <div v-else class="space-y-2">
        <div v-for="e in events" :key="e.id" class="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
          <div>
            <p class="font-medium">{{ e.title }}</p>
            <p class="text-xs text-gray-500">{{ e.event_type }} | {{ e.start_datetime }} | {{ e.location || "No location" }}</p>
          </div>
          <button class="btn-danger" @click="removeEvent(e.id)">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>
