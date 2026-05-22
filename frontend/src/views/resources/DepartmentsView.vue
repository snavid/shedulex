<script setup>
import { onMounted, ref, computed } from "vue"
import { getErrorMessage, resourcesApi } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const saving = ref(false)
const departments = ref([])
const showForm = ref(false)
const editTarget = ref(null)
const deleteTarget = ref(null)
const search = ref("")
const error = ref("")

const blank = () => ({ name: "", code: "", faculty: "", head_name: "" })
const form = ref(blank())

const filtered = computed(() => {
  const q = search.value.toLowerCase()
  return q
    ? departments.value.filter(
        (d) =>
          d.name.toLowerCase().includes(q) ||
          d.code.toLowerCase().includes(q) ||
          (d.faculty || "").toLowerCase().includes(q),
      )
    : departments.value
})

async function load() {
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

function openCreate() {
  editTarget.value = null
  form.value = blank()
  showForm.value = true
}

function openEdit(d) {
  editTarget.value = d
  form.value = { name: d.name, code: d.code, faculty: d.faculty || "", head_name: d.head_name || "" }
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
      await resourcesApi.updateDepartment(editTarget.value.id, form.value)
      toast.success("Department updated.")
    } else {
      await resourcesApi.createDepartment(form.value)
      toast.success("Department created.")
    }
    showForm.value = false
    editTarget.value = null
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to save department."))
  } finally {
    saving.value = false
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  try {
    await resourcesApi.deleteDepartment(deleteTarget.value.id)
    toast.success("Department deleted.")
    deleteTarget.value = null
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to delete department."))
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Departments</h1>
        <p class="text-sm text-gray-500 mt-1">
          Manage faculties and department metadata
          <span v-if="!loading" class="ml-1 text-gray-400">({{ departments.length }})</span>
        </p>
      </div>
      <button class="btn-primary flex items-center gap-2" @click="openCreate">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        Add Department
      </button>
    </div>

    <!-- Create / Edit form -->
    <div v-if="showForm" class="card space-y-4 border-blue-100 bg-blue-50/40">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-gray-900">{{ editTarget ? "Edit Department" : "New Department" }}</h2>
        <button @click="showForm = false" class="text-gray-400 hover:text-gray-600">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div class="grid md:grid-cols-2 gap-3">
        <div>
          <label class="label">Name *</label>
          <input v-model="form.name" class="input" placeholder="Faculty of Information Technology" />
        </div>
        <div>
          <label class="label">Code *</label>
          <input v-model="form.code" class="input" placeholder="FIT" />
        </div>
        <div>
          <label class="label">Faculty / School</label>
          <input v-model="form.faculty" class="input" placeholder="School of Science & Technology" />
        </div>
        <div>
          <label class="label">Head of Department</label>
          <input v-model="form.head_name" class="input" placeholder="Prof. Jane Doe" />
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
      <p class="text-sm text-red-800 font-medium">Delete <strong>{{ deleteTarget.name }}</strong>?</p>
      <p class="text-xs text-red-600">This may fail if the department has associated resources.</p>
      <div class="flex gap-2">
        <button class="btn-danger text-sm" @click="confirmDelete">Yes, delete</button>
        <button class="btn-secondary text-sm" @click="deleteTarget = null">Cancel</button>
      </div>
    </div>

    <!-- Search -->
    <div class="flex gap-3">
      <input v-model="search" class="input flex-1 max-w-sm" placeholder="Search departments…" />
    </div>

    <!-- Error -->
    <div v-if="error" class="card border-red-200 bg-red-50 text-red-700 text-sm">{{ error }}</div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="i in 6" :key="i" class="card animate-pulse space-y-3">
        <div class="h-4 bg-gray-200 rounded w-2/3"></div>
        <div class="h-3 bg-gray-200 rounded w-1/3"></div>
        <div class="h-3 bg-gray-200 rounded w-1/2"></div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!departments.length" class="card text-center py-14">
      <div class="w-14 h-14 mx-auto bg-indigo-50 rounded-2xl flex items-center justify-center mb-3">
        <svg class="w-7 h-7 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
        </svg>
      </div>
      <h3 class="font-semibold text-gray-900 mb-1">No departments yet</h3>
      <p class="text-sm text-gray-500 mb-5">Add your first department to start building programs.</p>
      <button class="btn-primary" @click="openCreate">Add Department</button>
    </div>

    <!-- No filter results -->
    <div v-else-if="!filtered.length" class="card text-center py-8 text-sm text-gray-500">
      No departments match "<strong>{{ search }}</strong>".
      <button class="text-blue-600 hover:underline ml-1" @click="search = ''">Clear</button>
    </div>

    <!-- Department cards -->
    <div v-else class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="d in filtered"
        :key="d.id"
        class="card hover:shadow-md transition-shadow space-y-3"
        :class="deleteTarget?.id === d.id ? 'border-red-300' : ''"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <h3 class="font-semibold text-gray-900 truncate">{{ d.name }}</h3>
            <span class="inline-block mt-1 px-2 py-0.5 rounded-md bg-blue-100 text-blue-700 text-xs font-semibold">{{ d.code }}</span>
          </div>
          <div class="flex gap-1 flex-shrink-0">
            <button
              class="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
              title="Edit"
              @click="openEdit(d)"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
            <button
              class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              title="Delete"
              @click="deleteTarget = d; showForm = false"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
        <div class="text-sm text-gray-600 space-y-1">
          <div class="flex items-center gap-2">
            <svg class="w-3.5 h-3.5 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16" />
            </svg>
            <span class="text-gray-500">{{ d.faculty || "No faculty assigned" }}</span>
          </div>
          <div class="flex items-center gap-2">
            <svg class="w-3.5 h-3.5 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <span class="text-gray-500">{{ d.head_name || "No HoD assigned" }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
