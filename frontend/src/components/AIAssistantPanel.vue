<script setup>
import { ref, computed, nextTick, onUnmounted } from "vue"
import { adjustmentApi, API_BASE } from "@/api/client"

const props = defineProps({
  timetableId:   { type: String, required: true },
  timetableName: { type: String, default: "Timetable" },
  conflictCount: { type: Number, default: 0 },
})

const emit = defineEmits(["refresh"])

// ── Panel ──────────────────────────────────────────────────────────────────────
const isOpen   = ref(false)
const input    = ref("")

// ── Session ────────────────────────────────────────────────────────────────────
const SESSION_FULL = 80
const session       = ref(null)
const sessionLoading = ref(false)

// ── Messages ───────────────────────────────────────────────────────────────────
const messages      = ref([])
const chatContainer = ref(null)

// ── Live streaming ─────────────────────────────────────────────────────────────
const isProcessing = ref(false)
const thinkingText = ref("")
const liveSteps    = ref([])   // { id, tool, icon, label, status: loading|success|error, output }
const sseReader    = ref(null)

// ── Human-in-the-loop ─────────────────────────────────────────────────────────
const interruptQ   = ref("")
const interruptAns = ref("")
const responding   = ref(false)

// ── Sessions history panel ─────────────────────────────────────────────────────
const showSessions    = ref(false)
const sessionsList    = ref([])
const sessionsLoading = ref(false)

// ── Tool trace expansion ───────────────────────────────────────────────────────
const expandedTraces = ref(new Set())

// ── Computed ───────────────────────────────────────────────────────────────────
const sessionFull = computed(() =>
  session.value?.is_full === true || (session.value?.total_messages ?? 0) >= SESSION_FULL
)

const canSend = computed(() => !isProcessing.value && !interruptQ.value && !sessionFull.value)

const QUICK_ACTIONS = [
  { icon: "⚠️", label: "Find conflicts",     prompt: "Detect all scheduling conflicts in this timetable and explain each one clearly." },
  { icon: "🔧", label: "Auto-fix conflicts", prompt: "Find all lecturer and room conflicts in this timetable and automatically move sessions to resolve them." },
  { icon: "⚖️", label: "Lecturer load",      prompt: "Analyse each lecturer's weekly workload. Flag anyone over their limit and suggest how to rebalance." },
  { icon: "🏛️", label: "Room usage",         prompt: "Show which rooms are over- or under-used and suggest rebalancing moves." },
  { icon: "🕐", label: "Find free slots",    prompt: "List all time slots that have no sessions scheduled across the whole timetable." },
  { icon: "✨", label: "Suggest swaps",      prompt: "Look for any two sessions that would benefit from swapping their time slots, then perform the best swap." },
]

// ── Open / close ───────────────────────────────────────────────────────────────
async function open() {
  isOpen.value = true
  if (!session.value) {
    await initSession()
  } else if (session.value.status === "processing") {
    beginProcessing("Working on your request…")
    connectSSE(session.value.id)
  }
  nextTick(scrollBottom)
}

function close() {
  isOpen.value = false
  showSessions.value = false
  disconnectSSE()
}

// ── Session lifecycle ──────────────────────────────────────────────────────────
async function initSession() {
  sessionLoading.value = true
  try {
    const { data } = await adjustmentApi.createSession({ timetable_id: props.timetableId })
    session.value = data.data
    hydrateMessages(session.value)
    if (session.value.status === "processing") {
      beginProcessing("Working on your request…")
      connectSSE(session.value.id)
    }
  } catch (e) {
    console.error("Session init failed:", e)
    pushWelcome()
  } finally {
    sessionLoading.value = false
  }
}

