<script setup>
/**
 * Drag-and-drop lecturer-course assignment board.
 *
 * Left panel  — each lecturer has a card; their assigned courses appear below.
 * Right panel — "Unassigned" pool: courses with no lecturer.
 *
 * Drag a course chip from anywhere → drop onto a lecturer card or the pool to
 * (re)assign or unassign it.  Changes are persisted immediately via PATCH /courses/<id>.
 */
import { onMounted, ref, computed, watch } from "vue"
import { resourcesApi } from "@/api/client"
import { useAuthStore } from "@/stores/auth"
import { useAcademicYearStore } from "@/stores/academicYear"
import { useToast } from "vue-toastification"

const auth      = useAuthStore()
const yearStore = useAcademicYearStore()
const toast     = useToast()

const loading = ref(true)
const saving  = ref(null)
const lecturers = ref([])
const courses   = ref([])
const search    = ref("")

const canManage = computed(() =>
  ["admin", "timetable_officer", "hod"].includes(auth.user?.role?.name)
)

async function loadData() {
  loading.value = true
  try {
    const [lecRes, crsRes] = await Promise.all([
      resourcesApi.lecturers(),
      resourcesApi.courses({ semester: yearStore.currentSemester }),
    ])
    lecturers.value = lecRes.data.data || []
    courses.value   = crsRes.data.data || []
  } finally {
    loading.value = false
  }
}

watch(() => yearStore.currentSemester, loadData)

// ── Drag state ────────────────────────────────────────────────────────────────
const dragging   = ref(null)   // { course_id, from_lecturer_id | null }
const dragOver   = ref(null)   // lecturer_id | "unassigned"

function onDragStart(course, fromLecturerId) {
  dragging.value = { course_id: course.id, from_lecturer_id: fromLecturerId ?? null }
}

function onDragOver(targetId) {
  dragOver.value = targetId
}

function onDragLeave(event) {
  if (!event.currentTarget.contains(event.relatedTarget)) {
    dragOver.value = null
  }
}

async function onDrop(targetLecturerId) {
  dragOver.value = null
  if (!dragging.value || !canManage.value) return
  const { course_id, from_lecturer_id } = dragging.value
  dragging.value = null

  const sameTarget = targetLecturerId === (from_lecturer_id ?? "unassigned")
  if (sameTarget) return

  const newLecturerId = targetLecturerId === "unassigned" ? null : targetLecturerId
  saving.value = course_id
  try {
    await resourcesApi.updateCourse(course_id, { lecturer_id: newLecturerId })
    // Optimistic update in local state
    const c = courses.value.find(x => x.id === course_id)
    if (c) {
      c.lecturer = newLecturerId
        ? (lecturers.value.find(l => l.id === newLecturerId) || null)
        : null
    }
    toast.success(
      newLecturerId
        ? `Assigned to ${lecturers.value.find(l => l.id === newLecturerId)?.name}`
        : "Moved to unassigned"
    )
  } catch (e) {
    toast.error(e?.response?.data?.message || "Failed to save assignment.")
    await loadData()
  } finally {
    saving.value = null
  }
}

// ── Derived data ──────────────────────────────────────────────────────────────
const filteredCourses = computed(() => {
  const q = search.value.toLowerCase()
  return q
    ? courses.value.filter(c =>
        c.name.toLowerCase().includes(q) ||
        c.code.toLowerCase().includes(q) ||
        (c.program?.code || "").toLowerCase().includes(q)
      )
    : courses.value
})

function lecturerCourses(lecturerId) {
  return filteredCourses.value.filter(c => c.lecturer?.id === lecturerId || (c.lecturer && typeof c.lecturer === "string" ? c.lecturer === lecturerId : false))
}

const unassignedCourses = computed(() =>
  filteredCourses.value.filter(c => !c.lecturer)
)

