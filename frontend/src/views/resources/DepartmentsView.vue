<script setup>
import { onMounted, ref } from "vue"
import { getErrorMessage, resourcesApi } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const departments = ref([])
const form = ref({ name: "", code: "", faculty: "", head_name: "" })
const error = ref("")

async function loadDepartments() {
  loading.value = true
  error.value = ""
  try {
    const { data } = await resourcesApi.departments()
    departments.value = data.data || []
  } catch (e) {
    error.value = getErrorMessage(e, "Failed to load departments.")
  } finally {
    loading.value = false
  }
}

async function createDepartment() {
  if (!form.value.name || !form.value.code) return
  try {
    await resourcesApi.createDepartment(form.value)
    toast.success("Department created.")
    form.value = { name: "", code: "", faculty: "", head_name: "" }
    await loadDepartments()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to create department."))
  }
}

async function removeDepartment(id) {
  try {
    await resourcesApi.deleteDepartment(id)
    toast.success("Department deleted.")
    await loadDepartments()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to delete department."))
  }
}

onMounted(loadDepartments)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Departments</h1>
      <p class="text-sm text-gray-500 mt-1">Manage faculties and department metadata.</p>
    </div>

    <div class="card space-y-3">
      <h2 class="font-semibold">Create Department</h2>
      <div class="grid md:grid-cols-2 gap-3">
        <input v-model="form.name" class="input" placeholder="Department name" />
        <input v-model="form.code" class="input" placeholder="Code" />
        <input v-model="form.faculty" class="input" placeholder="Faculty" />
        <input v-model="form.head_name" class="input" placeholder="Head name" />
      </div>
      <button class="btn-primary" @click="createDepartment">Create</button>
    </div>

    <div class="card">
      <h2 class="font-semibold mb-3">All Departments</h2>
      <div v-if="loading" class="text-sm text-gray-500">Loading...</div>
      <div v-else-if="error" class="text-sm text-red-600">{{ error }}</div>
      <div v-else-if="!departments.length" class="text-sm text-gray-500">No departments found.</div>
      <div v-else class="space-y-2">
        <div v-for="d in departments" :key="d.id" class="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
          <div>
            <p class="font-medium">{{ d.name }} ({{ d.code }})</p>
            <p class="text-xs text-gray-500">{{ d.faculty || "No faculty" }} | {{ d.head_name || "No head assigned" }}</p>
          </div>
          <button class="btn-danger" @click="removeDepartment(d.id)">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>
