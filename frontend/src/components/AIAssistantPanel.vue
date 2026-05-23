<script setup>
import { ref, nextTick, onUnmounted, defineExpose } from "vue"
import { adjustmentApi } from "@/api/client"

const props = defineProps({
  timetableId:   { type: String, required: true },
  timetableName: { type: String, default: "Timetable" },
  conflictCount: { type: Number, default: 0 },
})

const emit = defineEmits(["refresh"])

const isOpen      = ref(false)
const showHistory = ref(false)
const input       = ref("")
const sending     = ref(false)
const messages    = ref([])
const history     = ref([])
const historyLoading = ref(false)
const chatContainer  = ref(null)
const pollingTimer   = ref(null)
const expandedTraces = ref(new Set())

const QUICK_ACTIONS = [
  { icon: "⚠️", label: "Find conflicts",     prompt: "Detect all scheduling conflicts in this timetable and explain each one clearly." },
  { icon: "🔧", label: "Auto-fix conflicts", prompt: "Find all lecturer and room conflicts in this timetable and automatically move sessions to resolve them." },
  { icon: "⚖️", label: "Lecturer load",      prompt: "Analyse each lecturer's weekly workload. Flag anyone over their limit and suggest how to rebalance." },
  { icon: "🏛️", label: "Room usage",         prompt: "Show which rooms are over- or under-used and suggest rebalancing moves." },
  { icon: "🕐", label: "Find free slots",    prompt: "List all time slots that have no sessions scheduled across the whole timetable." },
  { icon: "✨", label: "Suggest swaps",      prompt: "Look for any two sessions that would benefit from swapping their time slots, then perform the best swap." },
]

function open() {
  isOpen.value = true
  if (!messages.value.length) pushWelcome()
  nextTick(scrollBottom)
}
function close() {
  isOpen.value = false
  showHistory.value = false
}

function pushWelcome() {
  messages.value.push({
    role: "assistant",
    content: `Hi! I'm **Sora** ✦, your AI timetabling assistant.\n\nI can **detect conflicts**, **move sessions**, **swap entries**, **find free rooms**, and much more.\n\nType a request below or tap a quick action to get started.`,
    toolTrace: [],
    ts: new Date(),
  })
}

async function send(promptOverride) {
  const text = (promptOverride || input.value).trim()
  if (!text || sending.value) return
  input.value = ""

  messages.value.push({ role: "user", content: text, ts: new Date() })

  const thinkingIdx = messages.value.length
  messages.value.push({ role: "assistant", content: null, toolTrace: [], ts: new Date(), _thinking: true })

  sending.value = true
  await nextTick()
  scrollBottom()

  try {
    const { data } = await adjustmentApi.chat({ prompt: text, timetable_id: props.timetableId })
    pollUntilDone(data.data.request_id, thinkingIdx)
  } catch (e) {
    patch(thinkingIdx, { content: "Connection to AI service failed. Please check that the adjustment engine is running.", _thinking: false, _error: true, toolTrace: [] })
    sending.value = false
  }
}

function pollUntilDone(requestId, idx, attempts = 0) {
  pollingTimer.value = setTimeout(async () => {
    try {
      const { data } = await adjustmentApi.requestStatus(requestId)
      const req = data.data
      if (req.status === "completed") {
        patch(idx, { content: req.response, toolTrace: req.tool_trace || [], _thinking: false })
        sending.value = false
        emit("refresh")
        loadHistory()
      } else if (req.status === "failed") {
        patch(idx, { content: req.response || "AI processing failed.", _thinking: false, _error: true, toolTrace: [] })
        sending.value = false
      } else if (attempts < 120) {
        pollUntilDone(requestId, idx, attempts + 1)
      } else {
        patch(idx, { content: "Request is still processing in the background. Refresh the page to see any changes.", _thinking: false, toolTrace: [] })
        sending.value = false
      }
    } catch {
      sending.value = false
    }
  }, 1500)
}