function hydrateMessages(s) {
  messages.value       = []
  expandedTraces.value = new Set()
  interruptQ.value     = ""
  const raw = s.messages || []
  if (!raw.length) {
    pushWelcome()
  } else {
    for (const m of raw) {
      messages.value.push({
        role:       m.role,
        content:    m.content,
        toolTrace:  m.tool_trace || [],
        ts:         m.ts ? new Date(m.ts) : new Date(),
        isDecision: !!m.content?.startsWith("[Decision]"),
      })
    }
  }
  if (s.status === "waiting_for_input" && s.interrupt_data?.question) {
    interruptQ.value = s.interrupt_data.question
    messages.value.push({ role: "interrupt", question: s.interrupt_data.question, ts: new Date() })
  }
}

async function newChat() {
  if (isProcessing.value && session.value) {
    try { await adjustmentApi.cancelSession(session.value.id) } catch {}
    disconnectSSE()
    endProcessing()
  } else {
    disconnectSSE()
  }
  if (session.value) {
    try { await adjustmentApi.archiveSession(session.value.id) } catch {}
  }
  session.value      = null
  messages.value     = []
  liveSteps.value    = []
  thinkingText.value = ""
  interruptQ.value   = ""
  isProcessing.value = false
  await initSession()
}

function pushWelcome() {
  messages.value.push({
    role:      "assistant",
    content:   "Hi! I'm **Sora** ✦, your AI timetabling assistant.\n\nI can **detect conflicts**, **move sessions**, **swap entries**, **find free rooms**, and much more.\n\nType a request below or tap a quick action to get started.",
    toolTrace: [],
    ts:        new Date(),
  })
}

// ── Send message ───────────────────────────────────────────────────────────────
async function send(promptOverride) {
  const text = (promptOverride || input.value).trim()
  if (!text || !canSend.value) return
  if (!session.value) { await initSession(); if (!session.value) return }
  input.value = ""

  messages.value.push({ role: "user", content: text, ts: new Date() })
  beginProcessing("Analysing your request…")
  await nextTick()
  scrollBottom()

  try {
    await adjustmentApi.sessionChat(session.value.id, { prompt: text })
    connectSSE(session.value.id)
  } catch {
    endProcessing()
    pushError("Failed to reach the AI service. Check that the adjustment engine is running.")
  }
}

// ── Interrupt respond ──────────────────────────────────────────────────────────
async function respond(answer) {
  const ans = (answer || interruptAns.value).trim()
  if (!ans || responding.value) return
  responding.value   = true
  interruptQ.value   = ""
  interruptAns.value = ""

  messages.value.push({ role: "user", content: ans, ts: new Date(), isDecision: true })
  beginProcessing("Continuing with your decision…")
  await nextTick()
  scrollBottom()

  try {
    await adjustmentApi.sessionRespond(session.value.id, { answer: ans })
    connectSSE(session.value.id)
  } catch {
    endProcessing()
    pushError("Failed to resume. Please try again.")
  } finally {
    responding.value = false
  }
}

// ── Processing helpers ─────────────────────────────────────────────────────────
function beginProcessing(text = "Thinking…") {
  isProcessing.value = true
  thinkingText.value = text
  liveSteps.value    = []
}

function endProcessing() {
  isProcessing.value = false
  thinkingText.value = ""
  liveSteps.value    = []
}

async function stopProcessing() {
  if (!isProcessing.value || !session.value) return
  try { await adjustmentApi.cancelSession(session.value.id) } catch {}
  disconnectSSE()
  endProcessing()
  messages.value.push({
    role:      "assistant",
    content:   "Stopped. You can send a new request.",
    toolTrace: [],
    ts:        new Date(),
  })
  nextTick(scrollBottom)
}

function pushError(msg) {
  messages.value.push({ role: "assistant", content: msg, _error: true, toolTrace: [], ts: new Date() })
  nextTick(scrollBottom)
}

