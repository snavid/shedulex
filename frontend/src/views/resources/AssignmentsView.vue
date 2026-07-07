<script setup>
/**
 * Drag-and-drop lecturer-course assignment board.
 *
 * Left panel  — each lecturer has a card; their assigned tasks appear below.
 * Right panel — "Unassigned" pool: tasks with no lecturer.
 *
 * Chip colour guide:
 *   Blue   – consolidated multi-group chip (all groups → same lecturer)
 *   Teal   – per-group chip in split mode (user clicked "Split"; same lecturer still)
 *   Purple – per-group chip with actual conflict (different lecturers per group)
 *   Amber  – unassigned
 */
import { onMounted, ref, computed, watch } from "vue"
import { resourcesApi, getErrorMessage } from "@/api/client"
import { useAuthStore } from "@/stores/auth"
import { useAcademicYearStore } from "@/stores/academicYear"
import { useToast } from "vue-toastification"

const auth      = useAuthStore()
const yearStore = useAcademicYearStore()
const toast     = useToast()

const loading     = ref(true)
const saving      = ref(null)      // task.key currently being saved
const lecturers   = ref([])
const courses     = ref([])
const departments = ref([])
const search      = ref("")
const deptFilter  = ref("")

// Course IDs the user has manually expanded into per-group chips.
// Cleared when the semester changes.
const splitCourses = ref(new Set())

const canManage = computed(() =>
  ["admin", "timetable_officer", "hod"].includes(auth.user?.role?.name)
)

// ── Data loading ──────────────────────────────────────────────────────────────
async function loadData(silent = false) {
  if (!silent) loading.value = true
  try {
    const [lecRes, crsRes, deptRes] = await Promise.all([
      resourcesApi.lecturers(),
      resourcesApi.courses({ semester: yearStore.currentSemester }),
      resourcesApi.departments(),
    ])
    lecturers.value   = lecRes.data.data || []
    courses.value     = crsRes.data.data || []
    departments.value = deptRes.data.data || []
  } finally {
    if (!silent) loading.value = false
  }
}

// Department filter scopes both sides of the board: which lecturer cards
// appear, and which courses/tasks are eligible to appear on either side.
const filteredLecturers = computed(() =>
  deptFilter.value
    ? lecturers.value.filter(l => (l.department_id || l.department?.id) === deptFilter.value)
    : lecturers.value
)

const filteredCourses = computed(() =>
  deptFilter.value
    ? courses.value.filter(c => c.department?.id === deptFilter.value)
    : courses.value
)

watch(() => yearStore.currentSemester, () => {
  splitCourses.value = new Set()
  loadData()
})

// ── Split / merge ─────────────────────────────────────────────────────────────
function splitCourse(courseId) {
  const next = new Set(splitCourses.value)
  next.add(courseId)
  splitCourses.value = next
}

function mergeCourse(courseId) {
  const next = new Set(splitCourses.value)
  next.delete(courseId)
  splitCourses.value = next
}

// ── Task model ────────────────────────────────────────────────────────────────
// task shape:
//   key               – unique string for v-key / saving ref
//   course_id         – course UUID
//   course            – full course object
//   group_id          – student_group UUID | null
//   group             – { id, code, name } | null
//   lecturer_id       – effective lecturer UUID | null
//   lecturer          – effective lecturer object | null
//   is_multi          – course has >1 group
//   has_override      – a per-group override row exists in DB
//   all_same          – all groups share the same effective lecturer (consolidated)
//   force_split       – user manually split a consolidated chip
//   groups            – all groups on the course (for badge / merge)
//   overridden_group_ids – group IDs with override rows to clean up on consolidated drag

