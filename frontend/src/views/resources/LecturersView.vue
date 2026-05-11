<script setup>
import { onMounted, ref } from "vue"
import { resourcesApi } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const lecturers = ref([])
const departments = ref([])
const form = ref({
  name: "",
  email: "",
  staff_id: "",
  department_id: "",
  max_hours_per_week: 20,
})

async function loadData() {
  loading.value = true
  try {
    const [lecRes, deptRes] = await Promise.all([
      resourcesApi.lecturers(),
      resourcesApi.departments(),
    ])
    lecturers.value = lecRes.data.data || []
    departments.value = deptRes.data.data || []
  } finally {
    loading.value = false
  }
}

async function createLecturer() {
  await resourcesApi.createLecturer(form.value)
  toast.success("Lecturer created.")
  form.value = { name: "", email: "", staff_id: "", department_id: "", max_hours_per_week: 20 }
  await loadData()
}

async function deactivateLecturer(id) {
  await resourcesApi.deleteLecturer(id)
  toast.success("Lecturer deactivated.")
  await loadData()
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Lecturers</h1>
      <p class="text-sm text-gray-500 mt-1">Academic staff profiles and workload caps.</p>
    </div>

    <div class="card space-y-3">
      <h2 class="font-semibold">Create Lecturer</h2>
      <div class="grid md:grid-cols-2 gap-3">
        <input v-model="form.name" class="input" placeholder="Full name" />
        <input v-model="form.email" type="email" class="input" placeholder="Email" />
        <input v-model="form.staff_id" class="input" placeholder="Staff ID" />
        <select v-model="form.department_id" class="input">
          <option value="">Select department</option>
          <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
        </select>
        <input v-model.number="form.max_hours_per_week" type="number" class="input" placeholder="Max hours per week" />
      </div>
      <button class="btn-primary" @click="createLecturer">Create</button>
    </div>

    <div class="card">
      <h2 class="font-semibold mb-3">All Lecturers</h2>
      <div v-if="loading" class="text-sm text-gray-500">Loading...</div>
      <div v-else-if="!lecturers.length" class="text-sm text-gray-500">No lecturers found.</div>
      <div v-else class="space-y-2">
        <div v-for="l in lecturers" :key="l.id" class="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
          <div>
            <p class="font-medium">{{ l.name }}</p>
            <p class="text-xs text-gray-500">{{ l.email }} | {{ l.department?.name || "No department" }}</p>
          </div>
          <button class="btn-danger" @click="deactivateLecturer(l.id)">Deactivate</button>
        </div>
      </div>
    </div>
  </div>
</template>
