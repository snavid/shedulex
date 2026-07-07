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

const createAccount = ref(true)
const showCredentials = ref(null)

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

function blankForm() {
  return {
    name: "", email: "", phone: "", staff_id: "",
    department_id: "", specialization: "",
    max_hours_per_week: 20, max_hours_per_day: 6, max_consecutive_hours: 3,
    preferred_days: [],
    program_ids: [],
  }
}

const form = ref(blankForm())

// Edit modal
const editTarget = ref(null)
const editForm = ref(blankForm())
const editSaving = ref(false)
const showAdvanced = ref(false)
const showEditAdvanced = ref(false)

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

async function createLecturer() {
  if (!form.value.name || !form.value.email) {
    toast.error("Name and email are required.")
    return
  }

  try {
    await resourcesApi.createLecturer({ ...form.value })

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

    toast.success("Lecturer created successfully.")
    form.value = blankForm()
    showAdvanced.value = false
    await loadData()
  } catch (e) {
    toast.error(e?.response?.data?.message || "Failed to create lecturer.")
  }
}

function openEdit(l) {
  editTarget.value = l
  editForm.value = {
    name: l.name || "",
    email: l.email || "",
    phone: l.phone || "",
    staff_id: l.staff_id || "",
    department_id: l.department_id || l.department?.id || "",
    specialization: l.specialization || "",
    max_hours_per_week: l.max_hours_per_week || 20,
    max_hours_per_day: l.max_hours_per_day || 6,
    max_consecutive_hours: l.max_consecutive_hours || 3,
    preferred_days: l.preferred_days || [],
    program_ids: l.program_ids || [],
  }
  showEditAdvanced.value = false
}

async function saveEdit() {
  if (!editTarget.value) return
  editSaving.value = true
  try {
    await resourcesApi.updateLecturer(editTarget.value.id, { ...editForm.value })
    toast.success("Lecturer updated.")
    editTarget.value = null
    await loadData()
  } catch (e) {
    toast.error(e?.response?.data?.message || "Failed to update lecturer.")
  } finally {
    editSaving.value = false
  }
}

