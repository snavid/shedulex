<script setup>
import { computed, reactive, ref, watch } from "vue"
import { useRoute } from "vue-router"
import { useToast } from "vue-toastification"

import { documentApi, getErrorMessage, notificationApi, resourcesApi, timetableApi } from "@/api/client"
import { useTimetableStore } from "@/stores/timetable"
import { useAuthStore } from "@/stores/auth"
import AIAssistantPanel from "@/components/AIAssistantPanel.vue"

const route = useRoute()
const store = useTimetableStore()
const auth = useAuthStore()
const toast = useToast()

const aiPanel = ref(null)
const loading = ref(true)
const conflictsLoading = ref(false)
const violationsLoading = ref(false)
const violations = ref([])
const showViolationsPanel = ref(false)
const exportPreviewLoading = ref(false)
const analyticsLoading = ref(false)
const exportPreview = ref(null)
const exportAnalytics = ref(null)
const shareLink = ref("")
const shareFormat = ref("bundle")
const shareExpiresHours = ref(24)
const exportStatus = ref("")
const pageError = ref("")
const versions = ref([])
const versionsLoading = ref(false)
const restoringSnapshotId = ref("")

// Calendar view state
const calendarView = ref("week") // "day" | "week" | "month"
const selectedDay = ref("Monday")
const filterProgram = ref("")
const filterLecturer = ref("")

// Session modal
const selectedEntry = ref(null)
const showSessionModal = ref(false)
const reminderForm = ref({ hours_before: 2, channel: "both", scheduled_at: "" })
const sendingReminder = ref(false)

const exportOps = ref({ pdf: false, excel: false, csv: false, bundle: false, share: false })
const templateBlocks = ref([])

// ── Drag & Drop ───────────────────────────────────────────────────────────────
const allTimeSlots = ref([])          // from GET /time-slots
const draggingEntry = ref(null)       // entry currently being dragged
const dragOverCell = ref(null)        // "Day__HH:MM" of the cell being hovered

// Full slot lookup: slotMap[day][start_time] = TimeSlot
// Built from API slots (covers empty cells) + entry slots (authoritative IDs)
const slotMap = computed(() => {
  const map = {}
  for (const s of allTimeSlots.value) {
    if (!map[s.day]) map[s.day] = {}
    map[s.day][s.start_time] = s
  }
  for (const e of (store.currentTimetable?.entries || [])) {
    const s = e.time_slot
    if (!s?.id) continue
    if (!map[s.day]) map[s.day] = {}
    map[s.day][s.start_time] = s
  }
  return map
})

const moveModal = reactive({
  visible: false,
  entry: null,
  fromSlot: null,
  targetSlot: null,
  conflicts: [],
  moving: false,
})

function isBreakSlot(slot) {
  return !!(slot.is_break || ["break", "lunch"].includes(slot.slot_type || slot.block_type))
}

function onDragStart(evt, entry) {
  if (entry.is_locked || !auth.isAdmin && !auth.isTimetableOfficer) {
    evt.preventDefault(); return
  }
  draggingEntry.value = entry
  evt.dataTransfer.effectAllowed = "move"
  evt.dataTransfer.setData("text/plain", entry.id)
}

function onDragEnd() {
  draggingEntry.value = null
  dragOverCell.value = null
}

function onDragOver(evt, day, slot) {
  if (!draggingEntry.value || isBreakSlot(slot)) return
  evt.preventDefault()
  evt.dataTransfer.dropEffect = "move"
  dragOverCell.value = `${day}__${slot.start_time}`
}

function onDragLeave(evt) {
  if (!evt.currentTarget.contains(evt.relatedTarget)) {
    dragOverCell.value = null
  }
}

function onDrop(evt, day, slot) {
  evt.preventDefault()
  dragOverCell.value = null
  if (!draggingEntry.value || isBreakSlot(slot)) return

  const entry = draggingEntry.value
  draggingEntry.value = null

  // No-op if dropped back on the same cell
  if (entry.time_slot?.day === day && entry.time_slot?.start_time === slot.start_time) return

  // Resolve the TimeSlot object for this (day, start_time)
  const targetSlot = slotMap.value[day]?.[slot.start_time]
  if (!targetSlot?.id) {
    toast.error(`No time slot found for ${day} ${slot.start_time}. Re-generate slots from a template first.`)
    return
  }

  const conflicts = detectMoveConflicts(entry, day, slot.start_time)
  Object.assign(moveModal, {
    visible: true, entry,
    fromSlot: entry.time_slot,
    targetSlot: { ...targetSlot, day },
    conflicts, moving: false,
  })
}

function detectMoveConflicts(entry, targetDay, targetStartTime) {
  const conflicts = []
  const occupants = timetableGrid.value[`${targetDay}__${targetStartTime}`] || []
  for (const other of occupants) {
    if (other.id === entry.id) continue
    if (entry.lecturer?.id && other.lecturer?.id === entry.lecturer.id) {
      conflicts.push({
        type: "lecturer", icon: "👤", label: "Lecturer Conflict",
        detail: `${entry.lecturer.name} is already teaching`,
        conflicting: other,
      })
    }
    if (entry.room?.id && other.room?.id === entry.room.id) {
      conflicts.push({
        type: "room", icon: "🏛", label: "Room Conflict",
        detail: `${entry.room.name} (${entry.room.code}) is already occupied`,
        conflicting: other,
      })
    }
    if (entry.student_group?.id && other.student_group?.id === entry.student_group.id) {
      conflicts.push({
        type: "group", icon: "👥", label: "Student Group Conflict",
        detail: `${entry.student_group.name} already has a session`,
        conflicting: other,
      })
    }
  }
  return conflicts
}

async function confirmMove() {
  moveModal.moving = true
  try {
    await timetableApi.moveEntry(moveModal.entry.id, moveModal.targetSlot.id)
    toast.success(`Moved ${moveModal.entry.course?.code} → ${moveModal.targetSlot.day} ${moveModal.targetSlot.start_time}`)
    moveModal.visible = false
    await store.fetchTimetable(route.params.id)
    const tid = store.currentTimetable?.template_id
    if (tid) resourcesApi.getTemplate(tid)
      .then(({ data }) => { templateBlocks.value = data.data?.blocks || [] })
      .catch(() => {})
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to move session."))
  } finally {
    moveModal.moving = false
  }
}