// ── SSE ────────────────────────────────────────────────────────────────────────
function connectSSE(sessionId) {
  disconnectSSE()
  const token = localStorage.getItem("access_token")
  fetch(`${API_BASE}/adjustments/sessions/${sessionId}/stream`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then(res => {
    if (!res.ok) throw new Error(`SSE ${res.status}`)
    const reader = res.body.getReader()
    sseReader.value = reader
    drainSSE(reader)
  }).catch(err => {
    console.error("SSE connect failed:", err)
    endProcessing()
  })
}

function disconnectSSE() {
  if (sseReader.value) {
    try { sseReader.value.cancel() } catch {}
    sseReader.value = null
  }
}

async function drainSSE(reader) {
  const dec = new TextDecoder()
  let buf = ""
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += dec.decode(value, { stream: true })
      const lines = buf.split("\n")
      buf = lines.pop() ?? ""
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const raw = line.slice(6).trim()
          if (raw) { try { handleSSE(JSON.parse(raw)) } catch {} }
        }
      }
    }
  } catch (e) {
    if (e?.name !== "AbortError") console.warn("SSE ended:", e)
  }
}

function handleSSE(ev) {
  switch (ev.type) {

    case "thinking":
      thinkingText.value = ev.content || "Thinking…"
      nextTick(scrollBottom)
      break

    case "tool_start": {
      const m = toolMeta(ev.tool)
      liveSteps.value = [...liveSteps.value, {
        id: Date.now() + Math.random(),
        tool: ev.tool, icon: m.icon, label: m.label,
        status: "loading", input: ev.input || "",
      }]
      nextTick(scrollBottom)
      break
    }

    case "tool_end": {
      const steps  = [...liveSteps.value]
      const ri     = steps.map((s, i) => [s, i]).reverse().find(([s]) => s.tool === ev.tool && s.status === "loading")
      if (ri) {
        steps[ri[1]] = { ...steps[ri[1]], status: ev.success ? "success" : "error", output: ev.output || "" }
        liveSteps.value = steps
      }
      nextTick(scrollBottom)
      break
    }

    case "interrupt":
      endProcessing()
      interruptQ.value = ev.question || ""
      messages.value = [...messages.value, { role: "interrupt", question: ev.question, ts: new Date() }]
      refreshSession()
      nextTick(scrollBottom)
      break

    case "done":
      endProcessing()
      messages.value = [...messages.value, {
        role:      "assistant",
        content:   ev.response || "",
        toolTrace: ev.tool_trace || [],
        ts:        new Date(),
      }]
      emit("refresh")
      refreshSession()
      nextTick(scrollBottom)
      break

    case "cancelled":
      endProcessing()
      messages.value = [...messages.value, {
        role:      "assistant",
        content:   ev.message || "Stopped. You can send a new request.",
        toolTrace: [],
        ts:        new Date(),
      }]
      refreshSession()
      nextTick(scrollBottom)
      break

    case "error":
      endProcessing()
      pushError(`Error: ${ev.message || "Unknown error."}`)
      break

    default:
      break
  }
}

// ── Session list ───────────────────────────────────────────────────────────────
async function refreshSession() {
  if (!session.value) return
  try {
    const { data } = await adjustmentApi.getSession(session.value.id)
    session.value = data.data
  } catch {}
}

async function openSessions() {
  showSessions.value = !showSessions.value
  if (showSessions.value) {
    sessionsLoading.value = true
    try {
      const { data } = await adjustmentApi.listSessions({ timetable_id: props.timetableId })
      sessionsList.value = data.data || []
    } finally {
      sessionsLoading.value = false
    }
  }
}

function switchSession(s) {
  if (session.value?.id === s.id) { showSessions.value = false; return }
  disconnectSSE()
  endProcessing()
  interruptQ.value = ""
  session.value = s
  hydrateMessages(s)
  showSessions.value = false
  nextTick(scrollBottom)
}

// ── Interrupt option parsing ───────────────────────────────────────────────────
function parseOptions(q) {
  const opts = []
  for (const line of (q || "").split("\n")) {
    const m = line.match(/^(?:[Oo]ption\s+)?([A-D])[\.\):\s]\s*(.+)/)
    if (m && m[2].trim().length > 3) opts.push({ key: m[1], text: m[2].trim() })
  }
  return opts
}

// ── Utilities ──────────────────────────────────────────────────────────────────
function scrollBottom() {
  if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
}

