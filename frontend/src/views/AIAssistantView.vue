<script setup>
import { onMounted, ref, watch } from "vue"
import { adjustmentApi, timetableApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"
import { useTimetableStore } from "@/stores/timetable"

const toast = useToast()
const timetableStore = useTimetableStore()

const prompt = ref("")
const timetableId = ref("")
const loading = ref(false)
const loadingTimetables = ref(false)
const loadingHistory = ref(false)
const messages = ref([])
const timetables = ref([])

const quickPrompts = [
  "Move Database class to Friday afternoon",
  "Find free slots for Lecturer A",
  "Resolve all semester two clashes",
  "Suggest best venue for 120 students",
]
const POLL_INTERVAL_MS = 2000
const MAX_POLL_ATTEMPTS = 120

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function adjustmentRowsToMessages(rows) {
  const chronological = [...(rows || [])].reverse()
  const out = []
  for (const r of chronological) {
    out.push({ role: "user", text: r.prompt })
    let text = r.response || ""
    if (r.status === "processing") text = "Processing…"
    else if (r.status === "failed" && !text) text = "Request failed."
    out.push({
      role: "assistant",
      text,
      tool_trace: r.tool_trace || [],
      status: r.status,
    })
  }
  return out
}

async function refreshConversationFromServer() {
  if (!timetableId.value) {
    messages.value = []
    return
  }
  loadingHistory.value = true
  try {
    const { data } = await adjustmentApi.history({ timetable_id: timetableId.value })
    messages.value = adjustmentRowsToMessages(data.data || [])
  } catch {
    toast.error("Failed to load chat history.")
  } finally {
    loadingHistory.value = false
  }
}

async function waitForRequestCompletion(requestId) {
  for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
    const { data } = await adjustmentApi.requestStatus(requestId)
    const req = data?.data
    if (!req) {
      throw new Error("Invalid AI status response.")
    }
    if (req.status === "completed") {
      return req.response || "AI request completed."
    }
    if (req.status === "failed") {
      throw new Error(req.response || "AI processing failed.")
    }
    await sleep(POLL_INTERVAL_MS)
  }
  throw new Error("AI request is taking longer than expected. Please check again shortly.")
}

watch(timetableId, () => {
  refreshConversationFromServer()
})

onMounted(async () => {
  loadingTimetables.value = true
  try {
    const { data } = await timetableApi.list()
    timetables.value = data.data || []
  } catch {
    toast.error("Failed to load timetables.")
  } finally {
    loadingTimetables.value = false
  }
})

async function sendPrompt() {
  if (!prompt.value || !timetableId.value) {
    toast.error("Select a timetable and provide a prompt.")
    return
  }
  loading.value = true
  const userText = prompt.value
  messages.value.push({ role: "user", text: userText })
  prompt.value = ""
  messages.value.push({ role: "assistant", text: "AI is processing your request…", tool_trace: [], status: "processing" })
  try {
    const { data } = await adjustmentApi.chat({ prompt: userText, timetable_id: timetableId.value })
    const requestId = data?.data?.request_id
    if (!requestId) {
      const responseText = data?.data?.response || data?.response || "AI request completed."
      messages.value[messages.value.length - 1].text = responseText
      messages.value[messages.value.length - 1].status = "completed"
      return
    }

    await waitForRequestCompletion(requestId)
    try {
      await timetableStore.fetchTimetable(timetableId.value)
    } catch {
      /* ignore refresh errors */
    }
    await refreshConversationFromServer()
  } catch (err) {
    const msg = getErrorMessage(err, "AI request failed.")
    const last = messages.value[messages.value.length - 1]
    if (last?.role === "assistant") last.text = msg
    else messages.value.push({ role: "assistant", text: msg })
    toast.error(msg)
    await refreshConversationFromServer()
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
      <label class="label">Timetable</label>
      <select v-model="timetableId" class="input" :disabled="loadingTimetables">
        <option value="">
          {{ loadingTimetables ? "Loading timetables..." : "Select timetable..." }}
        </option>
        <option v-for="tt in timetables" :key="tt.id" :value="tt.id">
          {{ tt.name }} - Semester {{ tt.semester }} - {{ tt.academic_year }}
        </option>
      </select>
      <p v-if="timetableId" class="text-xs">
        <RouterLink :to="`/timetable/${timetableId}`" class="text-blue-600 hover:underline font-medium">
          Open timetable (loads latest grid from server)
        </RouterLink>
      </p>
      <p v-if="loadingHistory" class="text-xs text-gray-500">Loading conversation history…</p>
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
      <div v-if="!messages.length" class="text-sm text-gray-500">No messages yet. Select a timetable to load history.</div>
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
          <details v-if="msg.role === 'assistant' && msg.tool_trace?.length" class="mt-2 text-xs">
            <summary class="cursor-pointer text-gray-600 font-medium">Tool trace</summary>
            <pre class="mt-1 p-2 bg-white border border-gray-200 rounded overflow-x-auto text-[11px]">{{ JSON.stringify(msg.tool_trace, null, 2) }}</pre>
          </details>
        </div>
      </div>
    </div>
  </div>
</template>