function patch(idx, fields) {
  if (messages.value[idx]) {
    messages.value[idx] = { ...messages.value[idx], ...fields }
    nextTick(scrollBottom)
  }
}

function scrollBottom() {
  if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const { data } = await adjustmentApi.history({ timetable_id: props.timetableId })
    history.value = data.data || []
  } finally {
    historyLoading.value = false
  }
}

function replayHistory(item) {
  showHistory.value = false
  messages.value.push(
    { role: "user",      content: item.prompt,   ts: new Date(item.created_at) },
    { role: "assistant", content: item.response,  toolTrace: item.tool_trace || [], ts: new Date(item.completed_at || item.created_at) },
  )
  nextTick(scrollBottom)
}

function toggleTrace(msgIdx) {
  if (expandedTraces.value.has(msgIdx)) expandedTraces.value.delete(msgIdx)
  else expandedTraces.value.add(msgIdx)
}

function onKeydown(e) {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send() }
}

const TOOL_META = {
  get_timetable_entries:    { icon: "📋", label: "Fetched timetable entries" },
  detect_timetable_conflicts:{ icon: "⚠️", label: "Scanned for conflicts" },
  get_available_rooms:      { icon: "🏛️", label: "Searched available rooms" },
  get_lecturer_free_slots:  { icon: "👤", label: "Checked lecturer availability" },
  swap_timetable_entries:   { icon: "🔄", label: "Swapped sessions" },
  move_timetable_entry:     { icon: "✈️", label: "Moved session" },
  suggest_best_venue:       { icon: "✨", label: "Suggested best venue" },
}

function toolMeta(name) {
  return TOOL_META[name] || { icon: "🔧", label: name }
}

function toolSuccess(output) {
  const o = (output || "").toString()
  if (o.startsWith("Swap successful:") || o.startsWith("Move successful:")) return "success"
  if (o.toLowerCase().includes("error") || o.toLowerCase().includes("failed")) return "error"
  return "info"
}