function buildTasks(courseList, q, splitSet) {
  const list = []

  for (const course of courseList) {
    const groups  = course.student_groups  || []
    const glMap   = course.group_lecturers || {}
    const isMulti = groups.length > 1
    const before  = list.length   // for search-filter loop below

    if (isMulti) {
      // Resolve effective lecturer for every group.
      // Override key present (even null) → use it; absent → fall back to course default.
      const resolved = groups.map(group => {
        const hasOverride = Object.hasOwn(glMap, group.id)
        const ov          = glMap[group.id]
        return {
          group,
          hasOverride,
          lecturer_id: hasOverride ? (ov.lecturer_id ?? null) : (course.lecturer?.id ?? null),
          lecturer:    hasOverride ? (ov.lecturer   ?? null)  : (course.lecturer  ?? null),
        }
      })

      const firstLid  = resolved[0]?.lecturer_id ?? null
      const allSame   = resolved.every(r => r.lecturer_id === firstLid)
      const forceSplit = splitSet.has(course.id)

      if (allSame && !forceSplit) {
        // Single consolidated chip
        const overriddenIds = resolved.filter(r => r.hasOverride).map(r => r.group.id)
        list.push({
          key:                 course.id,
          course_id:           course.id,
          course,
          group_id:            null,
          group:               null,
          lecturer_id:         firstLid,
          lecturer:            resolved[0]?.lecturer ?? null,
          is_multi:            true,
          has_override:        overriddenIds.length > 0,
          all_same:            true,
          force_split:         false,
          groups,
          overridden_group_ids: overriddenIds,
        })
      } else {
        // Per-group chips (real conflict or user-split)
        for (const { group, hasOverride, lecturer_id, lecturer } of resolved) {
          list.push({
            key:                 `${course.id}::${group.id}`,
            course_id:           course.id,
            course,
            group_id:            group.id,
            group,
            lecturer_id,
            lecturer,
            is_multi:            true,
            has_override:        hasOverride,
            all_same:            false,
            force_split:         allSame && forceSplit,   // true = teal; false = purple
            groups,
            overridden_group_ids: [],
          })
        }
      }
    } else {
      list.push({
        key:                 course.id,
        course_id:           course.id,
        course,
        group_id:            groups[0]?.id ?? null,
        group:               groups[0]     ?? null,
        lecturer_id:         course.lecturer?.id ?? null,
        lecturer:            course.lecturer     ?? null,
        is_multi:            false,
        has_override:        false,
        all_same:            true,
        force_split:         false,
        groups:              [],
        overridden_group_ids: [],
      })
    }

    // Filter ALL chips pushed for this course (not just the last one).
    if (q && list.length > before) {
      for (let i = list.length - 1; i >= before; i--) {
        if (!matchQ(list[i].course, list[i].group, q)) list.splice(i, 1)
      }
    }
  }
  return list
}

function matchQ(course, group, q) {
  return course.code.toLowerCase().includes(q)
    || course.name.toLowerCase().includes(q)
    || (group?.code || "").toLowerCase().includes(q)
}

const tasks = computed(() =>
  buildTasks(filteredCourses.value, search.value.toLowerCase(), splitCourses.value)
)

function lecturerTasks(lecturerId) {
  return tasks.value.filter(t => t.lecturer_id === lecturerId)
}

const unassignedTasks = computed(() => tasks.value.filter(t => !t.lecturer_id))

// ── Drag state ────────────────────────────────────────────────────────────────
const dragging = ref(null)
const dragOver = ref(null)

function onDragStart(task) {
  if (!canManage.value) return
  dragging.value = task
}

function onDragOver(targetId) { dragOver.value = targetId }

function onDragLeave(event) {
  if (!event.currentTarget.contains(event.relatedTarget)) dragOver.value = null
}

async function onDrop(targetLecturerId) {
  dragOver.value = null
  if (!dragging.value || !canManage.value) return
  const task = dragging.value
  dragging.value = null

  const newId = targetLecturerId === "unassigned" ? null : targetLecturerId
  if ((task.lecturer_id ?? null) === (newId ?? null)) return

  saving.value = task.key
  try {
    if (task.is_multi && !task.all_same) {
      // Per-group mode (conflict or force-split) — set per-group override
      await resourcesApi.setGroupLecturer(task.course_id, task.group_id, newId)
    } else {
      // Consolidated or single/ungrouped — update course default + clean overrides
      await resourcesApi.updateCourse(task.course_id, { lecturer_id: newId })
      for (const gid of (task.overridden_group_ids || [])) {
        await resourcesApi.removeGroupLecturer(task.course_id, gid)
      }
    }
    await loadData(true)
    const lec = lecturers.value.find(l => l.id === newId)
    toast.success(newId ? `Assigned to ${lec?.name}` : "Moved to unassigned")
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to save assignment."))
    await loadData()
  } finally {
    saving.value = null
  }
}

// ── Chip colour helpers ───────────────────────────────────────────────────────
// Returns [wrapperClass, dotClass, textClass] based on task state.
function chipClasses(task) {
  if (task.is_multi && !task.all_same) {
    if (task.force_split) {
      // Teal: user-initiated split, same lecturer on all groups
      return {
        wrap: "bg-teal-50 border-teal-200 hover:bg-teal-100",
        dot:  "bg-teal-500",
        code: "text-teal-900",
        name: "text-teal-700",
        sub:  "text-teal-500",
      }
    }
    // Purple: actual conflict — different lecturers
    return {
      wrap: "bg-purple-50 border-purple-200 hover:bg-purple-100",
      dot:  "bg-purple-500",
      code: "text-purple-900",
      name: "text-purple-700",
      sub:  "text-purple-500",
    }
  }
  // Blue: consolidated or single/ungrouped
  return {
    wrap: "bg-blue-50 border-blue-200 hover:bg-blue-100",
    dot:  "bg-blue-500",
    code: "text-blue-900",
    name: "text-blue-700",
    sub:  "text-blue-400",
  }
}

