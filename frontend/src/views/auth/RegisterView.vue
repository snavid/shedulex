<script setup>
import { ref, computed, onMounted, watch } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "@/stores/auth"
import { useToast } from "vue-toastification"
import api, { resourcesApi } from "@/api/client"

const auth = useAuthStore()
const router = useRouter()
const toast = useToast()

const form = ref({
  email: "", username: "", password: "", first_name: "", last_name: "",
  phone: "", department: "", department_id: "", program_id: "", student_group_id: "",
  role_name: "timetable_officer",
  university_id: "", university_name: "", university_code: "",
})
const loading = ref(false)
const error = ref("")
const pendingApproval = ref(false)
const registeredName = ref("")

const uniMode = ref("select")
const universities = ref([])
const departments = ref([])
const programs = ref([])
const studentGroups = ref([])

const isAdmin = computed(() => form.value.role_name === "admin")
const isStudent = computed(() => form.value.role_name === "student")
const needsDepartment = computed(() => ["student", "hod", "lecturer"].includes(form.value.role_name))

onMounted(async () => {
  try {
    const { data } = await api.get("/universities")
    universities.value = data.data || []
    if (!universities.value.length) uniMode.value = "create"
  } catch {
    uniMode.value = "create"
  }
})

watch(() => form.value.university_id, async (uniId) => {
  departments.value = []
  programs.value = []
  studentGroups.value = []
  form.value.department_id = ""
  form.value.program_id = ""
  form.value.student_group_id = ""
  if (!uniId) return
  try {
    const { data } = await resourcesApi.departments({ university_id: uniId })
    departments.value = data.data || []
  } catch {}
})

watch(() => form.value.department_id, async (deptId) => {
  programs.value = []
  studentGroups.value = []
  form.value.program_id = ""
  form.value.student_group_id = ""
  if (!deptId) return
  const dept = departments.value.find(d => d.id === deptId)
  if (dept) form.value.department = dept.name
  try {
    const { data } = await resourcesApi.programs({ department_id: deptId })
    programs.value = data.data || []
  } catch {}
})

watch(() => form.value.program_id, async (progId) => {
  studentGroups.value = []
  form.value.student_group_id = ""
  if (!progId) return
  try {
    const { data } = await resourcesApi.studentGroups({ program_id: progId })
    studentGroups.value = data.data || []
  } catch {}
})

