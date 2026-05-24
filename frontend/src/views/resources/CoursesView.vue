<script setup>
import { onMounted, ref, computed } from "vue"
import { RouterLink } from "vue-router"
import { resourcesApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const saving = ref(false)
const courses = ref([])
const departments = ref([])
const lecturers = ref([])
const studentGroups = ref([])
const showForm = ref(false)
const editTarget = ref(null)
const deleteTarget = ref(null)
const search = ref("")
const deptFilter = ref("")

const blank = () => ({
  name: "", code: "", department_id: "", lecturer_id: "",
  semester: 1, year_of_study: 1, weekly_hours: 3,
  student_count: 40, requires_lab: false, priority: 1,
  student_group_ids: [],
})
const form = ref(blank())

// Groups filtered to match the selected semester + year (convenience filter)
const relevantGroups = computed(() => {
  if (!form.value.semester && !form.value.year_of_study) return studentGroups.value
  return studentGroups.value.filter(g =>
    (!form.value.semester       || g.semester        === form.value.semester) &&
    (!form.value.year_of_study  || g.year_of_study   === form.value.year_of_study)
  )
})

// "list" | "byGroup"
const viewMode = ref("list")

const filtered = computed(() => {
  let list = courses.value
  if (deptFilter.value) list = list.filter((c) => c.department_id === deptFilter.value)
  const q = search.value.toLowerCase()
  if (q) list = list.filter((c) => c.name.toLowerCase().includes(q) || c.code.toLowerCase().includes(q))
  return list
})

// Group view: each student group → its courses; plus an "unassigned" bucket
const groupedView = computed(() => {
  const buckets = []
  for (const group of studentGroups.value) {
    const groupCourses = filtered.value.filter(c =>
      (c.student_group_ids || []).includes(group.id)
    )
    buckets.push({ group, courses: groupCourses })
  }
  // courses not assigned to any group
  const unassigned = filtered.value.filter(c => !(c.student_group_ids || []).length)
  return { buckets, unassigned }
})

async function loadData() {
  loading.value = true
  try {
    const [courseRes, deptRes, lecRes, grpRes] = await Promise.all([
      resourcesApi.courses(),
      resourcesApi.departments(),
      resourcesApi.lecturers(),
      resourcesApi.studentGroups(),
    ])
    courses.value       = courseRes.data.data || []
    departments.value   = deptRes.data.data   || []
    lecturers.value     = lecRes.data.data     || []
    studentGroups.value = grpRes.data.data     || []
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load data."))
  } finally {
    loading.value = false
  }
}

function toggleGroup(gid) {
  const idx = form.value.student_group_ids.indexOf(gid)
  if (idx >= 0) form.value.student_group_ids.splice(idx, 1)
  else           form.value.student_group_ids.push(gid)
}

function openCreate() {
  editTarget.value = null
  form.value = blank()
  showForm.value = true
  deleteTarget.value = null
}

function openEdit(c) {
  editTarget.value = c
  form.value = {
    name: c.name, code: c.code,
    department_id: c.department_id || "",
    lecturer_id: c.lecturer?.id || "",
    semester: c.semester, year_of_study: c.year_of_study,
    weekly_hours: c.weekly_hours, student_count: c.student_count,
    requires_lab: c.requires_lab || false, priority: c.priority || 1,
    student_group_ids: (c.student_group_ids || []).slice(),
  }
  showForm.value = true
  deleteTarget.value = null
}

async function save() {
  if (!form.value.name || !form.value.code) {
    toast.error("Name and code are required.")
    return
  }
  saving.value = true
  try {
    const { student_group_ids, ...courseData } = form.value
    if (editTarget.value) {
      await resourcesApi.updateCourse(editTarget.value.id, courseData)
      await resourcesApi.setCourseGroups(editTarget.value.id, student_group_ids)
      toast.success("Course updated.")
    } else {
      const { data } = await resourcesApi.createCourse(courseData)
      const newId = data.data?.id
      if (newId && student_group_ids.length) {
        await resourcesApi.setCourseGroups(newId, student_group_ids)
      }
      toast.success("Course created.")
    }
    showForm.value = false
    editTarget.value = null
    await loadData()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to save course."))
  } finally {
    saving.value = false
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  try {
    await resourcesApi.deleteCourse(deleteTarget.value.id)
    toast.success("Course deactivated.")
    deleteTarget.value = null
    await loadData()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to deactivate course."))
  }
}

function groupName(gid) {
  const g = studentGroups.value.find(g => g.id === gid)
  return g ? g.code : gid
}

// ── Group drag-and-drop (By Group view) ──────────────────────────────────────
const draggingGroup = ref(null)   // { course_id, from_group_id: string|null }
const dragOverGroup = ref(null)   // group_id | "unassigned" | null
const savingGroup   = ref(null)   // course_id being saved

function onGroupDragStart(course, fromGroupId) {
  draggingGroup.value = { course_id: course.id, from_group_id: fromGroupId ?? null }
}

function onGroupDragOver(targetId) {
  dragOverGroup.value = targetId
}

function onGroupDragLeave(event) {
  // Only clear when the mouse genuinely leaves the drop zone, not when it
  // crosses into a child element (which also fires dragleave on the parent).
  if (!event.currentTarget.contains(event.relatedTarget)) {
    dragOverGroup.value = null
  }
}

async function onGroupDrop(targetGroupId) {
  dragOverGroup.value = null
  if (!draggingGroup.value) return
  const { course_id, from_group_id } = draggingGroup.value
  draggingGroup.value = null

  if (targetGroupId === (from_group_id ?? "unassigned")) return

  const c = courses.value.find(x => x.id === course_id)
  if (!c) return

  const current = (c.student_group_ids || []).slice()
  let updated

  if (targetGroupId === "unassigned") {
    updated = current.filter(id => id !== from_group_id)
  } else if (!from_group_id) {
    updated = [...current, targetGroupId]
  } else {
    updated = current.filter(id => id !== from_group_id)
    if (!updated.includes(targetGroupId)) updated.push(targetGroupId)
  }

  savingGroup.value = course_id
  try {
    await resourcesApi.setCourseGroups(course_id, updated)
    c.student_group_ids = updated
    toast.success(
      targetGroupId === "unassigned"
        ? "Removed from group"
        : `Assigned to ${studentGroups.value.find(g => g.id === targetGroupId)?.code || "group"}`
    )
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to update group assignment."))
    await loadData()
  } finally {
    savingGroup.value = null
  }
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Courses</h1>
        <p class="text-sm text-gray-500 mt-1">
          Semester courses, lecturer assignments, and student group bindings
          <span v-if="!loading" class="ml-1 text-gray-400">({{ courses.length }})</span>
        </p>
      </div>
      <button class="btn-primary flex items-center gap-2" @click="openCreate">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        Add Course
      </button>
    </div>

    <!-- Create / Edit form -->
    <div v-if="showForm" class="card space-y-4 border-blue-100 bg-blue-50/40">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-gray-900">{{ editTarget ? "Edit Course" : "New Course" }}</h2>
        <button @click="showForm = false" class="text-gray-400 hover:text-gray-600">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="grid md:grid-cols-2 gap-3">
        <div>
          <label class="label">Course Name *</label>
          <input v-model="form.name" class="input" placeholder="Data Structures & Algorithms" />
        </div>
        <div>
          <label class="label">Code *</label>
          <input v-model="form.code" class="input" placeholder="CS201" />
        </div>
        <div>
          <label class="label">Department</label>
          <select v-model="form.department_id" class="input">
            <option value="">Select department</option>
            <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
        </div>
        <div>
          <label class="label">Assigned Lecturer</label>
          <select v-model="form.lecturer_id" class="input">
            <option value="">No lecturer yet — assign in Assignments view</option>
            <option v-for="l in lecturers" :key="l.id" :value="l.id">{{ l.name }}</option>
          </select>
          <p class="text-xs text-gray-400 mt-0.5">You can also use the drag-and-drop <RouterLink to="/resources/assignments" class="text-blue-600 hover:underline">Assignments</RouterLink> board.</p>
        </div>
        <div>
          <label class="label">Semester</label>
          <select v-model.number="form.semester" class="input">
            <option :value="1">Semester 1</option>
            <option :value="2">Semester 2</option>
          </select>
        </div>
        <div>
          <label class="label">Year of Study</label>
          <input v-model.number="form.year_of_study" type="number" min="1" max="6" class="input" />
        </div>
        <div>
          <label class="label">Weekly Hours</label>
          <input v-model.number="form.weekly_hours" type="number" min="1" max="20" class="input" />
        </div>
        <div>
          <label class="label">Student Count</label>
          <input v-model.number="form.student_count" type="number" min="1" class="input" />
        </div>
        <div>
          <label class="label">Priority (1–5)</label>
          <input v-model.number="form.priority" type="number" min="1" max="5" class="input" />
        </div>
        <div class="flex items-center">
          <label class="flex items-center gap-2.5 text-sm cursor-pointer select-none mt-5">
            <input v-model="form.requires_lab" type="checkbox" class="w-4 h-4 rounded accent-blue-600" />
            <span class="text-gray-700">Requires a lab room</span>
          </label>
        </div>
      </div>

      <!-- Student group assignment -->
      <div class="border border-indigo-100 rounded-xl p-4 space-y-2 bg-white">
        <div class="flex items-center justify-between">
          <label class="label !mb-0 font-semibold">Student Groups</label>
          <span class="text-xs text-indigo-600 font-medium bg-indigo-50 px-2 py-0.5 rounded-full">
            {{ form.student_group_ids.length }} selected
          </span>
        </div>
        <p class="text-xs text-gray-500">Select which student groups take this course. The GA will create a separate timetable session for each group.</p>

        <div v-if="!studentGroups.length" class="text-xs text-gray-400 italic py-2">
          No student groups found. <RouterLink to="/resources/student-groups" class="text-blue-600 hover:underline">Add student groups first.</RouterLink>
        </div>

        <div v-else class="flex flex-wrap gap-2 pt-1">
          <!-- Groups matching semester/year shown first -->
          <template v-if="relevantGroups.length">
            <button
              v-for="g in relevantGroups"
              :key="g.id"
              type="button"
              @click="toggleGroup(g.id)"
              :class="[
                'px-3 py-1.5 rounded-full text-xs font-medium border transition-all',
                form.student_group_ids.includes(g.id)
                  ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                  : 'bg-white text-gray-600 border-gray-300 hover:border-indigo-400'
              ]"
            >
              {{ g.code }} <span class="opacity-60">(Yr{{ g.year_of_study }} Sem{{ g.semester }})</span>
            </button>
          </template>

          <!-- Show all if no relevant groups -->
          <template v-else>
            <button
              v-for="g in studentGroups"
              :key="g.id"
              type="button"
              @click="toggleGroup(g.id)"
              :class="[
                'px-3 py-1.5 rounded-full text-xs font-medium border transition-all',
                form.student_group_ids.includes(g.id)
                  ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                  : 'bg-white text-gray-600 border-gray-300 hover:border-indigo-400'
              ]"
            >
              {{ g.code }}
            </button>
          </template>
        </div>
      </div>

      <div class="flex gap-2">
        <button class="btn-primary" :disabled="saving" @click="save">
          {{ saving ? "Saving…" : editTarget ? "Update" : "Create" }}
        </button>
        <button class="btn-secondary" @click="showForm = false">Cancel</button>
      </div>
    </div>

    <!-- Delete confirmation -->
    <div v-if="deleteTarget" class="card border-red-200 bg-red-50 space-y-3">
      <p class="text-sm text-red-800 font-medium">Deactivate <strong>{{ deleteTarget.code }} — {{ deleteTarget.name }}</strong>?</p>
      <div class="flex gap-2">
        <button class="btn-danger text-sm" @click="confirmDelete">Yes, deactivate</button>
        <button class="btn-secondary text-sm" @click="deleteTarget = null">Cancel</button>
      </div>
    </div>

    <!-- Filters + view toggle -->
    <div class="flex flex-wrap gap-3 items-center">
      <input v-model="search" class="input flex-1 min-w-[180px] max-w-xs" placeholder="Search courses…" />
      <select v-model="deptFilter" class="input w-auto">
        <option value="">All departments</option>
        <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
      </select>
      <!-- View mode toggle -->
      <div class="flex rounded-lg border border-gray-200 overflow-hidden text-sm font-medium">
        <button
          @click="viewMode = 'list'"
          :class="viewMode === 'list' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
          class="px-3 py-2 transition-colors flex items-center gap-1.5"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
          </svg>
          List
        </button>
        <button
          @click="viewMode = 'byGroup'"
          :class="viewMode === 'byGroup' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'"
          class="px-3 py-2 transition-colors border-l border-gray-200 flex items-center gap-1.5"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          By Group
        </button>
      </div>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="space-y-2">
      <div v-for="i in 8" :key="i" class="card animate-pulse flex items-center gap-4">
        <div class="w-10 h-10 bg-gray-200 rounded-lg flex-shrink-0"></div>
        <div class="flex-1 space-y-2">
          <div class="h-4 bg-gray-200 rounded w-1/3"></div>
          <div class="h-3 bg-gray-200 rounded w-1/4"></div>
        </div>
        <div class="w-16 h-6 bg-gray-200 rounded"></div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!courses.length" class="card text-center py-14">
      <div class="w-14 h-14 mx-auto bg-orange-50 rounded-2xl flex items-center justify-center mb-3">
        <svg class="w-7 h-7 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
      </div>
      <h3 class="font-semibold text-gray-900 mb-1">No courses yet</h3>
      <p class="text-sm text-gray-500 mb-5">Add courses to include them in timetable generation.</p>
      <button class="btn-primary" @click="openCreate">Add Course</button>
    </div>

    <!-- No filter results -->
    <div v-else-if="!filtered.length" class="card text-center py-8 text-sm text-gray-500">
      No courses match your filters.
      <button class="text-blue-600 hover:underline ml-1" @click="search = ''; deptFilter = ''">Clear</button>
    </div>

    <!-- ── Flat list view ─────────────────────────────────────────────────── -->
    <div v-else-if="viewMode === 'list'" class="card divide-y divide-gray-100">
      <div
        v-for="c in filtered"
        :key="c.id"
        class="flex items-center gap-4 py-3.5 -mx-6 px-6 hover:bg-gray-50 transition-colors"
        :class="deleteTarget?.id === c.id ? 'bg-red-50' : ''"
      >
        <div class="w-10 h-10 rounded-lg bg-orange-100 flex items-center justify-center flex-shrink-0">
          <svg class="w-5 h-5 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
        </div>

        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <p class="font-semibold text-gray-900">{{ c.code }}</p>
            <span class="text-gray-400">·</span>
            <p class="text-gray-700 truncate">{{ c.name }}</p>
            <span v-if="c.requires_lab" class="px-1.5 py-0.5 rounded text-xs bg-purple-100 text-purple-700 font-medium">Lab</span>
            <span v-if="!c.lecturer" class="px-1.5 py-0.5 rounded text-xs bg-amber-100 text-amber-700 font-medium">Unassigned</span>
          </div>
          <div class="flex items-center gap-3 text-xs text-gray-500 mt-0.5 flex-wrap">
            <span>{{ c.department?.name || "No dept" }}</span>
            <span>·</span>
            <span>Sem {{ c.semester }}</span>
            <span>·</span>
            <span>Yr {{ c.year_of_study }}</span>
            <span>·</span>
            <span>{{ c.weekly_hours }}h/wk</span>
            <span>·</span>
            <span>{{ c.student_count }} students</span>
            <span v-if="c.lecturer?.name">· {{ c.lecturer.name }}</span>
          </div>
          <div v-if="c.student_group_ids?.length" class="flex flex-wrap gap-1 mt-1.5">
            <span
              v-for="gid in c.student_group_ids"
              :key="gid"
              class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-100"
            >{{ groupName(gid) }}</span>
          </div>
          <p v-else class="text-[10px] text-gray-300 mt-1 italic">No groups assigned — GA will infer from programme</p>
        </div>

        <div class="flex gap-1 flex-shrink-0">
          <button class="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" @click="openEdit(c)" title="Edit">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
          <button class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg" @click="deleteTarget = c; showForm = false" title="Deactivate">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- ── By Group view ───────────────────────────────────────────────────── -->
    <div v-else class="grid md:grid-cols-[1fr_300px] gap-6">

      <!-- ── Group board ─────────────────────────────────────────────────── -->
      <div class="space-y-4">
        <h2 class="font-semibold text-gray-700 text-sm uppercase tracking-wide">Student Groups</h2>

        <div v-if="!studentGroups.length" class="card text-center py-10 text-gray-400">
          No student groups added yet.
        </div>

        <div class="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
          <div
            v-for="bucket in groupedView.buckets"
            :key="bucket.group.id"
            class="card border-2 transition-all duration-150 min-h-[140px] flex flex-col"
            :class="dragOverGroup === bucket.group.id
              ? 'border-indigo-400 bg-indigo-50 shadow-md'
              : 'border-transparent hover:border-gray-200'"
            @dragover.prevent="onGroupDragOver(bucket.group.id)"
            @dragleave="onGroupDragLeave"
            @drop.prevent="onGroupDrop(bucket.group.id)"
          >
            <!-- Group header -->
            <div class="flex items-center gap-3 mb-3">
              <div class="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-400 to-purple-500 flex items-center justify-center text-white text-xs font-bold shrink-0 select-none">
                {{ (bucket.group.code || "?").slice(0, 2).toUpperCase() }}
              </div>
              <div class="min-w-0">
                <p class="font-semibold text-gray-900 text-sm truncate">{{ bucket.group.code }}</p>
                <p class="text-xs text-gray-400 truncate">Yr{{ bucket.group.year_of_study }} · Sem{{ bucket.group.semester }}<span v-if="bucket.group.program?.name"> · {{ bucket.group.program.name }}</span></p>
              </div>
              <span class="ml-auto text-xs font-bold text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded-full shrink-0">
                {{ bucket.courses.length }}
              </span>
            </div>

            <!-- Drop hint -->
            <div
              v-if="dragOverGroup === bucket.group.id && draggingGroup && draggingGroup.from_group_id !== bucket.group.id"
              class="text-xs text-indigo-600 font-medium text-center py-1 rounded-lg bg-indigo-100 mb-2"
            >
              Drop to assign
            </div>

            <!-- Course chips -->
            <div class="flex flex-col gap-1.5 flex-1">
              <div
                v-for="c in bucket.courses"
                :key="c.id"
                draggable="true"
                @dragstart="onGroupDragStart(c, bucket.group.id)"
                class="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-indigo-50 border border-indigo-200 cursor-grab active:cursor-grabbing select-none hover:bg-indigo-100 transition-colors"
                :class="savingGroup === c.id ? 'opacity-50 cursor-wait' : ''"
              >
                <span class="w-1.5 h-1.5 rounded-full bg-indigo-500 shrink-0"></span>
                <div class="min-w-0 flex-1">
                  <p class="text-xs font-bold text-indigo-900 leading-tight">{{ c.code }}</p>
                  <p class="text-[11px] text-indigo-700 truncate leading-tight">{{ c.name }}</p>
                </div>
                <button
                  class="p-0.5 text-indigo-300 hover:text-blue-600 rounded shrink-0"
                  @click.stop="openEdit(c)"
                  @mousedown.stop
                  title="Edit"
                >
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>
              </div>

              <p v-if="!bucket.courses.length" class="text-xs text-gray-300 italic self-center mt-1">
                No courses — drop here
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Unassigned pool ─────────────────────────────────────────────── -->
      <div>
        <h2 class="font-semibold text-gray-700 text-sm uppercase tracking-wide mb-4">
          Unassigned
          <span class="text-amber-600 font-bold ml-1">({{ groupedView.unassigned.length }})</span>
        </h2>

        <div
          class="card border-2 min-h-[200px] flex flex-col gap-2 transition-all duration-150"
          :class="dragOverGroup === 'unassigned'
            ? 'border-amber-400 bg-amber-50 shadow-md'
            : 'border-dashed border-gray-300 hover:border-amber-300'"
          @dragover.prevent="onGroupDragOver('unassigned')"
          @dragleave="onGroupDragLeave"
          @drop.prevent="onGroupDrop('unassigned')"
        >
          <p v-if="dragOverGroup === 'unassigned'" class="text-xs text-amber-600 font-medium text-center py-1 rounded-lg bg-amber-100">
            Drop to remove from group
          </p>

          <template v-if="groupedView.unassigned.length">
            <div
              v-for="c in groupedView.unassigned"
              :key="c.id"
              draggable="true"
              @dragstart="onGroupDragStart(c, null)"
              class="flex items-start gap-2 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 cursor-grab active:cursor-grabbing select-none hover:bg-amber-100 transition-colors"
              :class="savingGroup === c.id ? 'opacity-50 cursor-wait' : ''"
            >
              <span class="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0 mt-1"></span>
              <div class="min-w-0 flex-1">
                <p class="text-xs font-bold text-amber-900">{{ c.code }}</p>
                <p class="text-[11px] text-amber-700 truncate">{{ c.name }}</p>
                <p class="text-[10px] text-amber-500">Sem {{ c.semester }} · Yr {{ c.year_of_study }}</p>
              </div>
              <button
                class="p-0.5 text-amber-300 hover:text-blue-600 rounded shrink-0 mt-0.5"
                @click.stop="openEdit(c)"
                @mousedown.stop
                title="Edit"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              </button>
            </div>
          </template>

          <div v-else class="flex-1 flex flex-col items-center justify-center text-center py-8">
            <svg class="w-8 h-8 text-green-300 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p class="text-xs text-gray-400 font-medium">All courses grouped!</p>
          </div>
        </div>

        <!-- Stats -->
        <div class="mt-4 p-3 rounded-xl bg-gray-50 border border-gray-100 text-xs text-gray-500 space-y-1">
          <div class="flex justify-between">
            <span>Total courses</span>
            <span class="font-semibold text-gray-700">{{ filtered.length }}</span>
          </div>
          <div class="flex justify-between">
            <span>Grouped</span>
            <span class="font-semibold text-green-700">{{ filtered.length - groupedView.unassigned.length }}</span>
          </div>
          <div class="flex justify-between">
            <span>Ungrouped</span>
            <span class="font-semibold text-amber-600">{{ groupedView.unassigned.length }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
