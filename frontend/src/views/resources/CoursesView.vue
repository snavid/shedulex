<script setup>
import { onMounted, ref } from "vue"
import { resourcesApi } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const courses = ref([])
const departments = ref([])
const lecturers = ref([])
const form = ref({
  name: "",
  code: "",
  department_id: "",
  lecturer_id: "",
  semester: 1,
  year_of_study: 1,
  weekly_hours: 3,
  student_count: 40,
  requires_lab: false,
  priority: 1,
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
  } finally {
    loading.value = false
  }
}

async function createCourse() {
  await resourcesApi.createCourse(form.value)
  toast.success("Course created.")
  form.value = {
    name: "",
    code: "",
    department_id: "",
    lecturer_id: "",
    semester: 1,
    year_of_study: 1,
    weekly_hours: 3,
    student_count: 40,
    requires_lab: false,
    priority: 1,
  }
  await loadData()
}

async function deactivateCourse(id) {
  await resourcesApi.deleteCourse(id)
  toast.success("Course deactivated.")
  await loadData()
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Courses</h1>
      <p class="text-sm text-gray-500 mt-1">Manage semester courses and scheduling constraints.</p>
    </div>

    <div class="card space-y-3">
      <h2 class="font-semibold">Create Course</h2>
      <div class="grid md:grid-cols-3 gap-3">
        <input v-model="form.name" class="input" placeholder="Course name" />
        <input v-model="form.code" class="input" placeholder="Course code" />
        <select v-model="form.department_id" class="input">
          <option value="">Department</option>
          <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
        </select>
        <select v-model="form.lecturer_id" class="input">
          <option value="">Lecturer</option>
          <option v-for="l in lecturers" :key="l.id" :value="l.id">{{ l.name }}</option>
        </select>
        <input v-model.number="form.semester" type="number" min="1" max="2" class="input" placeholder="Semester" />
        <input v-model.number="form.year_of_study" type="number" min="1" max="6" class="input" placeholder="Year of study" />
        <input v-model.number="form.weekly_hours" type="number" min="1" class="input" placeholder="Weekly hours" />
        <input v-model.number="form.student_count" type="number" min="1" class="input" placeholder="Student count" />
        <input v-model.number="form.priority" type="number" min="1" max="5" class="input" placeholder="Priority" />
      </div>
      <label class="flex items-center gap-2 text-sm">
        <input v-model="form.requires_lab" type="checkbox" />
        Requires lab
      </label>
      <button class="btn-primary" @click="createCourse">Create</button>
    </div>

    <div class="card">
      <h2 class="font-semibold mb-3">All Courses</h2>
      <div v-if="loading" class="text-sm text-gray-500">Loading...</div>
      <div v-else-if="!courses.length" class="text-sm text-gray-500">No courses found.</div>
      <div v-else class="space-y-2">
        <div v-for="c in courses" :key="c.id" class="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
          <div>
            <p class="font-medium">{{ c.code }} - {{ c.name }}</p>
            <p class="text-xs text-gray-500">
              Semester {{ c.semester }} | {{ c.department?.name || "No department" }} | {{ c.student_count }} students
            </p>
          </div>
          <button class="btn-danger" @click="deactivateCourse(c.id)">Deactivate</button>
        </div>
      </div>
    </div>
  </div>
</template>