function renderMd(text) {
  if (!text) return ""
  return text
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/`([^`]+)`/g, '<code class="bg-gray-100 text-gray-800 text-xs font-mono px-1 py-0.5 rounded">$1</code>')
    .replace(/\n/g, "<br>")
}

function fmtTime(d) {
  if (!d) return ""
  return new Date(d).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

onUnmounted(() => { if (pollingTimer.value) clearTimeout(pollingTimer.value) })
defineExpose({ open, close })
</script>

<template>
  <!-- Backdrop -->
  <Transition name="backdrop">
    <div v-if="isOpen" class="fixed inset-0 z-40 bg-black/30 backdrop-blur-[2px]" @click="close" />
  </Transition>

  <!-- Panel -->
  <Transition name="panel-slide">
    <div v-if="isOpen"
      class="fixed right-0 top-0 bottom-0 z-50 w-full sm:w-[460px] flex flex-col bg-white shadow-2xl shadow-black/20"
    >
      <!-- Header -->
      <div class="bg-gradient-to-r from-violet-600 via-purple-600 to-indigo-600 p-4 flex-shrink-0">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-xl bg-white/20 flex items-center justify-center text-lg flex-shrink-0">✦</div>
            <div>
              <h2 class="text-white font-bold text-sm leading-none">Sora AI Assistant</h2>
              <p class="text-white/70 text-xs mt-0.5 truncate max-w-[200px]">{{ timetableName }}</p>
            </div>
          </div>
          <div class="flex items-center gap-1.5">
            <span v-if="conflictCount > 0"
              class="bg-red-500 text-white text-xs font-bold px-2 py-0.5 rounded-full animate-pulse">
              ⚠ {{ conflictCount }}
            </span>
            <button
              @click="showHistory = !showHistory"
              :class="['w-8 h-8 rounded-lg flex items-center justify-center text-white/80 hover:text-white transition-colors text-sm',
                showHistory ? 'bg-white/20' : 'hover:bg-white/10']"
              title="Conversation history"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </button>
            <button @click="close" class="w-8 h-8 rounded-lg hover:bg-white/10 flex items-center justify-center text-white/80 hover:text-white text-xl leading-none">×</button>
          </div>
        </div>

        <!-- Status bar -->
        <div class="mt-3 flex items-center gap-2">
          <div v-if="sending" class="flex items-center gap-1.5 text-white/80 text-xs">
            <span class="flex gap-0.5">
              <span class="w-1.5 h-1.5 bg-white/60 rounded-full animate-bounce" style="animation-delay:0ms"/>
              <span class="w-1.5 h-1.5 bg-white/60 rounded-full animate-bounce" style="animation-delay:150ms"/>
              <span class="w-1.5 h-1.5 bg-white/60 rounded-full animate-bounce" style="animation-delay:300ms"/>
            </span>
            Thinking…
          </div>
          <div v-else class="text-white/60 text-xs flex items-center gap-1">
            <span class="w-1.5 h-1.5 bg-green-400 rounded-full"></span>
            Ready
          </div>
        </div>
      </div>

      <!-- History Sidebar -->
      <Transition name="fade">
        <div v-if="showHistory" class="flex-shrink-0 border-b border-gray-200 bg-gray-50 max-h-56 overflow-y-auto">
          <div class="p-3 flex items-center justify-between sticky top-0 bg-gray-50 border-b border-gray-100 z-10">
            <p class="text-xs font-semibold text-gray-600 uppercase tracking-wide">Past Conversations</p>
            <button @click="showHistory = false" class="text-gray-400 hover:text-gray-600 text-xs">Close</button>
          </div>
          <div v-if="historyLoading" class="p-4 text-xs text-gray-400 text-center">Loading…</div>
          <div v-else-if="!history.length" class="p-4 text-xs text-gray-400 text-center">No history yet.</div>
          <div v-else class="divide-y divide-gray-100">
            <button
              v-for="item in history"
              :key="item.id"
              @click="replayHistory(item)"
              class="w-full text-left px-3 py-2.5 hover:bg-white transition-colors"
            >
              <p class="text-xs font-medium text-gray-800 truncate">{{ item.prompt }}</p>
              <p class="text-[10px] text-gray-400 mt-0.5">
                {{ item.status === "completed" ? "✓" : item.status === "failed" ? "✗" : "…" }}
                {{ fmtTime(item.created_at) }}
              </p>
            </button>
          </div>
        </div>
      </Transition>

      <!-- Messages -->
      <div ref="chatContainer" class="flex-1 overflow-y-auto p-4 space-y-4 scroll-smooth">

        <div
          v-for="(msg, i) in messages"
          :key="i"
          :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'"
        >
          <!-- AI message -->
          <div v-if="msg.role === 'assistant'" class="flex gap-2.5 max-w-[92%]">
            <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white text-xs flex-shrink-0 mt-0.5">✦</div>
            <div class="flex-1 min-w-0">
              <!-- Thinking state -->
              <div v-if="msg._thinking" class="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
                <div class="flex items-center gap-2 text-gray-500 text-sm">
                  <svg class="w-4 h-4 animate-spin text-violet-500" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                  </svg>
                  <span class="text-sm text-gray-600">Analysing timetable…</span>
                </div>
              </div>

              <!-- Normal AI response -->
              <div v-else
                :class="['bg-white border rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm',
                  msg._error ? 'border-red-200 bg-red-50' : 'border-gray-200']"
              >
                <p class="text-sm text-gray-800 leading-relaxed" v-html="renderMd(msg.content)"></p>
              </div>

              <!-- Tool trace accordion -->
              <div v-if="msg.toolTrace?.length" class="mt-1.5">
                <button
                  @click="toggleTrace(i)"
                  class="flex items-center gap-1 text-[11px] text-gray-400 hover:text-violet-600 transition-colors"
                >
                  <svg class="w-3 h-3 transition-transform" :class="expandedTraces.has(i) ? 'rotate-90' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
                  </svg>
                  {{ msg.toolTrace.length }} tool call{{ msg.toolTrace.length > 1 ? "s" : "" }}
                </button>

                <div v-if="expandedTraces.has(i)" class="mt-1.5 space-y-1.5">
                  <div
                    v-for="(t, ti) in msg.toolTrace"
                    :key="ti"
                    :class="['rounded-xl px-3 py-2 text-xs border',
                      toolSuccess(t.output) === 'success' ? 'bg-green-50 border-green-200' :
                      toolSuccess(t.output) === 'error'   ? 'bg-red-50 border-red-200' :
                                                             'bg-gray-50 border-gray-200']"
                  >
                    <div class="flex items-center gap-1.5 font-medium text-gray-700 mb-1">
                      <span>{{ toolMeta(t.tool).icon }}</span>
                      <span>{{ toolMeta(t.tool).label }}</span>
                      <span class="text-gray-400 font-normal">({{ t.tool }})</span>
                    </div>
                    <p class="text-gray-500 font-mono text-[10px] whitespace-pre-wrap line-clamp-4">{{ t.output }}</p>
                  </div>
                </div>
              </div>

              <p class="text-[10px] text-gray-300 mt-1 ml-1">{{ fmtTime(msg.ts) }}</p>
            </div>
          </div>

          <!-- User message -->
          <div v-else class="max-w-[80%]">
            <div class="bg-gradient-to-br from-violet-600 to-indigo-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 shadow-sm">
              <p class="text-sm leading-relaxed">{{ msg.content }}</p>
            </div>
            <p class="text-[10px] text-gray-300 mt-1 text-right mr-1">{{ fmtTime(msg.ts) }}</p>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="flex-shrink-0 border-t border-gray-100 px-4 pt-3 pb-2">
        <p class="text-[10px] text-gray-400 uppercase tracking-wide font-semibold mb-2">Quick actions</p>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="qa in QUICK_ACTIONS"
            :key="qa.label"
            @click="send(qa.prompt)"
            :disabled="sending"
            :class="[
              'flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-full border transition-all',
              qa.label === 'Auto-fix conflicts' && conflictCount > 0
                ? 'bg-red-50 border-red-300 text-red-700 hover:bg-red-100'
                : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-violet-50 hover:border-violet-300 hover:text-violet-700',
              sending ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
            ]"
          >
            <span>{{ qa.icon }}</span>
            {{ qa.label }}
          </button>
        </div>
      </div>

      <!-- Input -->
      <div class="flex-shrink-0 border-t border-gray-100 p-4 bg-gray-50">
        <div class="flex gap-2 items-end">
          <div class="flex-1">
            <textarea
              v-model="input"
              @keydown="onKeydown"
              :disabled="sending"
              rows="2"
              placeholder="Ask me anything about this timetable… (Enter to send, Shift+Enter for new line)"
              class="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-violet-400 focus:border-transparent bg-white placeholder-gray-400 disabled:opacity-50 transition-shadow"
            />
          </div>
          <button
            @click="send()"
            :disabled="sending || !input.trim()"
            class="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 text-white flex items-center justify-center flex-shrink-0 disabled:opacity-40 transition-opacity hover:opacity-90 shadow-md"
          >
            <svg v-if="!sending" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
            </svg>
            <svg v-else class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
            </svg>
          </button>
        </div>
        <p class="text-[10px] text-gray-400 mt-1.5 text-center">Powered by GPT-4o · Changes are applied live to your timetable</p>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.panel-slide-enter-active, .panel-slide-leave-active {
  transition: transform 0.28s cubic-bezier(0.4, 0, 0.2, 1);
}
.panel-slide-enter-from, .panel-slide-leave-to {
  transform: translateX(100%);
}

.backdrop-enter-active, .backdrop-leave-active { transition: opacity 0.25s ease; }
.backdrop-enter-from, .backdrop-leave-to         { opacity: 0; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease, transform 0.2s ease; }
.fade-enter-from, .fade-leave-to       { opacity: 0; transform: translateY(-4px); }
</style>
