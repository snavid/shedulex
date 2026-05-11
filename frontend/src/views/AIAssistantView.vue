<script setup>
import { ref } from "vue"
import { adjustmentApi } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const prompt = ref("")
const timetableId = ref("")
const loading = ref(false)
const messages = ref([])

const quickPrompts = [
  "Move Database class to Friday afternoon",
  "Find free slots for Lecturer A",
  "Resolve all semester two clashes",
  "Suggest best venue for 120 students",
]

async function sendPrompt() {
  if (!prompt.value || !timetableId.value) {
    toast.error("Provide timetable ID and prompt.")
    return
  }
  loading.value = true
  const userText = prompt.value
  messages.value.push({ role: "user", text: userText })
  prompt.value = ""
  try {
    const { data } = await adjustmentApi.chat({ prompt: userText, timetable_id: timetableId.value })
    messages.value.push({ role: "assistant", text: data.data.response })
  } catch (err) {
    const msg = err.response?.data?.message || "AI request failed."
    messages.value.push({ role: "assistant", text: msg })
    toast.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">AI Scheduling Assistant</h1>
      <p class="text-sm text-gray-500 mt-1">Use natural language to resolve timetable conflicts and suggest changes.</p>
    </div>

    <div class="card space-y-3">
      <label class="label">Timetable ID</label>
      <input v-model="timetableId" class="input" placeholder="Paste timetable UUID" />
      <div class="flex flex-wrap gap-2">
        <button
          v-for="q in quickPrompts"
          :key="q"
          class="btn-secondary text-xs"
          @click="prompt = q"
        >
          {{ q }}
        </button>
      </div>
      <label class="label">Prompt</label>
      <textarea v-model="prompt" rows="3" class="input" placeholder="Type your scheduling request..." />
      <button class="btn-primary" :disabled="loading" @click="sendPrompt">
        {{ loading ? "Processing..." : "Send to AI" }}
      </button>
    </div>

    <div class="card">
      <h2 class="font-semibold mb-3">Conversation</h2>
      <div v-if="!messages.length" class="text-sm text-gray-500">No messages yet.</div>
      <div v-else class="space-y-3">
        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          :class="[
            'p-3 rounded-lg text-sm whitespace-pre-wrap',
            msg.role === 'user' ? 'bg-blue-50 border border-blue-200' : 'bg-gray-50 border border-gray-200'
          ]"
        >
          <p class="font-semibold mb-1">{{ msg.role === "user" ? "You" : "Assistant" }}</p>
          <p>{{ msg.text }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
