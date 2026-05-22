<script setup>
import { onMounted, ref, computed } from "vue"
import { resourcesApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const saving = ref(false)
const courses = ref([])
const departments = ref([])
const lecturers = ref([])
const showForm = ref(false)
const editTarget = ref(null)
const deleteTarget = ref(null)
const search = ref("")
const deptFilter = ref("")

const blank = () => ({
  name: "", code: "", department_id: "", lecturer_id: "",
  semester: 1, year_of_study: 1, weekly_hours: 3,
  student_count: 40, requires_lab: false, priority: 1,
})
const form = ref(blank())

const filtered = computed(() => {
  let list = courses.value
  if (deptFilter.value) list = list.filter((c) => c.department_id === deptFilter.value)
  const q = search.value.toLowerCase()
  if (q) list = list.filter((c) => c.name.toLowerCase().includes(q) || c.code.toLowerCase().includes(q))
  return list
})

async function loadData() {
  loading.value = true
  try {
    const [courseRes, deptRes, lecRes] = await Promise.all([
      resourcesApi.courses(),
      resourcesApi.departments(),
      resourcesApi.lecturers(),
    ])
    courses.value = courseRes.data.data || []
    departments.value = deptRes.data.data || []
    lecturers.value = lecRes.data.data || []
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load data."))
  } finally {
    loading.value = false
  }
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
    lecturer_id: c.lecturer_id || "",
    semester: c.semester, year_of_study: c.year_of_study,
    weekly_hours: c.weekly_hours, student_count: c.student_count,
    requires_lab: c.requires_lab || false, priority: c.priority || 1,
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
    if (editTarget.value) {
      await resourcesApi.updateCourse(editTarget.value.id, form.value)
      toast.success("Course updated.")
    } else {
      await resourcesApi.createCourse(form.value)
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

onMounted(loadData)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Courses</h1>
        <p class="text-sm text-gray-500 mt-1">
          Semester courses and scheduling constraints
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
            <option value="">Select lecturer</option>
            <option v-for="l in lecturers" :key="l.id" :value="l.id">{{ l.name }}</option>
          </select>
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

    <!-- Filters -->
    <div class="flex flex-wrap gap-3">
      <input v-model="search" class="input flex-1 min-w-[180px] max-w-xs" placeholder="Search courses…" />
      <select v-model="deptFilter" class="input w-auto">
        <option value="">All departments</option>
        <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
      </select>
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

    <!-- Course list -->
    <div v-else class="card divide-y divide-gray-100">
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
            <span v-if="c.lecturer?.name || lecturers.find(l => l.id === c.lecturer_id)">
              · {{ c.lecturer?.name || lecturers.find(l => l.id === c.lecturer_id)?.name }}
            </span>
          </div>
        </div>
        <div class="flex gap-1 flex-shrink-0">
          <button class="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" @click="openEdit(c)">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
          <button class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg" @click="deleteTarget = c; showForm = false">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
