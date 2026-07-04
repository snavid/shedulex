<script setup>
import { onMounted, ref, computed, watch } from "vue"
import { usersApi, resourcesApi, getErrorMessage, validatePhone, isInvalidStoredPhone } from "@/api/client"
import { useAuthStore } from "@/stores/auth"
import { useToast } from "vue-toastification"

const auth = useAuthStore()
const toast = useToast()
const loading = ref(true)
const users = ref([])
const pendingUsers = ref([])
const roles = ref([])
const activeTab = ref("all")  // "all" | "pending"
const showContactModal = ref(false)
const contactSaving = ref(false)
const contactForm = ref({ userId: "", name: "", email: "", phone: "", phoneInvalidHint: "" })

const showAddStudentModal = ref(false)
const addingStudent = ref(false)
const departments = ref([])
const programs = ref([])
const studentGroups = ref([])
const universityCode = ref("")
const studentForm = ref({
  first_name: "",
  last_name: "",
  registration_number: "",
  phone: "",
  email: "",
  department_id: "",
  program_id: "",
  student_group_id: "",
})

const portalLink = computed(() => {
  if (!universityCode.value) return ""
  const base = window.location.origin
  return `${base}/p/${universityCode.value.toLowerCase()}`
})

const pendingCount = computed(() => pendingUsers.value.length)

async function loadData() {
  loading.value = true
  try {
    const [usersRes, rolesRes, pendingRes] = await Promise.all([
      usersApi.list({ per_page: 100 }),
      usersApi.roles(),
      usersApi.list({ pending: "true", per_page: 100 }),
    ])
    users.value = (usersRes.data.data || []).filter(u => u.is_approved)
    pendingUsers.value = pendingRes.data.data || []
    roles.value = rolesRes.data.data || []
    await loadUniversityCode()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load users."))
  } finally {
    loading.value = false
  }
}

async function loadUniversityCode() {
  const uniId = auth.user?.university_id
  if (!uniId) return
  try {
    const { data } = await resourcesApi.universities()
    const uni = (data.data || []).find((u) => u.id === uniId)
    universityCode.value = uni?.code || ""
  } catch {}
}

watch(() => studentForm.value.department_id, async (deptId) => {
  programs.value = []
  studentGroups.value = []
  studentForm.value.program_id = ""
  studentForm.value.student_group_id = ""
  if (!deptId) return
  try {
    const { data } = await resourcesApi.programs({ department_id: deptId })
    programs.value = data.data || []
  } catch {}
})

watch(() => studentForm.value.program_id, async (progId) => {
  studentGroups.value = []
  studentForm.value.student_group_id = ""
  if (!progId) return
  try {
    const { data } = await resourcesApi.studentGroups({ program_id: progId })
    studentGroups.value = data.data || []
  } catch {}
})

function openAddStudentModal() {
  studentForm.value = {
    first_name: "",
    last_name: "",
    registration_number: "",
    phone: "",
    email: "",
    department_id: "",
    program_id: "",
    student_group_id: "",
  }
  showAddStudentModal.value = true
  if (auth.user?.university_id && !departments.value.length) {
    resourcesApi.departments({ university_id: auth.user.university_id })
      .then(({ data }) => { departments.value = data.data || [] })
      .catch(() => {})
  }
}

function closeAddStudentModal() {
  showAddStudentModal.value = false
}

async function submitStudent() {
  const f = studentForm.value
  if (!f.first_name || !f.last_name || !f.registration_number || !f.phone) {
    toast.error("Name, registration number, and phone are required.")
    return
  }
  if (!f.department_id || !f.program_id || !f.student_group_id) {
    toast.error("Select department, program, and student group.")
    return
  }
  const phoneError = validatePhone(f.phone)
  if (phoneError) {
    toast.error(phoneError)
    return
  }
  addingStudent.value = true
  try {
    await usersApi.createStudent({
      first_name: f.first_name.trim(),
      last_name: f.last_name.trim(),
      registration_number: f.registration_number.trim(),
      phone: f.phone.trim(),
      email: f.email?.trim() || undefined,
      department_id: f.department_id,
      program_id: f.program_id,
      student_group_id: f.student_group_id,
    })
    toast.success("Student enrolled. Share the portal link so they can sign in.")
    closeAddStudentModal()
    await loadData()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to add student."))
  } finally {
    addingStudent.value = false
  }
}