function initials(name) {
  return (name || "?").split(" ").slice(0, 2).map(w => w[0]).join("").toUpperCase()
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6">

    <!-- Header -->
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Lecturer-Course Assignments</h1>
        <p class="text-sm text-gray-500 mt-1">
          Drag tasks onto a lecturer to assign them — showing
          <span class="font-semibold text-blue-600">Semester {{ yearStore.currentSemester }}</span> courses.
          Multi-group courses appear as one chip; click <strong>Split</strong> to assign groups to different lecturers.
        </p>
      </div>
      <div class="flex flex-wrap gap-3">
        <select v-model="deptFilter" class="input w-auto">
          <option value="">All departments</option>
          <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
        </select>
        <input v-model="search" class="input max-w-xs" placeholder="Search courses or groups…" />
      </div>
    </div>

    <!-- Legend -->
    <div class="flex flex-wrap gap-4 text-xs text-gray-500">
      <span class="flex items-center gap-1.5">
        <span class="w-3 h-3 rounded-full bg-blue-500"></span> Assigned (all groups together)
      </span>
      <span class="flex items-center gap-1.5">
        <span class="w-3 h-3 rounded-full bg-teal-500"></span> Split — assigning per group
      </span>
      <span class="flex items-center gap-1.5">
        <span class="w-3 h-3 rounded-full bg-purple-500"></span> Split — different lecturers per group
      </span>
      <span class="flex items-center gap-1.5">
        <span class="w-3 h-3 rounded-full bg-amber-400"></span> Unassigned
      </span>
      <span v-if="canManage" class="flex items-center gap-1.5 text-blue-600 font-medium">
        Drag tasks to assign
      </span>
      <span v-else class="text-gray-400 italic">View only</span>
    </div>

    <!-- Loading skeleton -->
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

        <div v-if="!filteredLecturers.length" class="card text-center py-10 text-gray-400">
          {{ deptFilter ? "No lecturers in this department." : "No lecturers added yet." }}
        </div>

        <div class="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
          <div
            v-for="lec in filteredLecturers"
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
              <div class="w-9 h-9 rounded-full bg-gradient-to-br from-purple-400 to-indigo-500
                          flex items-center justify-center text-white text-xs font-bold shrink-0 select-none">
                {{ initials(lec.name) }}
              </div>
              <div class="min-w-0">
                <p class="font-semibold text-gray-900 text-sm truncate">{{ lec.name }}</p>
                <p class="text-xs text-gray-400 truncate">{{ lec.specialization || lec.department?.name || "—" }}</p>
              </div>
              <span class="ml-auto text-xs font-bold text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded-full shrink-0">
                {{ lecturerTasks(lec.id).length }}
              </span>
            </div>

            <!-- Drop hint -->
            <div v-if="dragOver === lec.id && dragging && dragging.lecturer_id !== lec.id"
                 class="text-xs text-blue-600 font-medium text-center py-1 rounded-lg bg-blue-100 mb-2">
              Drop to assign
            </div>

            <!-- Task chips -->
            <div class="flex flex-col gap-1.5 flex-1">
              <div
                v-for="task in lecturerTasks(lec.id)"
                :key="task.key"
                :draggable="canManage"
                @dragstart="onDragStart(task)"
                class="flex items-start gap-2 px-2.5 py-1.5 rounded-lg border cursor-grab
                       active:cursor-grabbing select-none transition-colors"
                :class="[chipClasses(task).wrap, saving === task.key ? 'opacity-50 cursor-wait' : '']"
              >
                <span class="w-1.5 h-1.5 rounded-full shrink-0 mt-1.5"
                      :class="chipClasses(task).dot">
                </span>
                <div class="min-w-0 flex-1">
                  <p class="text-xs font-bold leading-tight" :class="chipClasses(task).code">
                    {{ task.course.code }}
                  </p>
                  <p class="text-[11px] truncate leading-tight" :class="chipClasses(task).name">
                    {{ task.course.name }}
                  </p>

                  <!-- Per-group chip (conflict or force-split): group code + Merge button -->
                  <p v-if="task.is_multi && !task.all_same"
                     class="text-[10px] font-semibold mt-0.5 flex items-center gap-1.5"
                     :class="chipClasses(task).sub">
                    {{ task.group?.code }}
                    <span v-if="!task.has_override && !task.force_split"
                          class="italic font-normal opacity-70">default</span>
                    <button v-if="task.force_split && canManage"
                            @click.stop="mergeCourse(task.course_id)"
                            class="underline leading-none hover:opacity-80">
                      Merge
                    </button>
                  </p>

                  <!-- Consolidated chip: "N groups" + Split button -->
                  <p v-else-if="task.is_multi && task.all_same"
                     class="text-[10px] mt-0.5 flex items-center gap-1.5"
                     :class="chipClasses(task).sub">
                    {{ task.groups.length }} groups
                    <button v-if="canManage"
                            @click.stop="splitCourse(task.course_id)"
                            class="underline leading-none hover:opacity-80 font-medium">
                      Split
                    </button>
                  </p>
                </div>
              </div>

              <p v-if="!lecturerTasks(lec.id).length" class="text-xs text-gray-300 italic self-center py-2">
                No tasks assigned
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Unassigned pool ──────────────────────────────────────────────── -->
      <div>
        <h2 class="font-semibold text-gray-700 text-sm uppercase tracking-wide mb-4">
          Unassigned
          <span class="text-amber-600 font-bold ml-1">({{ unassignedTasks.length }})</span>
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
          <p v-if="dragOver === 'unassigned'"
             class="text-xs text-amber-600 font-medium text-center py-1 rounded-lg bg-amber-100">
            Drop to unassign
          </p>

          <template v-if="unassignedTasks.length">
            <div
              v-for="task in unassignedTasks"
              :key="task.key"
              :draggable="canManage"
              @dragstart="onDragStart(task)"
              class="flex items-start gap-2 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200
                     cursor-grab active:cursor-grabbing select-none hover:bg-amber-100 transition-colors"
              :class="saving === task.key ? 'opacity-50 cursor-wait' : ''"
            >
              <span class="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0 mt-1.5"></span>
              <div class="min-w-0 flex-1">
                <p class="text-xs font-bold text-amber-900">{{ task.course.code }}</p>
                <p class="text-[11px] text-amber-700 truncate">{{ task.course.name }}</p>

                <!-- Per-group chip (force-split or conflict) -->
                <p v-if="task.is_multi && !task.all_same"
                   class="text-[10px] text-amber-500 font-semibold flex items-center gap-1.5">
                  {{ task.group?.code }}
                  <button v-if="task.force_split && canManage"
                          @click.stop="mergeCourse(task.course_id)"
                          class="text-amber-500 hover:text-amber-700 underline leading-none">
                    Merge
                  </button>
                </p>

                <!-- Consolidated chip -->
                <p v-else-if="task.is_multi && task.all_same"
                   class="text-[10px] text-amber-400 flex items-center gap-1.5">
                  {{ task.groups.length }} groups
                  <button v-if="canManage"
                          @click.stop="splitCourse(task.course_id)"
                          class="text-amber-500 hover:text-amber-700 underline leading-none font-medium">
                    Split
                  </button>
                </p>

                <!-- Single / ungrouped -->
                <p v-else class="text-[10px] text-amber-400">
                  Sem {{ task.course.semester }} · Yr {{ task.course.year_of_study }}
                </p>
              </div>
            </div>
          </template>

          <div v-else class="flex-1 flex flex-col items-center justify-center text-center py-8">
            <svg class="w-8 h-8 text-green-300 mb-2" fill="none" stroke="currentColor"
                 viewBox="0 0 24 24" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round"
                    d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p class="text-xs text-gray-400 font-medium">All tasks assigned!</p>
          </div>
        </div>

        <!-- Stats -->
        <div class="mt-4 p-3 rounded-xl bg-gray-50 border border-gray-100 text-xs text-gray-500 space-y-1">
          <div class="flex justify-between">
            <span>Total tasks</span>
            <span class="font-semibold text-gray-700">{{ tasks.length }}</span>
          </div>
          <div class="flex justify-between">
            <span>Assigned</span>
            <span class="font-semibold text-green-700">{{ tasks.length - unassignedTasks.length }}</span>
          </div>
          <div class="flex justify-between">
            <span>Unassigned</span>
            <span class="font-semibold text-amber-600">{{ unassignedTasks.length }}</span>
          </div>
          <div class="flex justify-between border-t border-gray-200 pt-1 mt-1">
            <span>Per-group overrides</span>
            <span class="font-semibold text-purple-600">
              {{ tasks.filter(t => t.has_override).length }}
            </span>
          </div>
        </div>

        <!-- Key -->
        <div class="mt-3 space-y-1 text-[11px] text-gray-400">
          <div class="flex items-center gap-1.5">
            <span class="w-2.5 h-2.5 rounded-full bg-blue-400"></span>
            All groups → same lecturer (click Split)
          </div>
          <div class="flex items-center gap-1.5">
            <span class="w-2.5 h-2.5 rounded-full bg-teal-400"></span>
            Per-group edit mode (click Merge to recombine)
          </div>
          <div class="flex items-center gap-1.5">
            <span class="w-2.5 h-2.5 rounded-full bg-purple-400"></span>
            Different lecturers per group
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