async function loadAllSlots() {
  try {
    const { data } = await resourcesApi.timeSlots()
    allTimeSlots.value = data.data || []
  } catch { allTimeSlots.value = [] }
}

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

const entryColors = [
  "bg-blue-600", "bg-purple-600", "bg-green-600", "bg-orange-500",
  "bg-pink-600", "bg-teal-600", "bg-red-600", "bg-indigo-600",
]
const colorCache = {}

function getEntryColor(courseId) {
  if (!colorCache[courseId]) {
    colorCache[courseId] = entryColors[Object.keys(colorCache).length % entryColors.length]
  }
  return colorCache[courseId]
}

// Filtered entries based on active program / lecturer filter
const filteredEntries = computed(() => {
  if (!store.currentTimetable?.entries) return []
  let entries = store.currentTimetable.entries
  if (filterProgram.value) {
    entries = entries.filter((e) => e.course?.program_id === filterProgram.value)
  }
  if (filterLecturer.value) {
    entries = entries.filter((e) => e.lecturer?.id === filterLecturer.value)
  }
  return entries
})

const uniquePrograms = computed(() => {
  if (!store.currentTimetable?.entries) return []
  const seen = new Map()
  for (const e of store.currentTimetable.entries) {
    const p = e.course?.program
    if (p && !seen.has(p.id)) seen.set(p.id, p)
  }
  return [...seen.values()]
})

const uniqueLecturers = computed(() => {
  if (!store.currentTimetable?.entries) return []
  const seen = new Map()
  for (const e of store.currentTimetable.entries) {
    const l = e.lecturer
    if (l && !seen.has(l.id)) seen.set(l.id, l)
  }
  return [...seen.values()]
})

// Week-view grid
const timetableGrid = computed(() => {
  const grid = {}
  for (const entry of filteredEntries.value) {
    const slot = entry.time_slot
    if (!slot) continue
    const key = `${slot.day}__${slot.start_time}`
    if (!grid[key]) grid[key] = []
    grid[key].push(entry)
  }
  return grid
})

// Slots for week/day view — rows represent unique time periods.
// Prefer template blocks so breaks/lunch show even when no entries exist.
// Fall back to entry-derived slots when no template is linked.
const timeSlots = computed(() => {
  if (templateBlocks.value.length) {
    const seen = new Set()
    const rows = []
    const sorted = [...templateBlocks.value].sort(
      (a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.start_time.localeCompare(b.start_time)
    )
    for (const b of sorted) {
      const key = `${b.start_time}__${b.end_time}`
      if (!seen.has(key)) { seen.add(key); rows.push(b) }
    }
    return rows
  }
  if (!store.currentTimetable?.entries) return []
  const seen = new Set()
  const slots = []
  for (const entry of store.currentTimetable.entries) {
    const slot = entry.time_slot
    if (!slot) continue
    const key = `${slot.start_time}__${slot.end_time}`
    if (!seen.has(key)) { seen.add(key); slots.push(slot) }
  }
  return slots.sort((a, b) => a.start_time.localeCompare(b.start_time))
})

// Day-view: entries for selectedDay
const dayEntries = computed(() =>
  filteredEntries.value
    .filter((e) => e.time_slot?.day === selectedDay.value)
    .sort((a, b) => (a.time_slot?.slot_index || 0) - (b.time_slot?.slot_index || 0))
)

// Month-view: group entries by day-of-week (simplified)
const monthDaySummaries = computed(() =>
  DAYS.map((day) => ({
    day,
    count: filteredEntries.value.filter((e) => e.time_slot?.day === day).length,
  }))
)

// Session modal
function openSession(entry) {
  selectedEntry.value = entry
  reminderForm.value = { hours_before: 2, channel: "both", scheduled_at: "" }
  showSessionModal.value = true
}

function closeModal() {
  showSessionModal.value = false
  selectedEntry.value = null
}

async function sendReminder() {
  if (!selectedEntry.value) return
  sendingReminder.value = true
  try {
    const entry = selectedEntry.value
    const classTime = entry.time_slot
      ? `${entry.time_slot.day} ${entry.time_slot.start_time}`
      : "class"

    await notificationApi.send({
      recipient_id: entry.lecturer?.user_id,
      recipient_email: entry.lecturer?.email,
      channel: reminderForm.value.channel,
      notification_type: "reminder",
      subject: `Reminder: ${entry.course?.name}`,
      body: `You have ${entry.course?.name} at ${classTime} in ${entry.room?.name || "TBD"}.`,
      scheduled_at: reminderForm.value.scheduled_at || undefined,
    })
    toast.success("Reminder scheduled.")
    closeModal()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to send reminder."))
  } finally {
    sendingReminder.value = false
  }
}

// Export helpers (unchanged from before)
const exportCountsByFormat = computed(() => {
  const rows = exportAnalytics.value?.by_format || []
  const result = { pdf: 0, excel: 0, csv: 0, bundle: 0 }
  for (const row of rows) {
    if (row?.format in result) result[row.format] = row.count
  }
  return result
})

const recommendedFormat = computed(() => {
  const format = exportPreview.value?.insights?.recommended_format
  return ["pdf", "excel", "csv", "bundle"].includes(format) ? format : "bundle"
})

const complexityTier = computed(() => exportPreview.value?.insights?.complexity_tier || "n/a")

function setExportLoading(format, state) {
  exportOps.value = { ...exportOps.value, [format]: state }
}

function parseFilename(contentDisposition, fallback) {
  if (!contentDisposition) return fallback
  const match = contentDisposition.match(/filename="?([^"]+)"?/)
  return match?.[1] || fallback
}

function saveBlob(blob, filename) {
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = objectUrl
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(objectUrl)
}

