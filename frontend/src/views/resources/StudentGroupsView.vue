<script setup>
import { computed, onMounted, ref } from "vue"
import { resourcesApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const saving = ref(false)
const groups = ref([])
const programs = ref([])
const showForm = ref(false)
const editTarget = ref(null)
const deleteTarget = ref(null)
const filterProgram = ref("")
const search = ref("")

const blank = () => ({
  name: "", code: "", program_id: "",
  year_of_study: 1, student_count: 30,
})
const form = ref(blank())

const filtered = computed(() => {
  let list = groups.value
  if (filterProgram.value) list = list.filter((g) => g.program_id === filterProgram.value)
  const q = search.value.toLowerCase()
  if (q) list = list.filter((g) => g.name.toLowerCase().includes(q) || g.code.toLowerCase().includes(q))
  return list
})

async function load() {
  loading.value = true
  try {
    const [gRes, pRes] = await Promise.all([resourcesApi.studentGroups(), resourcesApi.programs()])
    groups.value = gRes.data.data || []
    programs.value = pRes.data.data || []
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

function openEdit(g) {
  editTarget.value = g
  form.value = {
    name: g.name, code: g.code, program_id: g.program_id,
    year_of_study: g.year_of_study, student_count: g.student_count,
  }
  showForm.value = true
  deleteTarget.value = null
}

async function save() {
  if (!form.value.name || !form.value.code || !form.value.program_id) {
    toast.error("Name, code and program are required.")
    return
  }
  saving.value = true
  try {
    if (editTarget.value) {
      await resourcesApi.updateStudentGroup(editTarget.value.id, form.value)
      toast.success("Student group updated.")
    } else {
      await resourcesApi.createStudentGroup(form.value)
      toast.success("Student group created.")
    }
    showForm.value = false
    editTarget.value = null
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to save student group."))
  } finally {
    saving.value = false
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  try {
    await resourcesApi.deleteStudentGroup(deleteTarget.value.id)
    toast.success("Student group removed.")
    deleteTarget.value = null
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to remove student group."))
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Student Groups</h1>
        <p class="text-sm text-gray-500 mt-1">
          Cohorts and class groups within programs
          <span v-if="!loading" class="ml-1 text-gray-400">({{ groups.length }})</span>
        </p>
      </div>
      <button class="btn-primary flex items-center gap-2" @click="openCreate">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        Add Group
      </button>
    </div>

    <!-- Create / Edit form -->
    <div v-if="showForm" class="card space-y-4 border-blue-100 bg-blue-50/40">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-gray-900">{{ editTarget ? "Edit Student Group" : "New Student Group" }}</h2>
        <button @click="showForm = false" class="text-gray-400 hover:text-gray-600">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div class="grid md:grid-cols-2 gap-3">
        <div>
          <label class="label">Group Name *</label>
          <input v-model="form.name" class="input" placeholder="BCS Year 1 Group A" />
        </div>
        <div>
          <label class="label">Code *</label>
          <input v-model="form.code" class="input" placeholder="BCS-Y1-A" />
        </div>
        <div>
          <label class="label">Program *</label>
          <select v-model="form.program_id" class="input">
            <option value="">Select program</option>
            <option v-for="p in programs" :key="p.id" :value="p.id">{{ p.name }} ({{ p.code }})</option>
          </select>
        </div>
        <div>
          <label class="label">Student Count</label>
          <input v-model.number="form.student_count" type="number" min="1" class="input" />
        </div>
        <div>
          <label class="label">Year of Study</label>
          <input v-model.number="form.year_of_study" type="number" min="1" max="6" class="input" />
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
      <p class="text-sm text-red-800 font-medium">Remove <strong>{{ deleteTarget.name }}</strong>?</p>
      <div class="flex gap-2">
        <button class="btn-danger text-sm" @click="confirmDelete">Yes, remove</button>
        <button class="btn-secondary text-sm" @click="deleteTarget = null">Cancel</button>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3">
      <input v-model="search" class="input flex-1 min-w-[150px] max-w-xs" placeholder="Search groups…" />
      <select v-model="filterProgram" class="input w-auto">
        <option value="">All Programs</option>
        <option v-for="p in programs" :key="p.id" :value="p.id">{{ p.name }} ({{ p.code }})</option>
      </select>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="card divide-y divide-gray-100">
      <div v-for="i in 8" :key="i" class="py-3 flex items-center gap-4 animate-pulse">
        <div class="w-9 h-9 bg-gray-200 rounded-lg flex-shrink-0"></div>
        <div class="flex-1 space-y-2">
          <div class="h-4 bg-gray-200 rounded w-2/5"></div>
          <div class="h-3 bg-gray-200 rounded w-1/3"></div>
        </div>
        <div class="w-12 h-5 bg-gray-200 rounded"></div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!groups.length" class="card text-center py-14">
      <div class="w-14 h-14 mx-auto bg-green-50 rounded-2xl flex items-center justify-center mb-3">
        <svg class="w-7 h-7 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
        </svg>
      </div>
      <h3 class="font-semibold text-gray-900 mb-1">No student groups yet</h3>
      <p class="text-sm text-gray-500 mb-5">Create programs first, then add student groups to them.</p>
      <button class="btn-primary" @click="openCreate">Add Group</button>
    </div>

    <!-- No filter results -->
    <div v-else-if="!filtered.length" class="card text-center py-8 text-sm text-gray-500">
      No groups match your filters.
      <button class="text-blue-600 hover:underline ml-1" @click="search = ''; filterProgram = ''">Clear</button>
    </div>

    <!-- Group list -->
    <div v-else class="card divide-y divide-gray-100">
      <div
        v-for="g in filtered"
        :key="g.id"
        class="flex items-center gap-4 py-3 -mx-6 px-6 hover:bg-gray-50 transition-colors"
        :class="deleteTarget?.id === g.id ? 'bg-red-50' : ''"
      >
        <div class="w-9 h-9 rounded-lg bg-green-100 flex items-center justify-center flex-shrink-0">
          <svg class="w-4.5 h-4.5 text-green-600" style="width:1.1rem;height:1.1rem" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75">
            <path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </div>

        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <p class="font-semibold text-gray-900">{{ g.name }}</p>
            <span class="text-xs text-gray-400 font-mono">{{ g.code }}</span>
          </div>
          <div class="flex items-center gap-2 text-xs text-gray-500 mt-0.5 flex-wrap">
            <span>{{ g.program?.name || programs.find(p => p.id === g.program_id)?.name || "—" }}</span>
            <span>·</span>
            <span class="px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded font-medium">Yr {{ g.year_of_study }}</span>
            <span>· {{ g.student_count }} students</span>
          </div>
        </div>

        <div class="flex gap-1 flex-shrink-0">
          <button class="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" @click="openEdit(g)">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
          <button class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg" @click="deleteTarget = g; showForm = false">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
