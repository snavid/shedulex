<script setup>
import { computed, onMounted, ref } from "vue"
import { useToast } from "vue-toastification"
import { lecturerApi, requestsApi, getErrorMessage } from "@/api/client"

const toast = useToast()

const activeTab = ref("lessons") // "lessons" | "department" | "requests"

const loadingLessons = ref(true)
const myEntries = ref([])

const myLecturer = ref(null)
const loadingDept = ref(false)
const deptEntries = ref([])
const deptLoaded = ref(false)

const loadingRequests = ref(true)
const myRequests = ref([])
const submitting = ref(false)
const requestForm = ref({ category: "schedule_change", message: "" })

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
const CATEGORIES = [
  { value: "schedule_change", label: "Schedule Change" },
  { value: "substitution_leave", label: "Substitution / Leave" },
  { value: "room_issue", label: "Room Issue" },
  { value: "other", label: "Other" },
]
const STATUS_LABELS = {
  pending_hod: "Awaiting HOD",
  pending_admin: "Awaiting Admin",
  approved: "Approved",
  rejected: "Rejected",
}
const STATUS_CLASSES = {
  pending_hod: "bg-amber-100 text-amber-700",
  pending_admin: "bg-blue-100 text-blue-700",
  approved: "bg-green-100 text-green-700",
  rejected: "bg-red-100 text-red-700",
}

function groupByDay(entries) {
  const map = {}
  for (const day of DAYS) map[day] = []
  for (const entry of entries) {
    const day = entry.time_slot?.day
    if (day && map[day]) map[day].push(entry)
  }
  for (const day of DAYS) {
    map[day].sort((a, b) => (a.time_slot?.start_time || "").localeCompare(b.time_slot?.start_time || ""))
  }
  return map
}

const groupedLessons = computed(() => groupByDay(myEntries.value))
const activeLessonDays = computed(() => DAYS.filter((d) => groupedLessons.value[d]?.length))

const groupedDept = computed(() => groupByDay(deptEntries.value))
const activeDeptDays = computed(() => DAYS.filter((d) => groupedDept.value[d]?.length))

async function loadLessons() {
  loadingLessons.value = true
  try {
    const { data } = await lecturerApi.myLessons()
    myEntries.value = data.data || []
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load your lessons."))
  } finally {
    loadingLessons.value = false
  }
}

async function loadDepartmentTimetable() {
  if (deptLoaded.value) return
  loadingDept.value = true
  try {
    if (!myLecturer.value) {
      const { data } = await lecturerApi.me()
      myLecturer.value = data.data
    }
    const deptId = myLecturer.value?.department?.id
    if (!deptId) {
      toast.error("No department found on your lecturer profile.")
      return
    }
    const { data: ttRes } = await lecturerApi.departmentTimetables(deptId)
    const active = (ttRes.data || [])[0]
    if (!active) {
      deptEntries.value = []
      deptLoaded.value = true
      return
    }
    const { data: entriesRes } = await lecturerApi.entriesForTimetable(active.id)
    deptEntries.value = entriesRes.data || []
    deptLoaded.value = true
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load department timetable."))
  } finally {
    loadingDept.value = false
  }
}

async function loadRequests() {
  loadingRequests.value = true
  try {
    const { data } = await requestsApi.list()
    myRequests.value = data.data || []
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load your requests."))
  } finally {
    loadingRequests.value = false
  }
}

async function submitRequest() {
  if (!requestForm.value.message.trim()) {
    toast.error("Please describe your request.")
    return
  }
  submitting.value = true
  try {
    await requestsApi.create({
      category: requestForm.value.category,
      message: requestForm.value.message.trim(),
    })
    toast.success("Request submitted to your department HOD.")
    requestForm.value.message = ""
    await loadRequests()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to submit request."))
  } finally {
    submitting.value = false
  }
}

function selectTab(tab) {
  activeTab.value = tab
  if (tab === "department") loadDepartmentTimetable()
}