async function loadExportPreview() {
  exportPreviewLoading.value = true
  try {
    const { data } = await documentApi.preview(route.params.id)
    exportPreview.value = data.data
    shareFormat.value = recommendedFormat.value
  } catch {
    exportPreview.value = null
  } finally {
    exportPreviewLoading.value = false
  }
}

async function loadExportAnalytics() {
  analyticsLoading.value = true
  try {
    const { data } = await documentApi.analyticsOverview({ limit: 8 })
    exportAnalytics.value = data.data
  } catch {
    exportAnalytics.value = null
  } finally {
    analyticsLoading.value = false
  }
}

async function runExport(format) {
  const timetableId = route.params.id
  setExportLoading(format, true)
  try {
    let response, fallbackFilename
    if (format === "pdf") {
      response = await documentApi.downloadPdfBlob(timetableId)
      fallbackFilename = `timetable-${String(timetableId).slice(0, 8)}.pdf`
    } else if (format === "excel") {
      response = await documentApi.downloadExcelBlob(timetableId)
      fallbackFilename = `timetable-${String(timetableId).slice(0, 8)}.xlsx`
    } else if (format === "csv") {
      response = await documentApi.downloadCsvBlob(timetableId)
      fallbackFilename = `timetable-${String(timetableId).slice(0, 8)}.csv`
    } else {
      response = await documentApi.downloadBundleBlob(timetableId)
      fallbackFilename = `timetable-${String(timetableId).slice(0, 8)}.zip`
    }
    const filename = parseFilename(response.headers?.["content-disposition"], fallbackFilename)
    saveBlob(response.data, filename)
    toast.success(`Export ready: ${filename}`)
    exportStatus.value = `Export generated successfully: ${filename}`
    await loadExportAnalytics()
  } catch (error) {
    toast.error(error.response?.data?.message || "Export failed.")
    exportStatus.value = "Export failed."
  } finally {
    setExportLoading(format, false)
  }
}

async function createSecureShareLink() {
  setExportLoading("share", true)
  try {
    const { data } = await documentApi.createShareLink({
      timetable_id: route.params.id,
      format: shareFormat.value,
      expires_hours: Number(shareExpiresHours.value),
    })
    shareLink.value = data.data.download_url
    toast.success("Share link generated.")
    exportStatus.value = "Secure share link generated."
    await loadExportAnalytics()
  } catch (error) {
    toast.error(error.response?.data?.message || "Could not create share link.")
  } finally {
    setExportLoading("share", false)
  }
}

async function copyShareLink() {
  if (!shareLink.value) return
  try {
    await navigator.clipboard.writeText(shareLink.value)
    toast.success("Share link copied.")
  } catch {
    toast.error("Failed to copy share link.")
  }
}

async function loadVersions() {
  versionsLoading.value = true
  try {
    const { data } = await timetableApi.listVersions(route.params.id)
    versions.value = data.data || []
  } catch {
    versions.value = []
  } finally {
    versionsLoading.value = false
  }
}

async function restoreSnapshot(snapshotId) {
  if (!window.confirm("Restore this snapshot? Current timetable entries will be replaced.")) return
  restoringSnapshotId.value = snapshotId
  try {
    await timetableApi.restoreVersion(snapshotId)
    toast.success("Timetable restored from snapshot.")
    await store.fetchTimetable(route.params.id)
    await loadVersions()
  } catch (e) {
    toast.error(getErrorMessage(e, "Could not restore version."))
  } finally {
    restoringSnapshotId.value = ""
  }
}

async function detectConflicts() {
  conflictsLoading.value = true
  try {
    const conflicts = await store.detectConflicts(route.params.id)
    if (conflicts.length === 0) {
      toast.success("No conflicts detected.")
    } else {
      toast.warning(`${conflicts.length} conflict(s) found.`)
    }
  } finally {
    conflictsLoading.value = false
  }
}

async function loadViolations() {
  violationsLoading.value = true
  try {
    const { data } = await timetableApi.violations(route.params.id)
    violations.value = data.data || []
    showViolationsPanel.value = true
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load violation report."))
  } finally {
    violationsLoading.value = false
  }
}

async function toggleLock(entry) {
  try {
    await timetableApi.toggleLock(route.params.id, entry.id)
    entry.is_locked = !entry.is_locked
    toast.success(entry.is_locked ? "Entry locked." : "Entry unlocked.")
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to toggle lock."))
  }
}

async function loadTimetablePage(id) {
  if (!id) return
  loading.value = true
  pageError.value = ""
  templateBlocks.value = []
  try {
    await store.fetchTimetable(id)
    const templateId = store.currentTimetable?.template_id
    await Promise.all([
      loadExportPreview(),
      loadExportAnalytics(),
      loadVersions(),
      loadAllSlots(),
      templateId
        ? resourcesApi.getTemplate(templateId)
            .then(({ data }) => { templateBlocks.value = data.data?.blocks || [] })
            .catch(() => {})
        : Promise.resolve(),
    ])
  } catch (e) {
    pageError.value = getErrorMessage(e, "Failed to load timetable details.")
  } finally {
    loading.value = false
  }
}

watch(() => route.params.id, (id) => loadTimetablePage(id), { immediate: true })
</script>