async function copyPortalLink() {
  if (!portalLink.value) {
    toast.error("University code not available.")
    return
  }
  try {
    await navigator.clipboard.writeText(portalLink.value)
    toast.success("Portal link copied.")
  } catch {
    toast.info(portalLink.value)
  }
}

async function toggleUser(userId) {
  try {
    await usersApi.toggleActivation(userId)
    toast.success("User status changed.")
    await loadData()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to change user status."))
  }
}

async function updateRole(userId, roleName) {
  try {
    await usersApi.changeRole(userId, roleName)
    toast.success("Role updated.")
    await loadData()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to update role."))
  }
}

async function approveUser(userId, name) {
  try {
    await usersApi.approveUser(userId)
    toast.success(`${name} approved and activated.`)
    await loadData()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to approve user."))
  }
}

async function rejectUser(userId, name) {
  if (!window.confirm(`Reject registration for ${name}? They will not be able to log in.`)) return
  try {
    await usersApi.rejectUser(userId)
    toast.success(`${name}'s registration rejected.`)
    await loadData()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to reject user."))
  }
}

function roleBadgeClass(roleName) {
  const map = {
    admin: "bg-red-100 text-red-700",
    timetable_officer: "bg-blue-100 text-blue-700",
    hod: "bg-indigo-100 text-indigo-700",
    lecturer: "bg-green-100 text-green-700",
    student: "bg-gray-100 text-gray-600",
  }
  return map[roleName] || "bg-gray-100 text-gray-600"
}

function openContactModal(user) {
  const storedPhone = user.phone || ""
  const invalidPhone = isInvalidStoredPhone(storedPhone)
  contactForm.value = {
    userId: user.id,
    name: `${user.first_name} ${user.last_name}`,
    email: user.email || "",
    phone: invalidPhone ? "" : storedPhone,
    phoneInvalidHint: invalidPhone ? "Previous phone value was invalid — enter a valid number." : "",
  }
  showContactModal.value = true
}

function closeContactModal() {
  showContactModal.value = false
}

async function saveContact() {
  if (!contactForm.value.email?.trim()) {
    toast.error("Email is required for notifications.")
    return
  }
  const phoneError = validatePhone(contactForm.value.phone)
  if (phoneError) {
    toast.error(phoneError)
    return
  }
  contactSaving.value = true
  try {
    await usersApi.update(contactForm.value.userId, {
      email: contactForm.value.email.trim(),
      phone: contactForm.value.phone.trim(),
    })
    toast.success("Contact details updated.")
    closeContactModal()
    await loadData()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to update contact details."))
  } finally {
    contactSaving.value = false
  }
}

