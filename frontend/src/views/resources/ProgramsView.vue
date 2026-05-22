<script setup>
import { computed, onMounted, ref } from "vue"
import { resourcesApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const saving = ref(false)
const programs = ref([])
const universities = ref([])
const departments = ref([])
const showForm = ref(false)
const editTarget = ref(null)
const deleteTarget = ref(null)
const filterUniversity = ref("")
const filterDept = ref("")
const search = ref("")

const blank = () => ({
  name: "", code: "", department_id: "",
  academic_level: "Bachelor", duration_years: 3, description: "",
})
const form = ref(blank())

const LEVELS = ["Certificate", "Diploma", "Bachelor", "Master", "PhD"]
const LEVEL_COLORS = {
  Certificate: "bg-gray-100 text-gray-600",
  Diploma: "bg-teal-100 text-teal-700",
  Bachelor: "bg-blue-100 text-blue-700",
  Master: "bg-purple-100 text-purple-700",
  PhD: "bg-rose-100 text-rose-700",
}

const filteredDepts = computed(() =>
  filterUniversity.value
    ? departments.value.filter((d) => d.university_id === filterUniversity.value)
    : departments.value,
)

const filteredPrograms = computed(() => {
  let list = programs.value
  if (filterDept.value) list = list.filter((p) => p.department_id === filterDept.value)
  else if (filterUniversity.value) list = list.filter((p) => p.department?.university_id === filterUniversity.value)
  const q = search.value.toLowerCase()
  if (q) list = list.filter((p) => p.name.toLowerCase().includes(q) || p.code.toLowerCase().includes(q))
  return list
})

async function load() {
  loading.value = true
  try {
    const [pRes, uRes, dRes] = await Promise.all([
      resourcesApi.programs(),
      resourcesApi.universities(),
      resourcesApi.departments(),
    ])
    programs.value = pRes.data.data || []
    universities.value = uRes.data.data || []
    departments.value = dRes.data.data || []
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

function openEdit(prog) {
  editTarget.value = prog
  form.value = {
    name: prog.name, code: prog.code,
    department_id: prog.department_id,
    academic_level: prog.academic_level,
    duration_years: prog.duration_years,
    description: prog.description || "",
  }
  showForm.value = true
  deleteTarget.value = null
}

async function save() {
  if (!form.value.name || !form.value.code || !form.value.department_id) {
    toast.error("Name, code and department are required.")
    return
  }
  saving.value = true
  try {
    if (editTarget.value) {
      await resourcesApi.updateProgram(editTarget.value.id, form.value)
      toast.success("Program updated.")
    } else {
      await resourcesApi.createProgram(form.value)
      toast.success("Program created.")
    }
    showForm.value = false
    editTarget.value = null
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to save program."))
  } finally {
    saving.value = false
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  try {
    await resourcesApi.deleteProgram(deleteTarget.value.id)
    toast.success("Program deactivated.")
    deleteTarget.value = null
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to deactivate program."))
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Study Programs</h1>
        <p class="text-sm text-gray-500 mt-1">
          BCS, BIT, DCS, CIT and other programmes within departments
          <span v-if="!loading" class="ml-1 text-gray-400">({{ programs.length }})</span>
        </p>
      </div>
      <button class="btn-primary flex items-center gap-2" @click="openCreate">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        Add Program
      </button>
    </div>

    <!-- Create / Edit form -->
    <div v-if="showForm" class="card space-y-4 border-blue-100 bg-blue-50/40">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-gray-900">{{ editTarget ? "Edit Program" : "New Program" }}</h2>
        <button @click="showForm = false" class="text-gray-400 hover:text-gray-600">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div class="grid md:grid-cols-2 gap-3">
        <div>
          <label class="label">Full Name *</label>
          <input v-model="form.name" class="input" placeholder="Bachelor of Computer Science" />
        </div>
        <div>
          <label class="label">Code *</label>
          <input v-model="form.code" class="input" placeholder="BCS" />
        </div>
        <div>
          <label class="label">Department *</label>
          <select v-model="form.department_id" class="input">
            <option value="">Select department</option>
            <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
        </div>
        <div>
          <label class="label">Academic Level</label>
          <select v-model="form.academic_level" class="input">
            <option v-for="l in LEVELS" :key="l" :value="l">{{ l }}</option>
          </select>
        </div>
        <div>
          <label class="label">Duration (years)</label>
          <input v-model.number="form.duration_years" type="number" min="1" max="6" class="input" />
        </div>
      </div>
      <div>
        <label class="label">Description <span class="text-gray-400 font-normal">(optional)</span></label>
        <textarea v-model="form.description" class="input" rows="2" placeholder="Brief programme description" />
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
      <p class="text-sm text-red-800 font-medium">Deactivate <strong>{{ deleteTarget.name }}</strong>?</p>
      <div class="flex gap-2">
        <button class="btn-danger text-sm" @click="confirmDelete">Yes, deactivate</button>
        <button class="btn-secondary text-sm" @click="deleteTarget = null">Cancel</button>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3">
      <input v-model="search" class="input flex-1 min-w-[150px] max-w-xs" placeholder="Search programs…" />
      <select v-model="filterUniversity" class="input w-auto" @change="filterDept = ''">
        <option value="">All Universities</option>
        <option v-for="u in universities" :key="u.id" :value="u.id">{{ u.code }}</option>
      </select>
      <select v-model="filterDept" class="input w-auto">
        <option value="">All Departments</option>
        <option v-for="d in filteredDepts" :key="d.id" :value="d.id">{{ d.name }}</option>
      </select>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="card divide-y divide-gray-100">
      <div v-for="i in 8" :key="i" class="py-3.5 flex items-center gap-4 animate-pulse">
        <div class="w-10 h-10 bg-gray-200 rounded-lg flex-shrink-0"></div>
        <div class="flex-1 space-y-2">
          <div class="h-4 bg-gray-200 rounded w-2/5"></div>
          <div class="h-3 bg-gray-200 rounded w-1/3"></div>
        </div>
        <div class="w-16 h-5 bg-gray-200 rounded-full"></div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!programs.length" class="card text-center py-14">
      <div class="w-14 h-14 mx-auto bg-purple-50 rounded-2xl flex items-center justify-center mb-3">
        <svg class="w-7 h-7 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4.26 10.147a60.436 60.436 0 00-.491 6.347A48.627 48.627 0 0112 20.904a48.627 48.627 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.57 50.57 0 00-2.658-.813A59.905 59.905 0 0112 3.493a59.902 59.902 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0112 13.489a50.702 50.702 0 017.74-3.342M6.75 15a.75.75 0 100-1.5.75.75 0 000 1.5zm0 0v-3.675A55.378 55.378 0 0112 8.443m-7.007 11.55A5.981 5.981 0 006.75 15.75v-1.5" />
        </svg>
      </div>
      <h3 class="font-semibold text-gray-900 mb-1">No programs yet</h3>
      <p class="text-sm text-gray-500 mb-5">Create departments first, then add programs to them.</p>
      <button class="btn-primary" @click="openCreate">Add Program</button>
    </div>

    <!-- No filter results -->
    <div v-else-if="!filteredPrograms.length" class="card text-center py-8 text-sm text-gray-500">
      No programs match your filters.
      <button class="text-blue-600 hover:underline ml-1" @click="search = ''; filterUniversity = ''; filterDept = ''">Clear</button>
    </div>

    <!-- Program list -->
    <div v-else class="card divide-y divide-gray-100">
      <div
        v-for="p in filteredPrograms"
        :key="p.id"
        class="flex items-center gap-4 py-3.5 -mx-6 px-6 hover:bg-gray-50 transition-colors"
        :class="deleteTarget?.id === p.id ? 'bg-red-50' : ''"
      >
        <div class="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center flex-shrink-0">
          <span class="text-xs font-bold text-purple-700">{{ p.code }}</span>
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <p class="font-semibold text-gray-900 truncate">{{ p.name }}</p>
            <span class="px-1.5 py-0.5 rounded text-xs font-medium" :class="LEVEL_COLORS[p.academic_level] || 'bg-gray-100 text-gray-600'">
              {{ p.academic_level }}
            </span>
          </div>
          <div class="flex items-center gap-2 text-xs text-gray-500 mt-0.5">
            <span>{{ p.department?.name || "No dept" }}</span>
            <span>·</span>
            <span>{{ p.duration_years }} yr{{ p.duration_years !== 1 ? "s" : "" }}</span>
          </div>
        </div>
        <div class="flex gap-1 flex-shrink-0">
          <button class="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" @click="openEdit(p)">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
          <button class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg" @click="deleteTarget = p; showForm = false">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