onMounted(() => {
  loadLessons()
  loadRequests()
})
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">My Portal</h1>
      <p class="text-sm text-gray-500 mt-1">Your lessons, department timetable, and requests to admin.</p>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 p-1 bg-gray-100 rounded-xl w-fit">
      <button
        v-for="t in [{ id: 'lessons', label: 'My Lessons' }, { id: 'department', label: 'Department Timetable' }, { id: 'requests', label: 'My Requests' }]"
        :key="t.id"
        @click="selectTab(t.id)"
        :class="activeTab === t.id ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
        class="px-4 py-2 rounded-lg text-sm font-semibold transition-all"
      >
        {{ t.label }}
      </button>
    </div>

    <!-- My Lessons -->
    <div v-if="activeTab === 'lessons'" class="space-y-4">
      <div v-if="loadingLessons" class="card animate-pulse space-y-3">
        <div v-for="i in 4" :key="i" class="h-14 bg-gray-100 rounded-lg"></div>
      </div>
      <div v-else-if="!myEntries.length" class="card text-center py-14">
        <h3 class="font-semibold text-gray-900 mb-1">No sessions scheduled</h3>
        <p class="text-sm text-gray-500">You have no active timetable sessions yet.</p>
      </div>
      <div v-else class="space-y-4">
        <div v-for="day in activeLessonDays" :key="day" class="card">
          <h3 class="font-semibold text-gray-900 mb-3">{{ day }}</h3>
          <div class="space-y-2">
            <div
              v-for="e in groupedLessons[day]"
              :key="e.id"
              class="flex items-center gap-3 p-3 rounded-xl bg-gray-50"
            >
              <div class="text-xs font-semibold text-gray-500 w-24 flex-shrink-0">
                {{ e.time_slot?.start_time }}–{{ e.time_slot?.end_time }}
              </div>
              <div class="min-w-0 flex-1">
                <p class="text-sm font-medium text-gray-900 truncate">{{ e.course?.name }}</p>
                <p class="text-xs text-gray-500">{{ e.room?.name || "No room" }} · {{ e.student_group?.name || "" }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Department Timetable -->
    <div v-else-if="activeTab === 'department'" class="space-y-4">
      <div v-if="loadingDept" class="card animate-pulse space-y-3">
        <div v-for="i in 4" :key="i" class="h-14 bg-gray-100 rounded-lg"></div>
      </div>
      <div v-else-if="!deptEntries.length" class="card text-center py-14">
        <h3 class="font-semibold text-gray-900 mb-1">No active department timetable</h3>
        <p class="text-sm text-gray-500">Nothing has been published for your department yet.</p>
      </div>
      <div v-else class="space-y-4">
        <p class="text-xs text-gray-400">Read-only — showing every session in your department's active timetable.</p>
        <div v-for="day in activeDeptDays" :key="day" class="card">
          <h3 class="font-semibold text-gray-900 mb-3">{{ day }}</h3>
          <div class="space-y-2">
            <div
              v-for="e in groupedDept[day]"
              :key="e.id"
              class="flex items-center gap-3 p-3 rounded-xl bg-gray-50"
            >
              <div class="text-xs font-semibold text-gray-500 w-24 flex-shrink-0">
                {{ e.time_slot?.start_time }}–{{ e.time_slot?.end_time }}
              </div>
              <div class="min-w-0 flex-1">
                <p class="text-sm font-medium text-gray-900 truncate">{{ e.course?.name }}</p>
                <p class="text-xs text-gray-500">{{ e.lecturer?.name || "?" }} · {{ e.room?.name || "No room" }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- My Requests -->
    <div v-else class="space-y-4">
      <div class="card space-y-4">
        <h2 class="font-semibold text-gray-900">New Request</h2>
        <div>
          <label class="label">Category</label>
          <select v-model="requestForm.category" class="input">
            <option v-for="c in CATEGORIES" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
        </div>
        <div>
          <label class="label">Message</label>
          <textarea v-model="requestForm.message" class="input" rows="3" placeholder="Describe your request…" />
        </div>
        <button class="btn-primary" :disabled="submitting" @click="submitRequest">
          {{ submitting ? "Submitting…" : "Submit to HOD" }}
        </button>
      </div>

      <div v-if="loadingRequests" class="card animate-pulse space-y-3">
        <div v-for="i in 3" :key="i" class="h-14 bg-gray-100 rounded-lg"></div>
      </div>
      <div v-else-if="!myRequests.length" class="card text-center py-10">
        <p class="text-sm text-gray-500">You haven't submitted any requests yet.</p>
      </div>
      <div v-else class="card divide-y divide-gray-100">
        <div v-for="r in myRequests" :key="r.id" class="py-3.5 space-y-1.5">
          <div class="flex items-center justify-between gap-2">
            <span class="text-sm font-semibold text-gray-900">
              {{ CATEGORIES.find(c => c.value === r.category)?.label || r.category }}
            </span>
            <span :class="STATUS_CLASSES[r.status]" class="text-xs font-semibold px-2 py-0.5 rounded-full">
              {{ STATUS_LABELS[r.status] || r.status }}
            </span>
          </div>
          <p class="text-sm text-gray-600">{{ r.message }}</p>
          <p v-if="r.hod_note" class="text-xs text-gray-500">HOD note: {{ r.hod_note }}</p>
          <p v-if="r.admin_note" class="text-xs text-gray-500">Admin note: {{ r.admin_note }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
