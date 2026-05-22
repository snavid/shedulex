<script setup>
import { onMounted, ref, computed } from "vue"
import { resourcesApi, usersApi } from "@/api/client"
import { useAuthStore } from "@/stores/auth"
import { useToast } from "vue-toastification"

const toast = useToast()
const auth = useAuthStore()
const loading = ref(true)
const lecturers = ref([])
const departments = ref([])
const programs = ref([])

// Whether to also create an auth account for the lecturer
const createAccount = ref(true)
const showCredentials = ref(null) // { username, default_password, name }

const form = ref({
  name: "",
  email: "",
  phone: "",
  staff_id: "",
  department_id: "",
  max_hours_per_week: 20,
  program_ids: [],
})

const canManage = ["admin", "timetable_officer", "hod"].includes(auth.user?.role?.name)

async function loadData() {
  loading.value = true
  try {
    const [lecRes, deptRes, progRes] = await Promise.all([
      resourcesApi.lecturers(),
      resourcesApi.departments(),
      resourcesApi.programs(),
    ])
    lecturers.value = lecRes.data.data || []
    departments.value = deptRes.data.data || []
    programs.value = progRes.data.data || []
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.value = {
    name: "", email: "", phone: "", staff_id: "",
    department_id: "", max_hours_per_week: 20, program_ids: [],
  }
}

async function createLecturer() {
  if (!form.value.name || !form.value.email) {
    toast.error("Name and email are required.")
    return
  }

  try {
    // 1. Always create the timetable-service lecturer record
    await resourcesApi.createLecturer({ ...form.value })

    // 2. Optionally create an auth account (sends credentials by email)
    if (createAccount.value) {
      const nameParts = form.value.name.trim().split(" ")
      const first = nameParts[0]
      const last = nameParts.slice(1).join(" ") || first

      const { data } = await usersApi.createLecturer({
        email: form.value.email,
        first_name: first,
        last_name: last,
        phone: form.value.phone,
        staff_id: form.value.staff_id,
        department: departments.value.find((d) => d.id === form.value.department_id)?.name,
      })

      showCredentials.value = {
        name: data.data.first_name + " " + data.data.last_name,
        username: data.data.username,
        default_password: data.data.default_password,
        email: data.data.email,
      }
    }

    toast.success("Lecturer created successfully. Credentials emailed.")
    resetForm()
    await loadData()
  } catch (e) {
    toast.error(e?.response?.data?.message || "Failed to create lecturer.")
  }
}

async function resend(userId, lecturerName) {
  if (!userId) {
    toast.error("No linked user account for this lecturer.")
    return
  }
  try {
    const { data } = await usersApi.resendCredentials(userId)
    showCredentials.value = {
      name: lecturerName,
      username: data.data.username,
      default_password: data.data.default_password,
      email: data.data.email,
    }
    toast.success("New credentials generated and emailed.")
  } catch (e) {
    toast.error(e?.response?.data?.message || "Failed to resend credentials.")
  }
}

const deleteTarget = ref(null)
const search = ref("")

const filtered = computed(() => {
  const q = search.value.toLowerCase()
  return q
    ? lecturers.value.filter(
        (l) =>
          l.name.toLowerCase().includes(q) ||
          l.email.toLowerCase().includes(q) ||
          (l.staff_id || "").toLowerCase().includes(q),
      )
    : lecturers.value
})

async function confirmDeactivate() {
  if (!deleteTarget.value) return
  try {
    await resourcesApi.deleteLecturer(deleteTarget.value.id)
    toast.success("Lecturer deactivated.")
    deleteTarget.value = null
    await loadData()
  } catch (e) {
    toast.error(e?.response?.data?.message || "Failed to deactivate.")
  }
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Lecturers</h1>
      <p class="text-sm text-gray-500 mt-1">Academic staff profiles, workload caps, and account management.</p>
    </div>

    <!-- Credentials flash panel -->
    <div v-if="showCredentials" class="card border-green-200 bg-green-50 space-y-3">
      <div class="flex items-start justify-between">
        <h3 class="font-semibold text-green-900">Account Created — Default Credentials</h3>
        <button @click="showCredentials = null" class="text-green-700 hover:text-green-900 text-xl leading-none">&times;</button>
      </div>
      <p class="text-xs text-green-700">These credentials have been emailed to {{ showCredentials.email }}. The lecturer must change their password on first login.</p>
      <div class="bg-white rounded-lg border border-green-200 p-4 font-mono text-sm space-y-1">
        <div class="flex gap-4"><span class="text-gray-500 min-w-[100px]">Name:</span><span class="font-semibold">{{ showCredentials.name }}</span></div>
        <div class="flex gap-4"><span class="text-gray-500 min-w-[100px]">Username:</span><span class="font-semibold">{{ showCredentials.username }}</span></div>
        <div class="flex gap-4"><span class="text-gray-500 min-w-[100px]">Password:</span><span class="font-semibold text-red-700">{{ showCredentials.default_password }}</span></div>
      </div>
      <p class="text-xs text-gray-500">This panel will not appear again. Save the credentials if needed.</p>
    </div>

    <!-- Create Form -->
    <div v-if="canManage" class="card space-y-4">
      <h2 class="font-semibold">Add Lecturer</h2>
      <div class="grid md:grid-cols-2 gap-3">
        <div>
          <label class="label">Full Name *</label>
          <input v-model="form.name" class="input" placeholder="Dr. Jane Smith" />
        </div>
        <div>
          <label class="label">Email *</label>
          <input v-model="form.email" type="email" class="input" placeholder="j.smith@university.ac.ke" />
        </div>
        <div>
          <label class="label">Phone</label>
          <input v-model="form.phone" class="input" placeholder="+254 700 000 000" />
        </div>
        <div>
          <label class="label">Staff ID</label>
          <input v-model="form.staff_id" class="input" placeholder="ST/2024/001" />
        </div>
        <div>
          <label class="label">Department</label>
          <select v-model="form.department_id" class="input">
            <option value="">Select department</option>
            <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
        </div>
        <div>
          <label class="label">Max Hours / Week</label>
          <input v-model.number="form.max_hours_per_week" type="number" min="1" max="40" class="input" />
        </div>
        <div class="md:col-span-2">
          <label class="label">Programs (multi-select)</label>
          <select v-model="form.program_ids" multiple class="input h-24 text-sm">
            <option v-for="p in programs" :key="p.id" :value="p.id">{{ p.name }} ({{ p.code }})</option>
          </select>
          <p class="text-xs text-gray-400 mt-1">Hold Ctrl/Cmd to select multiple programs.</p>
        </div>
      </div>
      <label class="flex items-center gap-2 text-sm cursor-pointer">
        <input v-model="createAccount" type="checkbox" />
        <span>Create auth account &amp; send credentials by email</span>
      </label>
      <button class="btn-primary" @click="createLecturer">Add Lecturer</button>
    </div>

    <!-- Deactivate confirmation -->
    <div v-if="deleteTarget" class="card border-red-200 bg-red-50 space-y-3">
      <p class="text-sm text-red-800 font-medium">Deactivate <strong>{{ deleteTarget.name }}</strong>?</p>
      <p class="text-xs text-red-600">Their timetable entries will remain. Auth account is unaffected.</p>
      <div class="flex gap-2">
        <button class="btn-danger text-sm" @click="confirmDeactivate">Yes, deactivate</button>
        <button class="btn-secondary text-sm" @click="deleteTarget = null">Cancel</button>
      </div>
    </div>

    <!-- Search -->
    <div>
      <input v-model="search" class="input max-w-sm" placeholder="Search by name, email or staff ID…" />
    </div>

    <!-- List -->
    <div class="card">
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-semibold text-gray-900">All Lecturers <span v-if="!loading" class="text-gray-400 font-normal text-sm">({{ lecturers.length }})</span></h2>
      </div>

      <!-- Loading skeleton -->
      <div v-if="loading" class="space-y-3">
        <div v-for="i in 5" :key="i" class="flex items-center gap-4 animate-pulse">
          <div class="w-10 h-10 bg-gray-200 rounded-full flex-shrink-0"></div>
          <div class="flex-1 space-y-2">
            <div class="h-4 bg-gray-200 rounded w-1/3"></div>
            <div class="h-3 bg-gray-200 rounded w-1/2"></div>
          </div>
          <div class="w-24 h-7 bg-gray-200 rounded-lg"></div>
        </div>
      </div>

      <div v-else-if="!lecturers.length" class="text-center py-12">
        <div class="w-12 h-12 mx-auto bg-purple-50 rounded-xl flex items-center justify-center mb-3">
          <svg class="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
          </svg>
        </div>
        <p class="font-medium text-gray-900 mb-1">No lecturers yet</p>
        <p class="text-sm text-gray-500">Add lecturers using the form above.</p>
      </div>

      <div v-else-if="!filtered.length" class="text-center py-8 text-sm text-gray-500">
        No lecturers match "<strong>{{ search }}</strong>".
        <button class="text-blue-600 hover:underline ml-1" @click="search = ''">Clear</button>
      </div>

      <div v-else class="divide-y divide-gray-100 -mx-6">
        <div
          v-for="l in filtered"
          :key="l.id"
          class="flex flex-wrap items-center gap-4 px-6 py-4 hover:bg-gray-50 transition-colors"
          :class="deleteTarget?.id === l.id ? 'bg-red-50' : ''"
        >
          <!-- Avatar -->
          <div class="w-10 h-10 rounded-full bg-gradient-to-br from-purple-400 to-indigo-500 flex items-center justify-center text-white text-sm font-semibold flex-shrink-0 select-none">
            {{ l.name.split(" ").slice(0, 2).map(w => w[0]).join("").toUpperCase() }}
          </div>

          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <p class="font-semibold text-gray-900">{{ l.name }}</p>
              <span v-if="l.user_id" class="px-1.5 py-0.5 rounded text-xs bg-green-100 text-green-700 font-medium">Account</span>
            </div>
            <p class="text-xs text-gray-500 mt-0.5">
              {{ l.email }}<span v-if="l.phone"> · {{ l.phone }}</span><span v-if="l.staff_id"> · {{ l.staff_id }}</span>
            </p>
            <p class="text-xs text-gray-400 mt-0.5">
              {{ l.department?.name || "No dept" }} · Max {{ l.max_hours_per_week }}h/wk<span v-if="l.program_ids?.length"> · {{ l.program_ids.length }} program(s)</span>
            </p>
          </div>

          <div v-if="canManage" class="flex flex-wrap gap-2 shrink-0">
            <button
              v-if="l.user_id"
              class="btn-secondary text-xs"
              @click="resend(l.user_id, l.name)"
            >Resend Credentials</button>
            <button class="btn-danger text-xs" @click="deleteTarget = l">Deactivate</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