function initials(name) {
  return (name || "?").split(" ").slice(0, 2).map(w => w[0]).join("").toUpperCase()
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Lecturer-Course Assignments</h1>
        <p class="text-sm text-gray-500 mt-1">
          Drag courses onto a lecturer to assign them — showing
          <span class="font-semibold text-blue-600">Semester {{ yearStore.currentSemester }}</span> courses.
          Switch semester from the top bar.
        </p>
      </div>
      <input v-model="search" class="input max-w-xs" placeholder="Search courses…" />
    </div>

    <!-- Legend -->
    <div class="flex flex-wrap gap-4 text-xs text-gray-500">
      <span class="flex items-center gap-1.5">
        <span class="w-3 h-3 rounded-full bg-blue-500"></span> Assigned
      </span>
      <span class="flex items-center gap-1.5">
        <span class="w-3 h-3 rounded-full bg-amber-400"></span> Unassigned
      </span>
      <span v-if="canManage" class="flex items-center gap-1.5 text-blue-600 font-medium">
        Drag courses to reassign
      </span>
      <span v-else class="text-gray-400 italic">View only — you don't have write access</span>
    </div>

    <div v-if="loading" class="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="i in 6" :key="i" class="card animate-pulse space-y-3">
        <div class="h-4 bg-gray-200 rounded w-1/2"></div>
        <div class="h-3 bg-gray-200 rounded w-2/3"></div>
        <div class="h-7 bg-gray-100 rounded-lg"></div>
      </div>
    </div>

    <div v-else class="grid md:grid-cols-[1fr_300px] gap-6">
      <!-- ── Lecturer board ────────────────────────────────────────────────── -->
      <div class="space-y-4">
        <h2 class="font-semibold text-gray-700 text-sm uppercase tracking-wide">Lecturers</h2>

        <div v-if="!lecturers.length" class="card text-center py-10 text-gray-400">
          No lecturers added yet.
        </div>

        <div class="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
          <div
            v-for="lec in lecturers"
            :key="lec.id"
            class="card border-2 transition-all duration-150 min-h-[140px] flex flex-col"
            :class="dragOver === lec.id
              ? 'border-blue-400 bg-blue-50 shadow-md'
              : 'border-transparent hover:border-gray-200'"
            @dragover.prevent="onDragOver(lec.id)"
            @dragleave="onDragLeave"
            @drop.prevent="onDrop(lec.id)"
          >
            <!-- Lecturer header -->
            <div class="flex items-center gap-3 mb-3">
              <div class="w-9 h-9 rounded-full bg-gradient-to-br from-purple-400 to-indigo-500 flex items-center justify-center text-white text-xs font-bold shrink-0 select-none">
                {{ initials(lec.name) }}
              </div>
              <div class="min-w-0">
                <p class="font-semibold text-gray-900 text-sm truncate">{{ lec.name }}</p>
                <p class="text-xs text-gray-400 truncate">{{ lec.specialization || lec.department?.name || "—" }}</p>
              </div>
              <span class="ml-auto text-xs font-bold text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded-full shrink-0">
                {{ lecturerCourses(lec.id).length }}
              </span>
            </div>

            <!-- Drop hint -->
            <div v-if="dragOver === lec.id && dragging && dragging.from_lecturer_id !== lec.id"
              class="text-xs text-blue-600 font-medium text-center py-1 rounded-lg bg-blue-100 mb-2">
              Drop to assign
            </div>

            <!-- Course chips -->
            <div class="flex flex-col gap-1.5 flex-1">
              <div
                v-for="course in lecturerCourses(lec.id)"
                :key="course.id"
                :draggable="canManage"
                @dragstart="onDragStart(course, lec.id)"
                class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-blue-50 border border-blue-200 cursor-grab active:cursor-grabbing select-none hover:bg-blue-100 transition-colors"
                :class="saving === course.id ? 'opacity-50 cursor-wait' : ''"
              >
                <span class="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0"></span>
                <div class="min-w-0">
                  <p class="text-xs font-bold text-blue-900 leading-tight">{{ course.code }}</p>
                  <p class="text-[11px] text-blue-700 truncate leading-tight">{{ course.name }}</p>
                </div>
              </div>

              <p v-if="!lecturerCourses(lec.id).length" class="text-xs text-gray-300 italic self-center">
                No courses assigned
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Unassigned pool ───────────────────────────────────────────────── -->
      <div>
        <h2 class="font-semibold text-gray-700 text-sm uppercase tracking-wide mb-4">
          Unassigned
          <span class="text-amber-600 font-bold ml-1">({{ unassignedCourses.length }})</span>
        </h2>

        <div
          class="card border-2 min-h-[200px] flex flex-col gap-2 transition-all duration-150"
          :class="dragOver === 'unassigned'
            ? 'border-amber-400 bg-amber-50 shadow-md'
            : 'border-dashed border-gray-300 hover:border-amber-300'"
          @dragover.prevent="onDragOver('unassigned')"
          @dragleave="onDragLeave"
          @drop.prevent="onDrop('unassigned')"
        >
          <p v-if="dragOver === 'unassigned'" class="text-xs text-amber-600 font-medium text-center py-1 rounded-lg bg-amber-100">
            Drop to unassign
          </p>

          <template v-if="unassignedCourses.length">
            <div
              v-for="course in unassignedCourses"
              :key="course.id"
              :draggable="canManage"
              @dragstart="onDragStart(course, null)"
              class="flex items-start gap-2 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 cursor-grab active:cursor-grabbing select-none hover:bg-amber-100 transition-colors"
              :class="saving === course.id ? 'opacity-50 cursor-wait' : ''"
            >
              <span class="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0 mt-1"></span>
              <div class="min-w-0">
                <p class="text-xs font-bold text-amber-900">{{ course.code }}</p>
                <p class="text-[11px] text-amber-700 truncate">{{ course.name }}</p>
                <p v-if="course.program" class="text-[10px] text-amber-500">{{ course.program.code }}</p>
              </div>
            </div>
          </template>

          <div v-else class="flex-1 flex flex-col items-center justify-center text-center py-8">
            <svg class="w-8 h-8 text-green-300 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p class="text-xs text-gray-400 font-medium">All courses assigned!</p>
          </div>
        </div>

        <!-- Stats -->
        <div class="mt-4 p-3 rounded-xl bg-gray-50 border border-gray-100 text-xs text-gray-500 space-y-1">
          <div class="flex justify-between">
            <span>Total courses</span>
            <span class="font-semibold text-gray-700">{{ courses.length }}</span>
          </div>
          <div class="flex justify-between">
            <span>Assigned</span>
            <span class="font-semibold text-green-700">{{ courses.length - unassignedCourses.length }}</span>
          </div>
          <div class="flex justify-between">
            <span>Unassigned</span>
            <span class="font-semibold text-amber-600">{{ unassignedCourses.length }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