<template>
  <div class="space-y-6">
    <div v-if="loading" class="animate-pulse space-y-4">
      <div class="h-8 bg-gray-200 rounded w-1/3"></div>
      <div class="card h-96 bg-gray-200 rounded"></div>
    </div>

    <div v-else-if="pageError" class="card border-red-200 bg-red-50 text-red-700 text-sm">{{ pageError }}</div>

    <template v-else-if="store.currentTimetable">
      <!-- Header -->
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 class="text-2xl font-bold text-gray-900">{{ store.currentTimetable.name }}</h1>
          <p class="text-gray-500 text-sm">
            {{ store.currentTimetable.department?.name }}
            <span v-if="store.currentTimetable.program">
              · {{ store.currentTimetable.program.name }} ({{ store.currentTimetable.program.code }})
            </span>
            · Semester {{ store.currentTimetable.semester }}
            · {{ store.currentTimetable.academic_year }}
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <button @click="detectConflicts" :disabled="conflictsLoading" class="btn-secondary flex items-center gap-2 text-sm">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
            </svg>
            {{ conflictsLoading ? "Checking…" : "Check Conflicts" }}
          </button>
          <button @click="loadViolations" :disabled="violationsLoading" class="btn-secondary flex items-center gap-2 text-sm">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
            </svg>
            {{ violationsLoading ? "Loading…" : "Violation Report" }}
          </button>
          <button @click="aiPanel?.open()" class="btn-secondary text-sm flex items-center gap-1.5">
            <span class="text-violet-500">✦</span> AI Assist
          </button>
        </div>
      </div>

      <!-- Violation Report Panel -->
      <div v-if="showViolationsPanel" class="card space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="font-semibold text-gray-900 flex items-center gap-2">
            <svg class="w-5 h-5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
            </svg>
            Constraint Violation Report
            <span class="px-2 py-0.5 rounded-full text-xs font-semibold"
              :class="violations.length ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'">
              {{ violations.length }} issue{{ violations.length !== 1 ? 's' : '' }}
            </span>
          </h3>
          <button @click="showViolationsPanel = false" class="text-gray-400 hover:text-gray-600">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
        </div>

        <div v-if="!violations.length" class="flex items-center gap-2 text-green-700 bg-green-50 p-3 rounded-xl text-sm">
          <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          All constraints are satisfied. No violations found in this timetable.
        </div>

        <div v-else class="space-y-2 max-h-72 overflow-y-auto">
          <div v-for="v in violations" :key="v.message"
            class="flex items-start gap-3 p-3 rounded-xl border text-sm"
            :class="v.severity === 'high' ? 'bg-red-50 border-red-200' : v.severity === 'medium' ? 'bg-amber-50 border-amber-200' : 'bg-gray-50 border-gray-200'">
            <span class="text-lg flex-shrink-0 mt-0.5">
              {{ v.severity === 'high' ? '⛔' : v.severity === 'medium' ? '⚠️' : 'ℹ️' }}
            </span>
            <div class="flex-1 min-w-0">
              <p class="font-semibold text-gray-800 text-xs uppercase tracking-wide mb-0.5">
                {{ v.rule || v.type }}
                <span class="normal-case font-normal text-gray-500 ml-1">({{ v.category || v.severity }})</span>
              </p>
              <p class="text-gray-700">{{ v.message }}</p>
            </div>
          </div>
        </div>

        <p class="text-xs text-gray-400">
          This report reflects the GA's constraint evaluation from when the timetable was generated.
          Use drag-and-drop or the AI assistant to resolve issues manually.
        </p>
      </div>

      <!-- Stored violation count from last GA run -->
      <div v-if="store.currentTimetable.violation_report?.length && !showViolationsPanel"
        class="card bg-amber-50 border-amber-200 flex items-center gap-3 py-3 cursor-pointer hover:bg-amber-100 transition-colors"
        @click="loadViolations">
        <svg class="w-5 h-5 text-amber-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
        </svg>
        <p class="text-sm text-amber-800">
          <strong>{{ store.currentTimetable.violation_report.length }} constraint note(s)</strong> from the last GA run.
          Click to view the full violation report.
        </p>
      </div>

      <!-- Stats -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="card text-center">
          <p class="text-2xl font-bold text-blue-600">{{ (store.currentTimetable.fitness_score * 100).toFixed(1) }}%</p>
          <p class="text-xs text-gray-500 mt-1">Fitness Score</p>
        </div>
        <div class="card text-center">
          <p class="text-2xl font-bold text-gray-900">{{ store.currentTimetable.entries?.length || 0 }}</p>
          <p class="text-xs text-gray-500 mt-1">Total Sessions</p>
        </div>
        <div class="card text-center">
          <p class="text-2xl font-bold text-gray-900">{{ store.currentTimetable.generations_run }}</p>
          <p class="text-xs text-gray-500 mt-1">GA Generations</p>
        </div>
        <div class="card text-center">
          <p class="text-2xl font-bold text-gray-900">{{ store.currentTimetable.generation_time_seconds?.toFixed(1) }}s</p>
          <p class="text-xs text-gray-500 mt-1">Generation Time</p>
        </div>
      </div>

      <!-- Schedule Grid Card -->
      <div class="card overflow-hidden p-0">
        <!-- Toolbar -->
        <div class="p-4 border-b border-gray-200 flex flex-wrap items-center gap-3">
          <h2 class="font-semibold text-gray-900 mr-auto">Schedule</h2>

          <!-- View toggle -->
          <div class="flex rounded-lg border border-gray-200 overflow-hidden text-sm">
            <button
              v-for="v in ['day', 'week', 'month']"
              :key="v"
              @click="calendarView = v"
              :class="['px-3 py-1.5 capitalize', calendarView === v ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50']"
            >{{ v }}</button>
          </div>

          <!-- Day selector (day-view only) -->
          <select v-if="calendarView === 'day'" v-model="selectedDay" class="input w-auto text-sm">
            <option v-for="d in DAYS" :key="d" :value="d">{{ d }}</option>
          </select>

          <!-- Filters -->
          <select v-if="uniquePrograms.length" v-model="filterProgram" class="input w-auto text-sm">
            <option value="">All Programs</option>
            <option v-for="p in uniquePrograms" :key="p.id" :value="p.id">{{ p.code }}</option>
          </select>
          <select v-if="uniqueLecturers.length" v-model="filterLecturer" class="input w-auto text-sm">
            <option value="">All Lecturers</option>
            <option v-for="l in uniqueLecturers" :key="l.id" :value="l.id">{{ l.name }}</option>
          </select>
        </div>

        <!-- WEEK VIEW -->
        <div v-if="calendarView === 'week'" class="overflow-x-auto">
          <div v-if="auth.isAdmin || auth.isTimetableOfficer" class="px-4 py-2 text-xs text-blue-600 bg-blue-50 border-b border-blue-100 flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"/>
            </svg>
            Drag sessions to reschedule · Locked sessions cannot be moved
          </div>
          <table class="w-full border-collapse min-w-[700px]">
            <thead>
              <tr>
                <th class="bg-gray-50 border border-gray-200 p-3 text-left text-xs font-semibold text-gray-600 w-28">Time</th>
                <th v-for="day in DAYS" :key="day" class="bg-gray-50 border border-gray-200 p-3 text-center text-xs font-semibold text-gray-600">{{ day }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="slot in timeSlots" :key="`${slot.id || slot.start_time}`"
                :class="isBreakSlot(slot) ? 'bg-yellow-50' : ''">
                <td class="border border-gray-200 p-2 text-xs font-medium text-gray-600 whitespace-nowrap">
                  <div>{{ slot.start_time }} – {{ slot.end_time }}</div>
                  <div v-if="slot.label" class="text-gray-400 text-xs mt-0.5">{{ slot.label }}</div>
                  <span v-if="isBreakSlot(slot) && (slot.slot_type || slot.block_type) === 'lunch'" class="block text-green-600 font-semibold">LUNCH</span>
                  <span v-else-if="isBreakSlot(slot)" class="block text-orange-600 font-semibold">BREAK</span>
                </td>
                <td
                  v-for="day in DAYS" :key="day"
                  class="border border-gray-200 p-1 align-top min-w-[130px] transition-colors duration-100"
                  :class="{
                    'bg-blue-50 ring-2 ring-inset ring-blue-400': dragOverCell === `${day}__${slot.start_time}` && !isBreakSlot(slot),
                    'bg-gray-50 cursor-not-allowed': isBreakSlot(slot),
                  }"
                  @dragover="onDragOver($event, day, slot)"
                  @dragleave="onDragLeave($event)"
                  @drop="onDrop($event, day, slot)"
                >
                  <!-- Drop-zone hint (shown when dragging and cell is empty) -->
                  <div
                    v-if="draggingEntry && !isBreakSlot(slot) && !(timetableGrid[`${day}__${slot.start_time}`]?.length)"
                    class="h-12 rounded border-2 border-dashed border-blue-200 flex items-center justify-center text-xs text-blue-300 pointer-events-none select-none"
                  >
                    drop here
                  </div>

                  <div
                    v-for="entry in (timetableGrid[`${day}__${slot.start_time}`] || [])"
                    :key="entry.id"
                    :draggable="!entry.is_locked && (auth.isAdmin || auth.isTimetableOfficer)"
                    :class="[
                      'timetable-entry relative group transition-opacity',
                      getEntryColor(entry.course?.id),
                      entry.is_locked ? 'ring-1 ring-gray-300 opacity-80 cursor-not-allowed' : 'cursor-grab active:cursor-grabbing',
                      draggingEntry?.id === entry.id ? 'opacity-30 scale-95' : 'opacity-100',
                    ]"
                    @click="!draggingEntry && openSession(entry)"
                    @dragstart="onDragStart($event, entry)"
                    @dragend="onDragEnd"
                  >
                    <div class="flex items-start justify-between gap-1">
                      <p class="font-bold truncate text-xs leading-tight">{{ entry.course?.code }}</p>
                      <div class="flex items-center gap-0.5 flex-shrink-0">
                        <!-- Year badge: prefer student_group year, fall back to course year -->
                        <span
                          v-if="(entry.student_group?.year_of_study || entry.course?.year_of_study)"
                          class="bg-white/25 text-white text-[9px] font-bold px-1 py-0.5 rounded leading-none"
                          :title="`Year ${entry.student_group?.year_of_study || entry.course?.year_of_study} of study`"
                        >Y{{ entry.student_group?.year_of_study || entry.course?.year_of_study }}</span>
                        <span v-if="entry.is_locked" class="text-white opacity-70" title="Locked">🔒</span>
                        <button v-else class="text-white opacity-0 group-hover:opacity-60" title="Lock"
                          @click.stop="toggleLock(entry)">🔓</button>
                      </div>
                    </div>
                    <p class="truncate opacity-90 text-xs">{{ entry.course?.name }}</p>
                    <p class="opacity-75 truncate text-xs">{{ entry.room?.code }}</p>
                    <p class="opacity-75 truncate text-xs">{{ entry.lecturer?.name?.split(" ")[0] }}</p>
                    <span v-if="entry.student_group" class="text-xs opacity-60 truncate block">{{ entry.student_group.code }}</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- DAY VIEW -->
        <div v-else-if="calendarView === 'day'" class="p-4 space-y-2">
          <div v-if="!dayEntries.length" class="text-sm text-gray-500 py-4 text-center">No sessions on {{ selectedDay }}.</div>
          <div
            v-for="entry in dayEntries"
            :key="entry.id"
            class="flex items-start gap-4 p-3 rounded-lg border border-gray-200 hover:bg-gray-50 cursor-pointer"
            @click="openSession(entry)"
          >
            <div class="text-center min-w-[60px]">
              <p class="text-sm font-semibold text-gray-900">{{ entry.time_slot?.start_time }}</p>
              <p class="text-xs text-gray-500">{{ entry.time_slot?.end_time }}</p>
            </div>
            <div :class="['w-1 self-stretch rounded', getEntryColor(entry.course?.id)]"></div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2">
                <p class="font-semibold text-gray-900 truncate">{{ entry.course?.name }}</p>
                <span
                  v-if="entry.student_group?.year_of_study || entry.course?.year_of_study"
                  class="flex-shrink-0 text-[10px] font-bold bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded"
                >Year {{ entry.student_group?.year_of_study || entry.course?.year_of_study }}</span>
              </div>
              <p class="text-xs text-gray-500">
                {{ entry.course?.code }}
                <span v-if="entry.course?.program"> · {{ entry.course.program.name }}</span>
              </p>
              <p class="text-xs text-gray-500">
                <span>{{ entry.lecturer?.name }}</span>
                <span v-if="entry.room"> · Room {{ entry.room?.name }}</span>
                <span v-if="entry.student_group"> · {{ entry.student_group.name }}</span>
              </p>
            </div>
          </div>
        </div>

        <!-- MONTH VIEW (day-of-week summary) -->
        <div v-else class="p-4">
          <p class="text-xs text-gray-500 mb-4">Session count per weekday for the active timetable.</p>
          <div class="grid grid-cols-5 gap-3">
            <div
              v-for="item in monthDaySummaries"
              :key="item.day"
              class="rounded-lg border border-gray-200 p-4 text-center cursor-pointer hover:bg-gray-50"
              @click="calendarView = 'day'; selectedDay = item.day"
            >
              <p class="font-semibold text-gray-900 text-sm">{{ item.day }}</p>
              <p class="text-2xl font-bold text-blue-600 mt-1">{{ item.count }}</p>
              <p class="text-xs text-gray-400">sessions</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Conflicts -->
      <div v-if="store.conflicts.length" class="card border-red-200 bg-red-50">
        <h3 class="font-semibold text-red-900 mb-3">{{ store.conflicts.length }} Conflict(s) Detected</h3>
        <ul class="space-y-2">
          <li v-for="(c, i) in store.conflicts" :key="i" class="text-sm text-red-700 bg-white rounded-lg p-2 border border-red-200">
            <strong>{{ c.type?.replace(/_/g, ' ').toUpperCase() }}:</strong> {{ c.message }}
          </li>
        </ul>
        <button @click="aiPanel?.open()" class="mt-3 inline-flex items-center gap-2 text-sm text-violet-600 hover:text-violet-700 font-medium">
          <span>✦</span> Ask Sora AI to resolve conflicts
        </button>
      </div>

      <!-- Export Center -->
      <div class="card space-y-4">
        <p class="sr-only" aria-live="polite">{{ exportStatus }}</p>
        <div class="flex items-center justify-between">
          <div>
            <h2 class="font-semibold text-gray-900">Export Center</h2>
            <p class="text-xs text-gray-500">Fast downloads, secure sharing, and export analytics.</p>
          </div>
          <div class="text-xs text-gray-500" v-if="analyticsLoading">Loading analytics...</div>
        </div>
        <div class="text-xs text-gray-600 bg-blue-50 border border-blue-100 rounded p-2 flex flex-wrap gap-3">
          <span>Recommended: <strong class="uppercase">{{ recommendedFormat }}</strong></span>
          <span>Complexity: <strong class="capitalize">{{ complexityTier }}</strong></span>
          <span v-if="exportPreview?.summary?.peak_day">Peak day: <strong>{{ exportPreview.summary.peak_day }}</strong></span>
        </div>
        <div class="grid md:grid-cols-4 gap-3">
          <button class="btn-secondary" :disabled="exportOps.pdf" @click="runExport('pdf')">{{ exportOps.pdf ? "Exporting..." : "PDF" }}</button>
          <button class="btn-secondary" :disabled="exportOps.excel" @click="runExport('excel')">{{ exportOps.excel ? "Exporting..." : "Excel" }}</button>
          <button class="btn-secondary" :disabled="exportOps.csv" @click="runExport('csv')">{{ exportOps.csv ? "Exporting..." : "CSV" }}</button>
          <button class="btn-primary" :disabled="exportOps.bundle" @click="runExport('bundle')">{{ exportOps.bundle ? "Packaging..." : "Bundle (.zip)" }}</button>
        </div>
        <div class="grid md:grid-cols-2 gap-4">
          <div class="p-4 border border-gray-200 rounded-lg bg-gray-50 space-y-3">
            <h3 class="font-semibold text-sm text-gray-900">Secure Share Link</h3>
            <div class="grid grid-cols-2 gap-2">
              <select v-model="shareFormat" class="input">
                <option value="bundle">Bundle</option>
                <option value="pdf">PDF</option>
                <option value="excel">Excel</option>
                <option value="csv">CSV</option>
              </select>
              <input v-model.number="shareExpiresHours" type="number" min="1" max="168" class="input" placeholder="Expiry (hours)" />
            </div>
            <button class="btn-secondary w-full" :disabled="exportOps.share" @click="createSecureShareLink">{{ exportOps.share ? "Generating..." : "Generate Share Link" }}</button>
            <div v-if="shareLink" class="space-y-2">
              <input :value="shareLink" readonly class="input text-xs" />
              <button class="btn-primary w-full" @click="copyShareLink">Copy Link</button>
            </div>
          </div>
          <div class="p-4 border border-gray-200 rounded-lg bg-gray-50 space-y-3">
            <h3 class="font-semibold text-sm text-gray-900">Export Insights</h3>
            <div class="grid grid-cols-2 gap-2 text-sm">
              <div class="p-2 bg-white rounded border">PDF: <strong>{{ exportCountsByFormat.pdf }}</strong></div>
              <div class="p-2 bg-white rounded border">Excel: <strong>{{ exportCountsByFormat.excel }}</strong></div>
              <div class="p-2 bg-white rounded border">CSV: <strong>{{ exportCountsByFormat.csv }}</strong></div>
              <div class="p-2 bg-white rounded border">Bundle: <strong>{{ exportCountsByFormat.bundle }}</strong></div>
            </div>
            <ul class="text-xs text-gray-600 list-disc pl-4 space-y-1">
              <li v-for="tip in exportPreview?.recommendations || []" :key="tip">{{ tip }}</li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Version snapshots -->
      <div class="card space-y-3">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold text-gray-900">Version Snapshots</h2>
          <span v-if="versionsLoading" class="text-xs text-gray-500">Loading…</span>
        </div>
        <p v-if="!versions.length && !versionsLoading" class="text-sm text-gray-500">No snapshots yet.</p>
        <ul v-else class="divide-y divide-gray-100 border border-gray-100 rounded-lg overflow-hidden">
          <li v-for="v in versions" :key="v.id" class="flex flex-wrap items-center justify-between gap-2 px-3 py-3 bg-white">
            <div class="min-w-0">
              <p class="text-sm font-medium text-gray-900 truncate">{{ v.notes || "Snapshot" }}</p>
              <p class="text-xs text-gray-500">{{ new Date(v.created_at).toLocaleString() }} · v{{ v.version }} · {{ v.entry_count }} entries</p>
            </div>
            <button v-if="auth.isTimetableOfficer" type="button" class="btn-secondary text-xs shrink-0" :disabled="restoringSnapshotId === v.id" @click="restoreSnapshot(v.id)">
              {{ restoringSnapshotId === v.id ? "Restoring…" : "Restore" }}
            </button>
          </li>
        </ul>
      </div>
    </template>

    <!-- ── Floating AI Button ─────────────────────────────────────────────────── -->
    <Teleport to="body">
      <button
        @click="aiPanel?.open()"
        class="fixed bottom-6 right-6 z-30 w-14 h-14 rounded-full bg-gradient-to-br from-violet-600 via-purple-600 to-indigo-600 text-white shadow-xl shadow-violet-500/40 flex items-center justify-center text-2xl hover:scale-110 active:scale-95 transition-transform select-none"
        :class="store.conflicts.length ? 'animate-pulse' : ''"
        title="Open Sora AI Assistant"
      >
        ✦
      </button>
      <AIAssistantPanel
        ref="aiPanel"
        :timetable-id="String(route.params.id)"
        :timetable-name="store.currentTimetable?.name || 'Timetable'"
        :conflict-count="store.conflicts.length"
        @refresh="store.fetchTimetable(route.params.id)"
      />
    </Teleport>

    <!-- Session Detail Modal -->
    <Teleport to="body">
      <div v-if="showSessionModal && selectedEntry" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" @click.self="closeModal">
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden">
          <!-- Modal header -->
          <div :class="['p-5 text-white', getEntryColor(selectedEntry.course?.id)]">
            <div class="flex items-start justify-between gap-2">
              <div>
                <div class="flex items-center gap-2 flex-wrap">
                  <p class="text-xs opacity-80 font-medium uppercase tracking-wide">{{ selectedEntry.course?.code }}</p>
                  <span
                    v-if="selectedEntry.student_group?.year_of_study || selectedEntry.course?.year_of_study"
                    class="text-[10px] font-bold bg-white/25 text-white px-1.5 py-0.5 rounded"
                  >Year {{ selectedEntry.student_group?.year_of_study || selectedEntry.course?.year_of_study }}</span>
                </div>
                <h2 class="text-xl font-bold mt-0.5">{{ selectedEntry.course?.name }}</h2>
              </div>
              <button @click="closeModal" class="text-white opacity-70 hover:opacity-100 text-2xl leading-none">&times;</button>
            </div>
          </div>

          <!-- Session details -->
          <div class="p-5 space-y-3 text-sm">
            <div class="grid grid-cols-2 gap-3">
              <div class="bg-gray-50 rounded-lg p-3">
                <p class="text-xs text-gray-500 font-medium">Time</p>
                <p class="font-semibold text-gray-900 mt-0.5">
                  {{ selectedEntry.time_slot?.day }} {{ selectedEntry.time_slot?.start_time }}–{{ selectedEntry.time_slot?.end_time }}
                </p>
              </div>
              <div class="bg-gray-50 rounded-lg p-3">
                <p class="text-xs text-gray-500 font-medium">Venue</p>
                <p class="font-semibold text-gray-900 mt-0.5">{{ selectedEntry.room?.name || "TBD" }} ({{ selectedEntry.room?.code }})</p>
              </div>
              <div class="bg-gray-50 rounded-lg p-3">
                <p class="text-xs text-gray-500 font-medium">Lecturer</p>
                <p class="font-semibold text-gray-900 mt-0.5">{{ selectedEntry.lecturer?.name || "—" }}</p>
              </div>
              <div class="bg-gray-50 rounded-lg p-3">
                <p class="text-xs text-gray-500 font-medium">Program</p>
                <p class="font-semibold text-gray-900 mt-0.5">{{ selectedEntry.course?.program?.name || selectedEntry.course?.department?.name || "—" }}</p>
              </div>
              <div v-if="selectedEntry.student_group" class="bg-gray-50 rounded-lg p-3">
                <p class="text-xs text-gray-500 font-medium">Student Group</p>
                <p class="font-semibold text-gray-900 mt-0.5">{{ selectedEntry.student_group.name }}</p>
              </div>
              <div class="bg-gray-50 rounded-lg p-3">
                <p class="text-xs text-gray-500 font-medium">Room Capacity</p>
                <p class="font-semibold text-gray-900 mt-0.5">{{ selectedEntry.room?.capacity || "—" }} seats</p>
              </div>
            </div>

            <!-- Reminder section (lecturers and admins only) -->
            <div v-if="auth.user?.role?.name === 'lecturer' || auth.user?.role?.name === 'admin' || auth.user?.role?.name === 'timetable_officer'" class="border-t border-gray-200 pt-4">
              <h3 class="font-semibold text-gray-900 mb-3">Send Class Reminder</h3>
              <div class="space-y-3">
                <div>
                  <label class="label text-xs">Notification Channel</label>
                  <select v-model="reminderForm.channel" class="input text-sm">
                    <option value="email">Email</option>
                    <option value="sms">SMS</option>
                    <option value="both">Email + SMS</option>
                  </select>
                </div>
                <div>
                  <label class="label text-xs">Schedule for (optional — leave blank to send now)</label>
                  <input v-model="reminderForm.scheduled_at" type="datetime-local" class="input text-sm" />
                </div>
              </div>
              <button
                class="btn-primary w-full mt-3"
                :disabled="sendingReminder"
                @click="sendReminder"
              >
                {{ sendingReminder ? "Sending…" : "Send Reminder" }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── Move Confirmation Modal ──────────────────────────────────────────── -->
    <Teleport to="body">
      <Transition name="modal-fade">
        <div v-if="moveModal.visible"
          class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          @click.self="!moveModal.moving && (moveModal.visible = false)"
        >
          <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden">

            <!-- Header -->
            <div :class="['p-5 text-white', moveModal.conflicts.length ? 'bg-gradient-to-r from-orange-500 to-red-500' : 'bg-gradient-to-r from-blue-600 to-indigo-600']">
              <div class="flex items-start justify-between gap-2">
                <div>
                  <p class="text-xs opacity-80 uppercase tracking-widest font-semibold mb-1">
                    {{ moveModal.conflicts.length ? '⚠ Conflicts Detected' : '✦ Move Session' }}
                  </p>
                  <h2 class="text-lg font-bold leading-tight">
                    {{ moveModal.entry?.course?.code }} — {{ moveModal.entry?.course?.name }}
                  </h2>
                </div>
                <button @click="moveModal.visible = false" :disabled="moveModal.moving"
                  class="text-white/70 hover:text-white text-2xl leading-none mt-0.5">✕</button>
              </div>
            </div>

            <div class="p-5 space-y-4">

              <!-- From → To slot diagram -->
              <div class="flex items-center gap-3 bg-gray-50 rounded-xl p-3 text-sm">
                <div class="flex-1 text-center">
                  <p class="text-[10px] text-gray-400 uppercase tracking-wide font-semibold mb-1">From</p>
                  <p class="font-bold text-gray-800">{{ moveModal.fromSlot?.day }}</p>
                  <p class="text-gray-500 text-xs">{{ moveModal.fromSlot?.start_time }} – {{ moveModal.fromSlot?.end_time }}</p>
                </div>
                <div class="text-gray-300 text-xl font-light">→</div>
                <div class="flex-1 text-center">
                  <p class="text-[10px] text-gray-400 uppercase tracking-wide font-semibold mb-1">To</p>
                  <p class="font-bold text-gray-800">{{ moveModal.targetSlot?.day }}</p>
                  <p class="text-gray-500 text-xs">{{ moveModal.targetSlot?.start_time }} – {{ moveModal.targetSlot?.end_time }}</p>
                </div>
              </div>

              <!-- Session info chips -->
              <div class="grid grid-cols-3 gap-2 text-xs">
                <div class="bg-gray-50 rounded-lg p-2 text-center">
                  <p class="text-gray-400 mb-0.5">Lecturer</p>
                  <p class="font-semibold text-gray-800 truncate">{{ moveModal.entry?.lecturer?.name?.split(" ")[0] || "—" }}</p>
                </div>
                <div class="bg-gray-50 rounded-lg p-2 text-center">
                  <p class="text-gray-400 mb-0.5">Room</p>
                  <p class="font-semibold text-gray-800">{{ moveModal.entry?.room?.code || "TBD" }}</p>
                </div>
                <div class="bg-gray-50 rounded-lg p-2 text-center">
                  <p class="text-gray-400 mb-0.5">Group</p>
                  <p class="font-semibold text-gray-800 truncate">{{ moveModal.entry?.student_group?.code || "—" }}</p>
                </div>
              </div>

              <!-- ── No conflicts ── -->
              <div v-if="!moveModal.conflicts.length"
                class="flex items-center gap-3 bg-green-50 border border-green-200 rounded-xl p-3 text-sm text-green-800">
                <svg class="w-5 h-5 text-green-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <span><strong>No conflicts</strong> — this slot is free for this lecturer, room, and student group.</span>
              </div>

              <!-- ── Conflicts list ── -->
              <div v-else class="space-y-2">
                <p class="text-xs font-semibold text-red-600 uppercase tracking-wide">
                  {{ moveModal.conflicts.length }} conflict{{ moveModal.conflicts.length > 1 ? 's' : '' }} at {{ moveModal.targetSlot?.day }} {{ moveModal.targetSlot?.start_time }}:
                </p>
                <div v-for="(c, i) in moveModal.conflicts" :key="i"
                  class="flex items-start gap-3 bg-red-50 border border-red-200 rounded-xl p-3 text-sm">
                  <span class="text-xl flex-shrink-0 mt-0.5">{{ c.icon }}</span>
                  <div class="flex-1 min-w-0">
                    <p class="font-semibold text-red-800 text-xs uppercase tracking-wide mb-1">{{ c.label }}</p>
                    <p class="text-red-700 text-sm">{{ c.detail }}</p>
                    <div class="mt-1.5 bg-white rounded-lg border border-red-100 px-2 py-1.5 text-xs text-gray-700 flex flex-wrap gap-x-3 gap-y-0.5">
                      <span class="font-semibold text-blue-700">{{ c.conflicting.course?.code }}</span>
                      <span>{{ c.conflicting.course?.name }}</span>
                      <span v-if="c.conflicting.lecturer?.name" class="text-gray-500">· {{ c.conflicting.lecturer.name }}</span>
                      <span v-if="c.conflicting.room?.code" class="text-gray-500">· {{ c.conflicting.room.code }}</span>
                    </div>
                  </div>
                </div>

                <div class="bg-amber-50 border border-amber-200 rounded-xl p-3 text-xs text-amber-800 flex items-start gap-2">
                  <svg class="w-4 h-4 flex-shrink-0 mt-0.5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
                  </svg>
                  <span>You can still force the placement, but these conflicts will remain and may affect the timetable's validity. Consider resolving them first.</span>
                </div>
              </div>
            </div>

            <!-- Footer -->
            <div class="px-5 pb-5 flex items-center justify-end gap-3">
              <button class="btn-secondary text-sm" :disabled="moveModal.moving"
                @click="moveModal.visible = false">
                Cancel
              </button>
              <button
                :class="['text-sm font-medium px-4 py-2 rounded-lg transition-colors text-white',
                  moveModal.conflicts.length
                    ? 'bg-orange-500 hover:bg-orange-600 disabled:bg-orange-300'
                    : 'bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300']"
                :disabled="moveModal.moving"
                @click="confirmMove"
              >
                <span v-if="moveModal.moving" class="flex items-center gap-2">
                  <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
                  </svg>
                  Moving…
                </span>
                <span v-else-if="moveModal.conflicts.length">⚠ Place Anyway</span>
                <span v-else>✓ Confirm Placement</span>
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.modal-fade-enter-active, .modal-fade-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; transform: scale(0.97); }
</style>