function phoneLabel(phone) {
  return phone && !isInvalidStoredPhone(phone) ? phone : null
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-start justify-between gap-4 flex-wrap">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">User Administration</h1>
        <p class="text-sm text-gray-500 mt-1">Manage accounts, approve registrations, and assign roles.</p>
      </div>
      <button class="btn-primary text-sm" @click="openAddStudentModal">Add Student</button>
    </div>

    <!-- Portal link card -->
    <div v-if="portalLink" class="card bg-blue-50 border-blue-100 flex flex-col sm:flex-row sm:items-center gap-4">
      <div class="flex-1 min-w-0">
        <h2 class="font-semibold text-gray-900">Student Portal Link</h2>
        <p class="text-sm text-gray-600 mt-1">
          Share this link with students. They sign in with registration number + last 4 phone digits.
        </p>
        <code class="text-sm text-blue-800 break-all">{{ portalLink }}</code>
      </div>
      <button class="btn-secondary text-sm flex-shrink-0" @click="copyPortalLink">Copy link</button>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 p-1 bg-gray-100 rounded-xl w-fit">
      <button
        @click="activeTab = 'all'"
        :class="activeTab === 'all' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
        class="px-4 py-2 rounded-lg text-sm font-semibold transition-all"
      >
        All Users
        <span v-if="!loading" class="ml-1.5 text-xs text-gray-400">({{ users.length }})</span>
      </button>
      <button
        @click="activeTab = 'pending'"
        :class="activeTab === 'pending' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
        class="px-4 py-2 rounded-lg text-sm font-semibold transition-all relative"
      >
        Pending Approval
        <span
          v-if="pendingCount > 0"
          class="ml-1.5 inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full bg-amber-500 text-white text-xs font-bold"
        >{{ pendingCount }}</span>
        <span v-else-if="!loading" class="ml-1.5 text-xs text-gray-400">(0)</span>
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="card">
      <div class="space-y-3">
        <div v-for="i in 5" :key="i" class="h-16 bg-gray-100 rounded-lg animate-pulse"></div>
      </div>
    </div>

    <!-- Pending Approvals tab -->
    <div v-else-if="activeTab === 'pending'">
      <div v-if="!pendingUsers.length" class="card text-center py-14">
        <div class="w-12 h-12 mx-auto bg-green-50 rounded-2xl flex items-center justify-center mb-3">
          <svg class="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h3 class="font-semibold text-gray-900 mb-1">All clear!</h3>
        <p class="text-sm text-gray-500">No registrations pending approval.</p>
      </div>
      <div v-else class="space-y-3">
        <div
          v-for="u in pendingUsers"
          :key="u.id"
          class="card border-amber-100 bg-amber-50/30 flex flex-col sm:flex-row sm:items-center gap-4"
        >
          <div class="flex items-center gap-3 flex-1 min-w-0">
            <div class="w-10 h-10 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
              {{ (u.first_name?.[0] || "") + (u.last_name?.[0] || "") }}
            </div>
            <div class="min-w-0">
              <p class="font-semibold text-gray-900">{{ u.first_name }} {{ u.last_name }}</p>
              <p class="text-xs text-gray-500 truncate">{{ u.email }}</p>
              <p v-if="phoneLabel(u.phone)" class="text-xs text-gray-400 truncate">{{ phoneLabel(u.phone) }}</p>
              <span v-else class="inline-block mt-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">No phone</span>
              <span :class="roleBadgeClass(u.role?.name)" class="inline-block mt-1 text-xs font-semibold px-2 py-0.5 rounded-full capitalize">
                {{ (u.role?.name || "").replace(/_/g, " ") }}
              </span>
            </div>
          </div>
          <div class="flex gap-2 flex-shrink-0">
            <button
              class="btn-secondary text-sm py-2"
              @click="openContactModal(u)"
            >
              Edit contact
            </button>
            <button
              class="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm font-semibold transition-colors"
              @click="approveUser(u.id, `${u.first_name} ${u.last_name}`)"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Approve
            </button>
            <button
              class="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 text-sm font-semibold transition-colors"
              @click="rejectUser(u.id, `${u.first_name} ${u.last_name}`)"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
              Reject
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- All Users tab -->
    <div v-else class="card">
      <div v-if="!users.length" class="text-center py-10">
        <p class="text-sm text-gray-500">No approved users found.</p>
      </div>
      <div v-else class="space-y-2">
        <div
          v-for="u in users"
          :key="u.id"
          class="flex flex-col sm:flex-row sm:items-center gap-3 p-3 rounded-xl border border-gray-100 hover:border-gray-200 hover:bg-gray-50 transition-colors"
        >
          <div class="flex items-center gap-3 flex-1 min-w-0">
            <div class="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
              {{ (u.first_name?.[0] || "") + (u.last_name?.[0] || "") }}
            </div>
            <div class="min-w-0">
              <p class="font-medium text-gray-900 truncate">{{ u.first_name }} {{ u.last_name }}</p>
              <p class="text-xs text-gray-500 truncate">{{ u.email }}</p>
              <p v-if="phoneLabel(u.phone)" class="text-xs text-gray-400 truncate">{{ phoneLabel(u.phone) }}</p>
              <span v-else class="inline-block mt-0.5 text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">No phone</span>
            </div>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0 flex-wrap">
            <span
              :class="u.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
              class="text-xs font-semibold px-2 py-0.5 rounded-full"
            >
              {{ u.is_active ? "Active" : "Inactive" }}
            </span>
            <button class="btn-secondary text-sm py-1.5" @click="openContactModal(u)">
              Edit contact
            </button>
            <select
              class="input !w-auto text-sm py-1.5"
              :value="u.role?.name"
              @change="updateRole(u.id, $event.target.value)"
            >
              <option v-for="r in roles" :key="r.id" :value="r.name">{{ r.name }}</option>
            </select>
            <button class="btn-secondary text-sm py-1.5" @click="toggleUser(u.id)">
              {{ u.is_active ? "Deactivate" : "Activate" }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Edit contact modal -->
    <div
      v-if="showContactModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      @click.self="closeContactModal"
    >
      <div class="card w-full max-w-md space-y-4">
        <div>
          <h2 class="text-lg font-semibold text-gray-900">Edit contact</h2>
          <p class="text-sm text-gray-500 mt-1">{{ contactForm.name }}</p>
        </div>
        <div>
          <label class="label">Email *</label>
          <input v-model="contactForm.email" type="email" required class="input" placeholder="user@university.ac" />
        </div>
        <div>
          <label class="label">Phone *</label>
          <input v-model="contactForm.phone" required class="input" placeholder="+255700000000" />
          <p v-if="contactForm.phoneInvalidHint" class="text-xs text-amber-600 mt-1">{{ contactForm.phoneInvalidHint }}</p>
        </div>
        <div class="flex justify-end gap-2">
          <button class="btn-secondary" :disabled="contactSaving" @click="closeContactModal">Cancel</button>
          <button class="btn-primary" :disabled="contactSaving" @click="saveContact">
            {{ contactSaving ? "Saving..." : "Save" }}
          </button>
        </div>
      </div>
    </div>

    <!-- Add student modal -->
    <div
      v-if="showAddStudentModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      @click.self="closeAddStudentModal"
    >
      <div class="card w-full max-w-lg max-h-[90vh] overflow-y-auto space-y-4">
        <div>
          <h2 class="text-lg font-semibold text-gray-900">Add Student</h2>
          <p class="text-sm text-gray-500 mt-1">Enroll a student for portal access and class notifications.</p>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="label">First name</label>
            <input v-model="studentForm.first_name" class="input" />
          </div>
          <div>
            <label class="label">Last name</label>
            <input v-model="studentForm.last_name" class="input" />
          </div>
        </div>
        <div>
          <label class="label">Registration number</label>
          <input v-model="studentForm.registration_number" class="input" placeholder="REG2026001" />
        </div>
        <div>
          <label class="label">Phone *</label>
          <input v-model="studentForm.phone" class="input" placeholder="+255749300606" />
        </div>
        <div>
          <label class="label">Email (optional)</label>
          <input v-model="studentForm.email" type="email" class="input" />
        </div>
        <div>
          <label class="label">Department</label>
          <select v-model="studentForm.department_id" class="input">
            <option value="">Select department…</option>
            <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
        </div>
        <div>
          <label class="label">Program</label>
          <select v-model="studentForm.program_id" class="input" :disabled="!studentForm.department_id">
            <option value="">Select program…</option>
            <option v-for="p in programs" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </div>
        <div>
          <label class="label">Student group</label>
          <select v-model="studentForm.student_group_id" class="input" :disabled="!studentForm.program_id">
            <option value="">Select group…</option>
            <option v-for="g in studentGroups" :key="g.id" :value="g.id">{{ g.name }}</option>
          </select>
        </div>
        <div class="flex justify-end gap-2">
          <button class="btn-secondary" :disabled="addingStudent" @click="closeAddStudentModal">Cancel</button>
          <button class="btn-primary" :disabled="addingStudent" @click="submitStudent">
            {{ addingStudent ? "Saving…" : "Add Student" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