function toggleTrace(idx) {
  const s = new Set(expandedTraces.value)
  s.has(idx) ? s.delete(idx) : s.add(idx)
  expandedTraces.value = s
}

function onKeydown(e) {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send() }
}

const TOOL_META = {
  get_timetable_entries:      { icon: "📋", label: "Fetched timetable entries" },
  detect_timetable_conflicts: { icon: "⚠️", label: "Scanned for conflicts" },
  get_available_rooms:        { icon: "🏛️", label: "Searched available rooms" },
  get_lecturer_free_slots:    { icon: "👤", label: "Checked lecturer availability" },
  swap_timetable_entries:     { icon: "🔄", label: "Swapped sessions" },
  move_timetable_entry:       { icon: "✈️", label: "Moved session" },
  suggest_best_venue:         { icon: "✨", label: "Suggested best venue" },
  ask_user:                   { icon: "💬", label: "Requesting your decision" },
}

function toolMeta(name) {
  return TOOL_META[name] || { icon: "🔧", label: name }
}

function traceStatusClass(output) {
  const o = (output || "").toString()
  if (o.startsWith("Swap successful:") || o.startsWith("Move successful:")) return "success"
  if (o.toLowerCase().includes("failed:") || o.toLowerCase().includes("error")) return "error"
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

function fmtTime(d)  { return d ? new Date(d).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "" }
function fmtDate(d)  {
  if (!d) return ""
  const dt = new Date(d)
  return dt.toLocaleDateString([], { month: "short", day: "numeric" }) + " " + dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

onUnmounted(disconnectSSE)
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
      class="fixed right-0 top-0 bottom-0 z-50 w-full sm:w-[480px] flex flex-col bg-white shadow-2xl shadow-black/20"
    >
      <!-- ── Header ── -->
      <div class="bg-gradient-to-r from-violet-600 via-purple-600 to-indigo-600 px-4 pt-4 pb-3 flex-shrink-0">
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-3 min-w-0">
            <div class="w-9 h-9 rounded-xl bg-white/20 flex items-center justify-center text-lg flex-shrink-0">✦</div>
            <div class="min-w-0">
              <h2 class="text-white font-bold text-sm leading-none">Sora AI Assistant</h2>
              <p class="text-white/70 text-xs mt-0.5 truncate">{{ timetableName }}</p>
            </div>
          </div>
          <div class="flex items-center gap-1 flex-shrink-0">
            <span v-if="conflictCount > 0"
              class="bg-red-500 text-white text-xs font-bold px-2 py-0.5 rounded-full animate-pulse mr-1">
              ⚠ {{ conflictCount }}
            </span>
            <!-- Sessions history button -->
            <button @click="openSessions"
              :class="['w-8 h-8 rounded-lg flex items-center justify-center text-white/80 hover:text-white transition-colors',
                showSessions ? 'bg-white/20' : 'hover:bg-white/10']"
              title="Past sessions"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </button>
            <button @click="close"
              class="w-8 h-8 rounded-lg hover:bg-white/10 flex items-center justify-center text-white/70 hover:text-white text-xl leading-none">
              ×
            </button>
          </div>
        </div>

        <!-- Status / session bar -->
        <div class="mt-2.5 flex items-center justify-between">
          <div v-if="isProcessing" class="flex items-center gap-2 text-white/80 text-xs">
            <span class="flex items-center gap-0.5">
              <span class="w-1.5 h-1.5 bg-white/70 rounded-full animate-bounce" style="animation-delay:0ms"/>
              <span class="w-1.5 h-1.5 bg-white/70 rounded-full animate-bounce" style="animation-delay:120ms"/>
              <span class="w-1.5 h-1.5 bg-white/70 rounded-full animate-bounce" style="animation-delay:240ms"/>
            </span>
            <span class="italic">{{ thinkingText }}</span>
            <button
              @click="stopProcessing"
              class="ml-1 flex items-center gap-1 bg-white/15 hover:bg-red-500/80 text-white text-[10px] font-bold px-2 py-0.5 rounded-md transition-colors"
              title="Stop Sora"
            >
              ■ Stop
            </button>
          </div>
          <div v-else-if="interruptQ" class="flex items-center gap-1.5 text-amber-200 text-xs font-medium">
            <span class="text-amber-300">💬</span>
            Waiting for your decision
          </div>
          <div v-else class="flex items-center gap-1.5 text-white/60 text-xs">
            <span class="w-1.5 h-1.5 bg-green-400 rounded-full"></span>
            Ready
            <span v-if="session" class="text-white/40">· {{ session.total_messages || 0 }} messages</span>
            <span v-if="session?.compressed_summary" class="ml-1 bg-white/10 text-white/60 text-[10px] px-1.5 py-0.5 rounded-full">
              memory compressed
            </span>
          </div>

          <!-- New chat -->
          <button v-if="sessionFull" @click="newChat"
            class="flex items-center gap-1 bg-white/15 hover:bg-white/25 text-white text-xs font-semibold px-2.5 py-1 rounded-lg transition-colors"
          >
            <span>+</span> New chat
          </button>
          <button v-else-if="session && !isProcessing" @click="newChat"
            class="text-white/40 hover:text-white/70 text-[10px] transition-colors px-1"
          >
            new chat
          </button>
        </div>
      </div>

      <!-- ── Sessions list panel ── -->
      <Transition name="fade">
        <div v-if="showSessions" class="flex-shrink-0 border-b border-gray-200 bg-gray-50 max-h-52 overflow-y-auto">
          <div class="flex items-center justify-between px-3 py-2 sticky top-0 bg-gray-50 border-b border-gray-100 z-10">
            <p class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Past Sessions</p>
            <button @click="showSessions = false" class="text-gray-400 hover:text-gray-600 text-xs">Done</button>
          </div>
          <div v-if="sessionsLoading" class="p-4 text-xs text-gray-400 text-center">Loading…</div>
          <div v-else-if="!sessionsList.length" class="p-4 text-xs text-gray-400 text-center">No past sessions yet.</div>
          <div v-else class="divide-y divide-gray-100">
            <button
              v-for="s in sessionsList" :key="s.id"
              @click="switchSession(s)"
              :class="['w-full text-left px-3 py-2.5 hover:bg-white transition-colors flex items-start gap-2',
                s.id === session?.id ? 'bg-violet-50' : '']"
            >
              <div class="flex-1 min-w-0">
                <p class="text-xs font-medium text-gray-800 truncate">
                  {{ (s.messages?.[0]?.content || "Empty session").slice(0, 60) }}
                </p>
                <p class="text-[10px] text-gray-400 mt-0.5">
                  {{ fmtDate(s.last_activity) }} · {{ s.total_messages }} msgs
                </p>
              </div>
              <span :class="['text-[10px] px-1.5 py-0.5 rounded-full flex-shrink-0 mt-0.5',
                s.status === 'waiting_for_input' ? 'bg-amber-100 text-amber-700' :
                s.status === 'archived' ? 'bg-gray-100 text-gray-500' :
                s.id === session?.id ? 'bg-violet-100 text-violet-700' : 'bg-green-50 text-green-700']">
                {{ s.id === session?.id ? "current" : s.status === "waiting_for_input" ? "paused" : s.status }}
              </span>
            </button>
          </div>
        </div>
      </Transition>

      <!-- ── Messages ── -->
      <div ref="chatContainer" class="flex-1 overflow-y-auto p-4 space-y-4 scroll-smooth bg-gray-50/30">

        <!-- Loading spinner when creating session -->
        <div v-if="sessionLoading" class="flex justify-center items-center py-8">
          <svg class="w-6 h-6 animate-spin text-violet-400" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
          </svg>
        </div>

        <template v-else>
          <div v-for="(msg, i) in messages" :key="i"
            :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'"
          >

            <!-- ── User message ── -->
            <div v-if="msg.role === 'user'" class="max-w-[80%]">
              <div :class="[
                'rounded-2xl rounded-tr-sm px-4 py-2.5 shadow-sm',
                msg.isDecision
                  ? 'bg-amber-50 border border-amber-200'
                  : 'bg-gradient-to-br from-violet-600 to-indigo-600 text-white'
              ]">
                <span v-if="msg.isDecision"
                  class="inline-flex items-center gap-1 text-[10px] font-bold text-amber-600 bg-amber-100 px-1.5 py-0.5 rounded-full mb-1.5 mr-1">
                  💬 Decision
                </span>
                <p :class="['text-sm leading-relaxed', msg.isDecision ? 'text-gray-800' : '']">
                  {{ msg.isDecision ? msg.content.replace(/^\[Decision\]\s*/, "") : msg.content }}
                </p>
              </div>
              <p class="text-[10px] text-gray-300 mt-1 text-right mr-1">{{ fmtTime(msg.ts) }}</p>
            </div>

            <!-- ── AI message ── -->
            <div v-else-if="msg.role === 'assistant'" class="flex gap-2.5 max-w-[92%]">
              <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white text-xs flex-shrink-0 mt-0.5">✦</div>
              <div class="flex-1 min-w-0">
                <div :class="['bg-white border rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm',
                  msg._error ? 'border-red-200 bg-red-50' : 'border-gray-200']">
                  <p class="text-sm text-gray-800 leading-relaxed" v-html="renderMd(msg.content)"></p>
                </div>

                <!-- Tool trace accordion -->
                <div v-if="msg.toolTrace?.length" class="mt-1.5">
                  <button @click="toggleTrace(i)"
                    class="flex items-center gap-1 text-[11px] text-gray-400 hover:text-violet-600 transition-colors">
                    <svg class="w-3 h-3 transition-transform" :class="expandedTraces.has(i) ? 'rotate-90' : ''"
                      fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
                    </svg>
                    {{ msg.toolTrace.length }} tool call{{ msg.toolTrace.length > 1 ? "s" : "" }}
                  </button>
                  <Transition name="fade">
                    <div v-if="expandedTraces.has(i)" class="mt-1.5 space-y-1.5">
                      <div v-for="(t, ti) in msg.toolTrace" :key="ti"
                        :class="['rounded-xl px-3 py-2 text-xs border',
                          traceStatusClass(t.output) === 'success' ? 'bg-green-50 border-green-200' :
                          traceStatusClass(t.output) === 'error'   ? 'bg-red-50 border-red-200' :
                                                                       'bg-gray-50 border-gray-200']">
                        <div class="flex items-center gap-1.5 font-medium text-gray-700 mb-1">
                          <span>{{ toolMeta(t.tool).icon }}</span>
                          <span>{{ toolMeta(t.tool).label }}</span>
                          <span class="text-gray-400 font-normal text-[10px]">{{ t.tool }}</span>
                          <span v-if="traceStatusClass(t.output) === 'success'" class="ml-auto text-green-500 text-[10px]">✓</span>
                          <span v-else-if="traceStatusClass(t.output) === 'error'" class="ml-auto text-red-500 text-[10px]">✗</span>
                        </div>
                        <p class="text-gray-500 font-mono text-[10px] whitespace-pre-wrap line-clamp-4">{{ t.output }}</p>
                      </div>
                    </div>
                  </Transition>
                </div>

                <p class="text-[10px] text-gray-300 mt-1 ml-1">{{ fmtTime(msg.ts) }}</p>
              </div>
            </div>

            <!-- ── Interrupt card (in-chat) ── -->
            <div v-else-if="msg.role === 'interrupt'" class="flex gap-2.5 max-w-[92%]">
              <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center text-white text-xs flex-shrink-0 mt-0.5">💬</div>
              <div class="flex-1 min-w-0">
                <div class="bg-amber-50 border border-amber-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
                  <p class="text-[10px] font-bold text-amber-600 uppercase tracking-wide mb-2">Decision needed</p>
                  <p class="text-sm text-gray-800 leading-relaxed" v-html="renderMd(msg.question)"></p>
                </div>
                <p class="text-[10px] text-gray-300 mt-1 ml-1">{{ fmtTime(msg.ts) }}</p>
              </div>
            </div>

          </div>

          <!-- ── Live streaming bubble ── -->
          <div v-if="isProcessing" class="flex gap-2.5 max-w-[92%]">
            <div class="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white text-xs flex-shrink-0 mt-0.5">✦</div>
            <div class="flex-1 min-w-0">
              <div class="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
                <!-- No steps yet: show thinking text -->
                <div v-if="!liveSteps.length" class="flex items-center gap-2 text-gray-500">
                  <svg class="w-4 h-4 animate-spin text-violet-400 flex-shrink-0" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                  </svg>
                  <span class="text-sm italic text-gray-500">{{ thinkingText }}</span>
                </div>
                <!-- Live tool steps -->
                <div v-else class="space-y-2">
                  <p class="text-[10px] text-gray-400 font-semibold uppercase tracking-wide mb-1.5">Working…</p>
                  <div v-for="step in liveSteps" :key="step.id"
                    class="flex items-start gap-2 text-xs">
                    <!-- Status icon -->
                    <div class="flex-shrink-0 mt-0.5">
                      <svg v-if="step.status === 'loading'" class="w-3.5 h-3.5 animate-spin text-violet-500" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                      </svg>
                      <span v-else-if="step.status === 'success'" class="text-green-500 text-sm leading-none">✓</span>
                      <span v-else class="text-red-500 text-sm leading-none">✗</span>
                    </div>
                    <!-- Step info -->
                    <div class="flex-1 min-w-0">
                      <span class="font-medium text-gray-700">{{ step.icon }} {{ step.label }}</span>
                      <span class="text-gray-400 ml-1">({{ step.tool }})</span>
                      <p v-if="step.output && step.status !== 'loading'"
                        class="text-[10px] text-gray-400 font-mono mt-0.5 truncate">
                        {{ step.output }}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- ── Human-in-the-loop decision panel ── -->
      <Transition name="decision-slide">
        <div v-if="interruptQ"
          class="flex-shrink-0 border-t-2 border-amber-300 bg-gradient-to-b from-amber-50 to-white px-4 pt-3.5 pb-4 shadow-[0_-4px_20px_rgba(0,0,0,0.08)]"
        >
          <div class="flex items-center gap-2 mb-3">
            <div class="w-6 h-6 rounded-lg bg-amber-400 flex items-center justify-center text-white text-xs flex-shrink-0">💬</div>
            <p class="text-sm font-bold text-amber-800">Sora needs your decision</p>
          </div>

          <!-- Parsed option buttons -->
          <div v-if="parseOptions(interruptQ).length" class="space-y-1.5 mb-3">
            <button
              v-for="opt in parseOptions(interruptQ)" :key="opt.key"
              @click="respond(`${opt.key}. ${opt.text}`)"
              :disabled="responding"
              class="w-full flex items-start gap-2.5 text-left text-sm px-3 py-2.5 rounded-xl border-2 border-amber-200 bg-white hover:bg-amber-50 hover:border-amber-400 transition-all text-gray-800 disabled:opacity-50 group"
            >
              <span class="w-5 h-5 rounded-full bg-amber-400 group-hover:bg-amber-500 text-white text-[10px] font-bold flex items-center justify-center flex-shrink-0 mt-0.5 transition-colors">
                {{ opt.key }}
              </span>
              <span class="leading-snug">{{ opt.text }}</span>
            </button>
          </div>

          <!-- Free-text answer -->
          <div class="flex gap-2">
            <input
              v-model="interruptAns"
              @keydown.enter.prevent="respond(interruptAns)"
              :disabled="responding"
              placeholder="Or type a custom answer…"
              class="flex-1 px-3 py-2 text-sm border-2 border-amber-200 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-amber-400 focus:border-transparent placeholder-amber-300 disabled:opacity-50"
            />
            <button
              @click="respond(interruptAns)"
              :disabled="!interruptAns.trim() || responding"
              class="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white text-sm font-bold rounded-xl disabled:opacity-40 transition-colors flex items-center gap-1.5"
            >
              <svg v-if="responding" class="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
              </svg>
              <span>{{ responding ? "…" : "Send" }}</span>
            </button>
          </div>
        </div>
      </Transition>

      <!-- ── Quick actions ── -->
      <div class="flex-shrink-0 border-t border-gray-100 px-4 pt-3 pb-2 bg-white">
        <p class="text-[10px] text-gray-400 uppercase tracking-wide font-semibold mb-2">Quick actions</p>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="qa in QUICK_ACTIONS" :key="qa.label"
            @click="send(qa.prompt)"
            :disabled="!canSend"
            :class="[
              'flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-full border transition-all',
              qa.label === 'Auto-fix conflicts' && conflictCount > 0
                ? 'bg-red-50 border-red-300 text-red-700 hover:bg-red-100'
                : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-violet-50 hover:border-violet-300 hover:text-violet-700',
              !canSend ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer',
            ]"
          >
            <span>{{ qa.icon }}</span>{{ qa.label }}
          </button>
        </div>
      </div>

      <!-- ── Input ── -->
      <div class="flex-shrink-0 border-t border-gray-100 p-4 bg-gray-50">
        <!-- Session-full banner -->
        <div v-if="sessionFull"
          class="mb-3 flex items-center justify-between bg-violet-50 border border-violet-200 rounded-xl px-3 py-2">
          <p class="text-xs text-violet-700">Session memory is full — start a new chat to continue.</p>
          <button @click="newChat"
            class="ml-2 text-xs font-bold text-violet-700 bg-violet-100 hover:bg-violet-200 px-2.5 py-1 rounded-lg transition-colors flex-shrink-0">
            + New chat
          </button>
        </div>

        <div class="flex gap-2 items-end">
          <div class="flex-1">
            <textarea
              v-model="input"
              @keydown="onKeydown"
              :disabled="!canSend || sessionFull"
              rows="2"
              :placeholder="interruptQ ? 'Use the decision panel above ↑' : sessionFull ? 'Session full — start a new chat' : 'Ask me anything about this timetable… (Enter to send)'"
              class="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-violet-400 focus:border-transparent bg-white placeholder-gray-400 disabled:opacity-40 transition-shadow"
            />
          </div>
          <button
            v-if="isProcessing"
            @click="stopProcessing"
            class="w-10 h-10 rounded-xl bg-red-500 hover:bg-red-600 text-white flex items-center justify-center flex-shrink-0 transition-colors shadow-md"
            title="Stop"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <rect x="6" y="6" width="12" height="12" rx="1"/>
            </svg>
          </button>
          <button
            v-else
            @click="send()"
            :disabled="!canSend || !input.trim() || sessionFull"
            class="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-600 to-indigo-600 text-white flex items-center justify-center flex-shrink-0 disabled:opacity-40 transition-opacity hover:opacity-90 shadow-md"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
            </svg>
          </button>
        </div>
        <p class="text-[10px] text-gray-400 mt-1.5 text-center">
          Sora AI · Changes are applied live · <span class="text-violet-400">streaming</span>
        </p>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.panel-slide-enter-active, .panel-slide-leave-active {
  transition: transform 0.28s cubic-bezier(0.4, 0, 0.2, 1);
}
.panel-slide-enter-from, .panel-slide-leave-to { transform: translateX(100%); }

.backdrop-enter-active, .backdrop-leave-active { transition: opacity 0.25s ease; }
.backdrop-enter-from, .backdrop-leave-to       { opacity: 0; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.18s ease, transform 0.18s ease; }
.fade-enter-from, .fade-leave-to       { opacity: 0; transform: translateY(-4px); }

.decision-slide-enter-active, .decision-slide-leave-active { transition: all 0.22s ease; }
.decision-slide-enter-from, .decision-slide-leave-to       { opacity: 0; transform: translateY(12px); }
</style>
