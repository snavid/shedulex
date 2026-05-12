<script setup>
import { computed, ref, watch } from "vue"
import { useRoute } from "vue-router"
import { useToast } from "vue-toastification"

import { documentApi, getErrorMessage, timetableApi } from "@/api/client"
import { useTimetableStore } from "@/stores/timetable"
import { useAuthStore } from "@/stores/auth"

const route = useRoute()
const store = useTimetableStore()
const auth = useAuthStore()
const toast = useToast()

const loading = ref(true)
const conflictsLoading = ref(false)
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

const exportOps = ref({
  pdf: false,
  excel: false,
  csv: false,
  bundle: false,
  share: false,
})

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
const entryColors = [
  "bg-blue-600",
  "bg-purple-600",
  "bg-green-600",
  "bg-orange-500",
  "bg-pink-600",
  "bg-teal-600",
  "bg-red-600",
  "bg-indigo-600",
]
const colorCache = {}

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

const timetableGrid = computed(() => {
  if (!store.currentTimetable?.entries) return {}
  const grid = {}
  for (const entry of store.currentTimetable.entries) {
    const slot = entry.time_slot
    if (!slot) continue
    const key = `${slot.day}__${slot.start_time}`
    grid[key] = entry
  }
  return grid
})

const timeSlots = computed(() => {
  if (!store.currentTimetable?.entries) return []
  const seen = new Set()
  const slots = []
  for (const entry of store.currentTimetable.entries) {
    const slot = entry.time_slot
    if (!slot) continue
    const key = `${slot.start_time}__${slot.slot_index}`
    if (!seen.has(key)) {
      seen.add(key)
      slots.push(slot)
    }
  }
  return slots.sort((a, b) => (a.slot_index || 0) - (b.slot_index || 0))
})

function getEntryColor(courseId) {
  if (!colorCache[courseId]) {
    colorCache[courseId] = entryColors[Object.keys(colorCache).length % entryColors.length]
  }
  return colorCache[courseId]
}

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
    let response
    let fallbackFilename

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
    exportStatus.value = "Failed to generate secure share link."
  } finally {
    setExportLoading("share", false)
  }
}