async function resend(userId, lecturerName) {
  if (!userId) { toast.error("No linked user account."); return }
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

const registerLink = ref(null)
const generatingInvite = ref(null)

async function generateInvite(l) {
  generatingInvite.value = l.id
  try {
    const { data } = await usersApi.createLecturerInvite({
      lecturer_id: l.id,
      name: l.name,
      email: l.email,
      phone: l.phone,
      department: l.department?.name,
      university_id: l.department?.university_id,
    })
    registerLink.value = { name: l.name, url: data.data.invite_url }
    window.open(data.data.invite_url, "_blank")
  } catch (e) {
    toast.error(e?.response?.data?.message || "Failed to generate registration link.")
  } finally {
    generatingInvite.value = null
  }
}

async function copyRegisterLink() {
  try {
    await navigator.clipboard.writeText(registerLink.value.url)
    toast.success("Link copied.")
  } catch {
    toast.error("Could not copy — select and copy the link manually.")
  }
}

const deleteTarget = ref(null)
const search = ref("")
const deptFilter = ref("")

const filtered = computed(() => {
  let list = lecturers.value
  if (deptFilter.value) list = list.filter((l) => (l.department_id || l.department?.id) === deptFilter.value)
  const q = search.value.toLowerCase()
  if (q) {
    list = list.filter(
      (l) => l.name.toLowerCase().includes(q) || l.email.toLowerCase().includes(q) || (l.staff_id || "").toLowerCase().includes(q),
    )
  }
  return list
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
      <p class="text-sm text-gray-500 mt-1">Academic staff profiles, workload caps, preferred schedules, and account management.</p>
    </div>

    <!-- Credentials flash panel -->
    <div v-if="showCredentials" class="card border-green-200 bg-green-50 space-y-3">
      <div class="flex items-start justify-between">
        <h3 class="font-semibold text-green-900">Account Created — Default Credentials</h3>
        <button @click="showCredentials = null" class="text-green-700 hover:text-green-900 text-xl leading-none">&times;</button>
      </div>
      <p class="text-xs text-green-700">Emailed to {{ showCredentials.email }}. Lecturer must change password on first login.</p>
      <div class="bg-white rounded-lg border border-green-200 p-4 font-mono text-sm space-y-1">
        <div class="flex gap-4"><span class="text-gray-500 min-w-[100px]">Name:</span><span class="font-semibold">{{ showCredentials.name }}</span></div>
        <div class="flex gap-4"><span class="text-gray-500 min-w-[100px]">Username:</span><span class="font-semibold">{{ showCredentials.username }}</span></div>
        <div class="flex gap-4"><span class="text-gray-500 min-w-[100px]">Password:</span><span class="font-semibold text-red-700">{{ showCredentials.default_password }}</span></div>
      </div>
    </div>

    <!-- Register link flash panel -->
    <div v-if="registerLink" class="card border-blue-200 bg-blue-50 space-y-3">
      <div class="flex items-start justify-between">
        <h3 class="font-semibold text-blue-900">Registration Link — {{ registerLink.name }}</h3>
        <button @click="registerLink = null" class="text-blue-700 hover:text-blue-900 text-xl leading-none">&times;</button>
      </div>
      <p class="text-xs text-blue-700">
        Opened in a new tab. Share this link with {{ registerLink.name }} so they can set their own password —
        it expires in 14 days and only works once.
      </p>
      <div class="flex items-center gap-2 bg-white rounded-lg border border-blue-200 p-3">
        <input :value="registerLink.url" readonly class="input flex-1 font-mono text-xs" @click="$event.target.select()" />
        <button class="btn-secondary text-xs shrink-0" @click="copyRegisterLink">Copy</button>
        <a :href="registerLink.url" target="_blank" rel="noopener" class="btn-primary text-xs shrink-0">Open</a>
      </div>
    </div>

    <!-- ── Create Form ────────────────────────────────────────────────────────── -->
    <div v-if="canManage" class="card space-y-4">
      <h2 class="font-semibold">Add Lecturer</h2>

      <!-- Core fields -->
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
          <label class="label">Specialization</label>
          <input v-model="form.specialization" class="input" placeholder="e.g. Networking, AI, Databases" />
        </div>
      </div>

      <!-- Advanced toggle -->
      <button
        @click="showAdvanced = !showAdvanced"
        class="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium"
      >
        <svg class="w-4 h-4 transition-transform" :class="showAdvanced ? 'rotate-90' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
        </svg>
        {{ showAdvanced ? "Hide" : "Show" }} preferences &amp; workload limits
      </button>

      <!-- Advanced fields -->
      <div v-if="showAdvanced" class="border border-blue-100 bg-blue-50/40 rounded-xl p-4 space-y-4">
        <div class="grid md:grid-cols-3 gap-3">
          <div>
            <label class="label">Max Hours / Week</label>
            <input v-model.number="form.max_hours_per_week" type="number" min="1" max="40" class="input" />
          </div>
          <div>
            <label class="label">Max Hours / Day</label>
            <input v-model.number="form.max_hours_per_day" type="number" min="1" max="12" class="input" />
          </div>
          <div>
            <label class="label">Max Consecutive Hours</label>
            <input v-model.number="form.max_consecutive_hours" type="number" min="1" max="6" class="input" />
          </div>
        </div>

        <div>
          <label class="label">Preferred Teaching Days</label>
          <p class="text-xs text-gray-500 mb-2">The GA will try to schedule this lecturer on selected days (soft preference).</p>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="day in DAYS"
              :key="day"
              type="button"
              @click="form.preferred_days.includes(day) ? form.preferred_days.splice(form.preferred_days.indexOf(day), 1) : form.preferred_days.push(day)"
              :class="[
                'px-3 py-1.5 rounded-full text-sm font-medium border transition-all',
                form.preferred_days.includes(day)
                  ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                  : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400',
              ]"
            >
              {{ day.slice(0, 3) }}
            </button>
          </div>
          <p v-if="form.preferred_days.length" class="text-xs text-blue-600 mt-1.5">
            Preferred: {{ form.preferred_days.join(", ") }}
          </p>
        </div>

        <div class="md:col-span-2">
          <label class="label">Programs</label>
          <select v-model="form.program_ids" multiple class="input h-24 text-sm">
            <option v-for="p in programs" :key="p.id" :value="p.id">{{ p.name }} ({{ p.code }})</option>
          </select>
          <p class="text-xs text-gray-400 mt-1">Hold Ctrl/Cmd to select multiple.</p>
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
      <p class="text-xs text-red-600">Timetable entries will remain. Auth account is unaffected.</p>
      <div class="flex gap-2">
        <button class="btn-danger text-sm" @click="confirmDeactivate">Yes, deactivate</button>
        <button class="btn-secondary text-sm" @click="deleteTarget = null">Cancel</button>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3">
      <input v-model="search" class="input max-w-sm" placeholder="Search by name, email or staff ID…" />
      <select v-model="deptFilter" class="input w-auto">
        <option value="">All departments</option>
        <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
      </select>
    </div>

    <!-- List -->
    <div class="card">
      <div class="flex items-center justify-between mb-4">
        <h2 class="font-semibold text-gray-900">
          All Lecturers
          <span v-if="!loading" class="text-gray-400 font-normal text-sm">({{ lecturers.length }})</span>
        </h2>
      </div>

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
        No lecturers match your filters.
        <button class="text-blue-600 hover:underline ml-1" @click="search = ''; deptFilter = ''">Clear</button>
      </div>

      <div v-else class="divide-y divide-gray-100 -mx-6">
        <div
          v-for="l in filtered"
          :key="l.id"
          class="flex flex-wrap items-center gap-4 px-6 py-4 hover:bg-gray-50 transition-colors"
          :class="deleteTarget?.id === l.id ? 'bg-red-50' : ''"
        >
          <div class="w-10 h-10 rounded-full bg-gradient-to-br from-purple-400 to-indigo-500 flex items-center justify-center text-white text-sm font-semibold flex-shrink-0 select-none">
            {{ l.name.split(" ").slice(0, 2).map(w => w[0]).join("").toUpperCase() }}
          </div>

          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <p class="font-semibold text-gray-900">{{ l.name }}</p>
              <span v-if="l.user_id" class="px-1.5 py-0.5 rounded text-xs bg-green-100 text-green-700 font-medium">Account</span>
              <span v-if="l.specialization" class="px-1.5 py-0.5 rounded text-xs bg-blue-50 text-blue-600 font-medium">{{ l.specialization }}</span>
            </div>
            <p class="text-xs text-gray-500 mt-0.5">
              {{ l.email }}<span v-if="l.phone"> · {{ l.phone }}</span><span v-if="l.staff_id"> · {{ l.staff_id }}</span>
            </p>
            <div class="flex flex-wrap items-center gap-2 mt-1">
              <span class="text-xs text-gray-400">{{ l.department?.name || "No dept" }}</span>
              <span class="text-gray-200">·</span>
              <span class="text-xs text-gray-400">Max {{ l.max_hours_per_week }}h/wk</span>
              <template v-if="l.preferred_days?.length">
                <span class="text-gray-200">·</span>
                <div class="flex gap-1">
                  <span
                    v-for="d in l.preferred_days"
                    :key="d"
                    class="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700"
                  >{{ d.slice(0, 3) }}</span>
                </div>
              </template>
            </div>
          </div>

          <div v-if="canManage" class="flex flex-wrap gap-2 shrink-0">
            <button class="btn-secondary text-xs" @click="openEdit(l)">Edit</button>
            <button v-if="l.user_id" class="btn-secondary text-xs" @click="resend(l.user_id, l.name)">Resend Credentials</button>
            <button
              v-else
              class="btn-secondary text-xs"
              :disabled="generatingInvite === l.id"
              @click="generateInvite(l)"
            >
              {{ generatingInvite === l.id ? "Generating…" : "Register" }}
            </button>
            <button class="btn-danger text-xs" @click="deleteTarget = l">Deactivate</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- ── Edit Modal ─────────────────────────────────────────────────────────── -->
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="editTarget"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
        @click.self="editTarget = null"
      >
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-xl overflow-hidden max-h-[90vh] flex flex-col">
          <!-- Header -->
          <div class="bg-gradient-to-r from-purple-600 to-indigo-600 px-6 py-4 flex items-center justify-between flex-shrink-0">
            <div>
              <h2 class="text-white font-bold text-lg">Edit Lecturer</h2>
              <p class="text-white/70 text-sm">{{ editTarget.name }}</p>
            </div>
            <button @click="editTarget = null" class="text-white/70 hover:text-white text-2xl leading-none">×</button>
          </div>

          <div class="overflow-y-auto p-6 space-y-4 flex-1">
            <!-- Core -->
            <div class="grid md:grid-cols-2 gap-3">
              <div>
                <label class="label">Full Name *</label>
                <input v-model="editForm.name" class="input" />
              </div>
              <div>
                <label class="label">Email *</label>
                <input v-model="editForm.email" type="email" class="input" />
              </div>
              <div>
                <label class="label">Phone</label>
                <input v-model="editForm.phone" class="input" />
              </div>
              <div>
                <label class="label">Staff ID</label>
                <input v-model="editForm.staff_id" class="input" />
              </div>
              <div>
                <label class="label">Department</label>
                <select v-model="editForm.department_id" class="input">
                  <option value="">Select department</option>
                  <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
                </select>
              </div>
              <div>
                <label class="label">Specialization</label>
                <input v-model="editForm.specialization" class="input" placeholder="e.g. Networking, AI" />
              </div>
            </div>

            <!-- Preferences -->
            <button
              @click="showEditAdvanced = !showEditAdvanced"
              class="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium"
            >
              <svg class="w-4 h-4 transition-transform" :class="showEditAdvanced ? 'rotate-90' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
              </svg>
              {{ showEditAdvanced ? "Hide" : "Show" }} preferences &amp; workload limits
            </button>

            <div v-if="showEditAdvanced" class="border border-blue-100 bg-blue-50/40 rounded-xl p-4 space-y-4">
              <div class="grid md:grid-cols-3 gap-3">
                <div>
                  <label class="label">Max Hours / Week</label>
                  <input v-model.number="editForm.max_hours_per_week" type="number" min="1" max="40" class="input" />
                </div>
                <div>
                  <label class="label">Max Hours / Day</label>
                  <input v-model.number="editForm.max_hours_per_day" type="number" min="1" max="12" class="input" />
                </div>
                <div>
                  <label class="label">Max Consecutive Hours</label>
                  <input v-model.number="editForm.max_consecutive_hours" type="number" min="1" max="6" class="input" />
                </div>
              </div>

              <div>
                <label class="label">Preferred Teaching Days</label>
                <p class="text-xs text-gray-500 mb-2">The GA uses these as soft constraints when generating the timetable.</p>
                <div class="flex flex-wrap gap-2">
                  <button
                    v-for="day in DAYS"
                    :key="day"
                    type="button"
                    @click="editForm.preferred_days.includes(day) ? editForm.preferred_days.splice(editForm.preferred_days.indexOf(day), 1) : editForm.preferred_days.push(day)"
                    :class="[
                      'px-3 py-1.5 rounded-full text-sm font-medium border transition-all',
                      editForm.preferred_days.includes(day)
                        ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                        : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400',
                    ]"
                  >
                    {{ day }}
                  </button>
                </div>
              </div>

              <div>
                <label class="label">Programs</label>
                <select v-model="editForm.program_ids" multiple class="input h-24 text-sm">
                  <option v-for="p in programs" :key="p.id" :value="p.id">{{ p.name }} ({{ p.code }})</option>
                </select>
                <p class="text-xs text-gray-400 mt-1">Hold Ctrl/Cmd to select multiple.</p>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="px-6 pb-5 flex justify-end gap-3 flex-shrink-0 border-t border-gray-100 pt-4">
            <button class="btn-secondary" @click="editTarget = null">Cancel</button>
            <button class="btn-primary" :disabled="editSaving" @click="saveEdit">
              {{ editSaving ? "Saving…" : "Save Changes" }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-fade-enter-active, .modal-fade-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.modal-fade-enter-from, .modal-fade-leave-to       { opacity: 0; transform: scale(0.97); }
</style>