async function submit() {
  error.value = ""

  if (uniMode.value === "select" && !form.value.university_id) {
    error.value = "Please select your university."
    return
  }
  if (uniMode.value === "create" && (!form.value.university_name || !form.value.university_code)) {
    error.value = "University name and code are required."
    return
  }
  if (isStudent.value && !form.value.program_id) {
    error.value = "Please select your program."
    return
  }
  if (needsDepartment.value && !form.value.department_id) {
    error.value = "Please select your department."
    return
  }
  if (!form.value.phone) {
    error.value = "Phone number is required."
    return
  }

  const payload = { ...form.value }
  if (uniMode.value === "select") {
    delete payload.university_name
    delete payload.university_code
  } else {
    delete payload.university_id
  }
  Object.keys(payload).forEach(k => { if (payload[k] === "") delete payload[k] })

  loading.value = true
  try {
    const result = await auth.register(payload)
    if (result.pending) {
      registeredName.value = form.value.first_name
      pendingApproval.value = true
    } else {
      toast.success("Account created! Welcome to Shedulex.")
      router.push("/dashboard")
    }
  } catch (e) {
    error.value = e.response?.data?.message || e.response?.data?.errors
      ? JSON.stringify(e.response?.data?.errors || e.response?.data?.message)
      : "Registration failed."
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 px-4 py-8">
    <div class="w-full max-w-lg">

      <div v-if="pendingApproval" class="bg-white rounded-2xl shadow-xl p-10 text-center">
        <div class="inline-flex items-center justify-center w-20 h-20 rounded-full bg-amber-100 text-amber-600 text-4xl mb-6">⏳</div>
        <h2 class="text-2xl font-bold text-gray-900 mb-2">Registration Submitted!</h2>
        <p class="text-gray-600 mb-4">
          Thanks{{ registeredName ? `, ${registeredName}` : "" }}. Your account is
          <span class="font-semibold text-amber-600">pending approval</span> by a university administrator.
        </p>
        <p class="text-sm text-gray-500 mb-8">
          You'll be able to log in once your account has been reviewed and activated. This usually takes less than 24 hours.
        </p>
        <RouterLink to="/login" class="btn-primary inline-block px-8">Back to Login</RouterLink>
      </div>

      <div v-else class="bg-white rounded-2xl shadow-xl p-8">
        <div class="text-center mb-8">
          <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-600 text-white text-3xl mb-4">📅</div>
          <h1 class="text-2xl font-bold text-gray-900">Create Account</h1>
          <p class="text-gray-500 text-sm mt-1">Join Shedulex — your smart timetabling platform</p>
        </div>

        <div v-if="error" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{{ error }}</div>

        <form @submit.prevent="submit" class="space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="label">First Name</label>
              <input v-model="form.first_name" required class="input" placeholder="John" />
            </div>
            <div>
              <label class="label">Last Name</label>
              <input v-model="form.last_name" required class="input" placeholder="Doe" />
            </div>
          </div>

          <div>
            <label class="label">Email Address</label>
            <input v-model="form.email" type="email" required class="input" placeholder="you@university.ac" />
          </div>
          <div>
            <label class="label">Username</label>
            <input v-model="form.username" required class="input" placeholder="johndoe" />
          </div>
          <div>
            <label class="label">Password</label>
            <input v-model="form.password" type="password" required class="input" placeholder="Min 8 chars, 1 uppercase, 1 digit" />
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="label">Phone *</label>
              <input v-model="form.phone" required class="input" placeholder="+255700000000" />
            </div>
            <div>
              <label class="label">Role</label>
              <select v-model="form.role_name" class="input">
                <option value="timetable_officer">Timetable Officer</option>
                <option value="admin">Administrator</option>
                <option value="hod">Head of Department</option>
                <option value="lecturer">Lecturer</option>
                <option value="student">Student</option>
              </select>
            </div>
          </div>

          <div class="border border-blue-100 rounded-xl p-4 space-y-3 bg-blue-50/40">
            <div class="flex items-center justify-between">
              <label class="label !mb-0 font-semibold">University</label>
              <div v-if="isAdmin" class="flex gap-1 rounded-lg border border-blue-200 overflow-hidden text-xs">
                <button type="button" @click="uniMode = 'select'" :class="uniMode === 'select' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-blue-50'" class="px-3 py-1 font-medium transition-colors">Join Existing</button>
                <button type="button" @click="uniMode = 'create'" :class="uniMode === 'create' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-blue-50'" class="px-3 py-1 font-medium transition-colors">Create New</button>
              </div>
            </div>

            <div v-if="!isAdmin || uniMode === 'select'">
              <template v-if="universities.length">
                <select v-model="form.university_id" class="input">
                  <option value="">— Select your university —</option>
                  <option v-for="u in universities" :key="u.id" :value="u.id">{{ u.name }} ({{ u.code }})</option>
                </select>
              </template>
              <p v-else class="text-sm text-gray-500 italic">No universities registered yet.</p>
            </div>

            <div v-else class="space-y-2">
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="label">University Name *</label>
                  <input v-model="form.university_name" class="input" placeholder="Kilimanjaro University" />
                </div>
                <div>
                  <label class="label">Short Code *</label>
                  <input v-model="form.university_code" class="input" placeholder="KUT" maxlength="20" />
                </div>
              </div>
            </div>
          </div>

          <div v-if="needsDepartment && form.university_id" class="border border-gray-200 rounded-xl p-4 space-y-3">
            <label class="label font-semibold">Academic Enrollment</label>
            <div>
              <label class="label">Department *</label>
              <select v-model="form.department_id" class="input" required>
                <option value="">— Select department —</option>
                <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
              </select>
            </div>
            <div v-if="isStudent">
              <label class="label">Program *</label>
              <select v-model="form.program_id" class="input" required>
                <option value="">— Select program —</option>
                <option v-for="p in programs" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
            </div>
            <div v-if="isStudent && studentGroups.length">
              <label class="label">Student Group (optional)</label>
              <select v-model="form.student_group_id" class="input">
                <option value="">— All groups in program —</option>
                <option v-for="g in studentGroups" :key="g.id" :value="g.id">{{ g.name }}</option>
              </select>
            </div>
          </div>

          <p v-if="!isAdmin" class="text-xs text-amber-600">
            Non-admin accounts require approval from a university administrator before you can log in.
          </p>

          <button type="submit" :disabled="loading" class="btn-primary w-full flex justify-center items-center gap-2 mt-2">
            {{ loading ? "Creating account…" : "Create Account" }}
          </button>
        </form>

        <p class="text-center text-sm text-gray-600 mt-6">
          Already have an account?
          <RouterLink to="/login" class="text-blue-600 hover:text-blue-700 font-medium">Sign in</RouterLink>
        </p>
      </div>

    </div>
  </div>
</template>