async function copyShareLink() {
  if (!shareLink.value) return
  try {
    await navigator.clipboard.writeText(shareLink.value)
    toast.success("Share link copied.")
    exportStatus.value = "Share link copied to clipboard."
  } catch {
    toast.error("Failed to copy share link.")
    exportStatus.value = "Failed to copy share link."
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

async function loadTimetablePage(id) {
  if (!id) return
  loading.value = true
  pageError.value = ""
  try {
    await store.fetchTimetable(id)
    await Promise.all([loadExportPreview(), loadExportAnalytics(), loadVersions()])
  } catch (e) {
    pageError.value = getErrorMessage(e, "Failed to load timetable details.")
  } finally {
    loading.value = false
  }
}

watch(
  () => route.params.id,
  (id) => loadTimetablePage(id),
  { immediate: true },
)
</script>

<template>
  <div class="space-y-6">
    <div v-if="loading" class="animate-pulse space-y-4">
      <div class="h-8 bg-gray-200 rounded w-1/3"></div>
      <div class="card h-96 bg-gray-200 rounded"></div>
    </div>

    <div v-else-if="pageError" class="card border-red-200 bg-red-50 text-red-700 text-sm">
      {{ pageError }}
    </div>

    <template v-else-if="store.currentTimetable">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 class="text-2xl font-bold text-gray-900">{{ store.currentTimetable.name }}</h1>
          <p class="text-gray-500 text-sm">
            {{ store.currentTimetable.department?.name }} |
            Semester {{ store.currentTimetable.semester }} |
            {{ store.currentTimetable.academic_year }}
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <button
            @click="detectConflicts"
            :disabled="conflictsLoading"
            class="btn-secondary flex items-center gap-2"
            aria-label="Check timetable conflicts"
          >
            {{ conflictsLoading ? "Checking..." : "Check Conflicts" }}
          </button>
          <RouterLink to="/ai-assistant" class="btn-secondary flex items-center gap-2" aria-label="Open AI adjustment assistant">
            AI Adjust
          </RouterLink>
        </div>
      </div>

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
          <span>Recommended format: <strong class="uppercase">{{ recommendedFormat }}</strong></span>
          <span>Complexity: <strong class="capitalize">{{ complexityTier }}</strong></span>
          <span v-if="exportPreview?.summary?.peak_day">Peak day: <strong>{{ exportPreview.summary.peak_day }}</strong></span>
        </div>

        <div class="grid md:grid-cols-4 gap-3">
          <button class="btn-secondary" :disabled="exportOps.pdf" @click="runExport('pdf')" aria-label="Export timetable as PDF">
            {{ exportOps.pdf ? "Exporting PDF..." : "PDF" }}
          </button>
          <button class="btn-secondary" :disabled="exportOps.excel" @click="runExport('excel')" aria-label="Export timetable as Excel">
            {{ exportOps.excel ? "Exporting Excel..." : "Excel" }}
          </button>
          <button class="btn-secondary" :disabled="exportOps.csv" @click="runExport('csv')" aria-label="Export timetable as CSV">
            {{ exportOps.csv ? "Exporting CSV..." : "CSV" }}
          </button>
          <button class="btn-primary" :disabled="exportOps.bundle" @click="runExport('bundle')" aria-label="Export timetable bundle as ZIP">
            {{ exportOps.bundle ? "Packaging..." : "Export Bundle (.zip)" }}
          </button>
        </div>

        <div class="grid md:grid-cols-2 gap-4">
          <div class="p-4 border border-gray-200 rounded-lg bg-gray-50 space-y-3">
            <h3 class="font-semibold text-sm text-gray-900">Secure Share Link</h3>
            <div class="grid grid-cols-2 gap-2">
              <select v-model="shareFormat" class="input" aria-label="Share export format">
                <option value="bundle">Bundle</option>
                <option value="pdf">PDF</option>
                <option value="excel">Excel</option>
                <option value="csv">CSV</option>
              </select>
              <input
                v-model.number="shareExpiresHours"
                type="number"
                min="1"
                max="168"
                class="input"
                aria-label="Share link expiry in hours"
                placeholder="Expiry (hours)"
              />
            </div>
            <button class="btn-secondary w-full" :disabled="exportOps.share" @click="createSecureShareLink">
              {{ exportOps.share ? "Generating..." : "Generate Share Link" }}
            </button>
            <div v-if="shareLink" class="space-y-2">
              <input :value="shareLink" readonly class="input text-xs" aria-label="Generated share link" />
              <button class="btn-primary w-full" @click="copyShareLink">Copy Link</button>
            </div>
          </div>

          <div class="p-4 border border-gray-200 rounded-lg bg-gray-50 space-y-3">
            <h3 class="font-semibold text-sm text-gray-900">Export Insights</h3>
            <div class="grid grid-cols-2 gap-2 text-sm">
              <div class="p-2 bg-white rounded border">PDF exports: <strong>{{ exportCountsByFormat.pdf }}</strong></div>
              <div class="p-2 bg-white rounded border">Excel exports: <strong>{{ exportCountsByFormat.excel }}</strong></div>
              <div class="p-2 bg-white rounded border">CSV exports: <strong>{{ exportCountsByFormat.csv }}</strong></div>
              <div class="p-2 bg-white rounded border">Bundle exports: <strong>{{ exportCountsByFormat.bundle }}</strong></div>
            </div>
            <p v-if="exportPreviewLoading" class="text-xs text-gray-500">Loading recommendations...</p>
            <ul v-else class="text-xs text-gray-600 list-disc pl-4 space-y-1">
              <li v-for="tip in exportPreview?.recommendations || []" :key="tip">{{ tip }}</li>
            </ul>
          </div>
        </div>
      </div>

      <div class="card space-y-3">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold text-gray-900">Version snapshots</h2>
          <span v-if="versionsLoading" class="text-xs text-gray-500">Loading…</span>
        </div>
        <p class="text-xs text-gray-500">
          Snapshots are saved automatically before and after AI adjustments. Restore replaces current slots with the snapshot (admins and timetable officers).
        </p>
        <p v-if="!versions.length && !versionsLoading" class="text-sm text-gray-500">No snapshots yet.</p>
        <ul v-else class="divide-y divide-gray-100 border border-gray-100 rounded-lg overflow-hidden">
          <li
            v-for="v in versions"
            :key="v.id"
            class="flex flex-wrap items-center justify-between gap-2 px-3 py-3 bg-white"
          >
            <div class="min-w-0">
              <p class="text-sm font-medium text-gray-900 truncate">{{ v.notes || "Snapshot" }}</p>
              <p class="text-xs text-gray-500">
                {{ new Date(v.created_at).toLocaleString() }}
                · version {{ v.version }}
                · {{ v.entry_count }} entries
              </p>
            </div>
            <button
              v-if="auth.isTimetableOfficer"
              type="button"
              class="btn-secondary text-xs shrink-0"
              :disabled="restoringSnapshotId === v.id"
              @click="restoreSnapshot(v.id)"
            >
              {{ restoringSnapshotId === v.id ? "Restoring…" : "Restore" }}
            </button>
          </li>
        </ul>
      </div>

      <div v-if="store.conflicts.length" class="card border-red-200 bg-red-50">
        <h3 class="font-semibold text-red-900 mb-3">{{ store.conflicts.length }} Conflict(s) Detected</h3>
        <ul class="space-y-2">
          <li v-for="(c, i) in store.conflicts" :key="i" class="text-sm text-red-700 bg-white rounded-lg p-2 border border-red-200">
            <strong>{{ c.type?.replace('_', ' ').toUpperCase() }}:</strong> {{ c.message }}
          </li>
        </ul>
        <RouterLink to="/ai-assistant" class="mt-3 inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700 font-medium">
          Ask AI to resolve conflicts
        </RouterLink>
      </div>

      <div class="card overflow-hidden p-0">
        <div class="p-4 border-b border-gray-200">
          <h2 class="font-semibold text-gray-900">Weekly Schedule Grid</h2>
          <p class="text-xs text-gray-500 mt-1">Drag-and-drop adjustments are supported from the AI adjustment workflow.</p>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full border-collapse min-w-[700px]">
            <thead>
              <tr>
                <th class="bg-gray-50 border border-gray-200 p-3 text-left text-xs font-semibold text-gray-600 w-28">Time</th>
                <th v-for="day in DAYS" :key="day" class="bg-gray-50 border border-gray-200 p-3 text-center text-xs font-semibold text-gray-600">
                  {{ day }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="slot in timeSlots" :key="slot.id" :class="slot.is_break ? 'bg-yellow-50' : ''">
                <td class="border border-gray-200 p-2 text-xs font-medium text-gray-600 whitespace-nowrap">
                  {{ slot.start_time }} - {{ slot.end_time }}
                  <span v-if="slot.is_break" class="block text-yellow-600 font-semibold">BREAK</span>
                </td>
                <td v-for="day in DAYS" :key="day" class="timetable-cell">
                  <div
                    v-if="timetableGrid[`${day}__${slot.start_time}`]"
                    :class="['timetable-entry', getEntryColor(timetableGrid[`${day}__${slot.start_time}`]?.course?.id)]"
                  >
                    <p class="font-bold truncate">{{ timetableGrid[`${day}__${slot.start_time}`]?.course?.code }}</p>
                    <p class="truncate opacity-90">{{ timetableGrid[`${day}__${slot.start_time}`]?.course?.name }}</p>
                    <p class="opacity-75 truncate">Room {{ timetableGrid[`${day}__${slot.start_time}`]?.room?.code }}</p>
                    <p class="opacity-75 truncate">Lecturer {{ timetableGrid[`${day}__${slot.start_time}`]?.lecturer?.name?.split(" ")[0] }}</p>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
