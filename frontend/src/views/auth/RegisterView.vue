<script setup>
import { ref, computed, onMounted } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "@/stores/auth"
import { useToast } from "vue-toastification"
import api from "@/api/client"

const auth = useAuthStore()
const router = useRouter()
const toast = useToast()

const form = ref({
  email: "", username: "", password: "", first_name: "", last_name: "",
  phone: "", department: "", role_name: "timetable_officer",
  university_id: "", university_name: "", university_code: "",
})
const loading = ref(false)
const error = ref("")
const pendingApproval = ref(false)
const registeredName = ref("")

// "select" = join existing; "create" = new university (admin only)
const uniMode = ref("select")
const universities = ref([])

onMounted(async () => {
  try {
    const { data } = await api.get("/universities")
    universities.value = data.data || []
    if (!universities.value.length) uniMode.value = "create"
  } catch {
    uniMode.value = "create"
  }
})

// Only admins can create a new university
const isAdmin = computed(() => form.value.role_name === "admin")

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
    error.value = e.response?.data?.message || "Registration failed."
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 px-4 py-8">
    <div class="w-full max-w-lg">

      <!-- Pending approval screen -->
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

      <!-- Registration form -->
      <div v-else class="bg-white rounded-2xl shadow-xl p-8">
        <div class="text-center mb-8">
          <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-600 text-white text-3xl mb-4">📅</div>
          <h1 class="text-2xl font-bold text-gray-900">Create Account</h1>
          <p class="text-gray-500 text-sm mt-1">Join Shedulex — your smart timetabling platform</p>
        </div>

        <div v-if="error" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{{ error }}</div>

        <form @submit.prevent="submit" class="space-y-4">
          <!-- Name -->
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
              <label class="label">Phone (optional)</label>
              <input v-model="form.phone" class="input" placeholder="+255700000000" />
            </div>
            <div>
              <label class="label">Department (optional)</label>
              <input v-model="form.department" class="input" placeholder="Computer Science" />
            </div>
          </div>

          <!-- Role -->
          <div>
            <label class="label">Role</label>
            <select v-model="form.role_name" class="input">
              <option value="timetable_officer">Timetable Officer</option>
              <option value="admin">Administrator</option>
              <option value="hod">Head of Department</option>
              <option value="lecturer">Lecturer</option>
              <option value="student">Student</option>
            </select>
            <p v-if="!isAdmin" class="text-xs text-amber-600 mt-1">
              Non-admin accounts require approval from a university administrator before you can log in.
            </p>
            <p v-else class="text-xs text-green-600 mt-1">
              Admin accounts are activated immediately and can set up their university.
            </p>
          </div>

          <!-- University -->
          <div class="border border-blue-100 rounded-xl p-4 space-y-3 bg-blue-50/40">
            <div class="flex items-center justify-between">
              <label class="label !mb-0 font-semibold">University</label>
              <!-- Only admins can create a new university -->
              <div v-if="isAdmin" class="flex gap-1 rounded-lg border border-blue-200 overflow-hidden text-xs">
                <button
                  type="button"
                  @click="uniMode = 'select'"
                  :class="uniMode === 'select' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-blue-50'"
                  class="px-3 py-1 font-medium transition-colors"
                >Join Existing</button>
                <button
                  type="button"
                  @click="uniMode = 'create'"
                  :class="uniMode === 'create' ? 'bg-blue-600 text-white' : 'bg-white text-gray-600 hover:bg-blue-50'"
                  class="px-3 py-1 font-medium transition-colors"
                >Create New</button>
              </div>
            </div>

            <!-- Join existing university -->
            <div v-if="!isAdmin || uniMode === 'select'">
              <template v-if="universities.length">
                <select v-model="form.university_id" class="input">
                  <option value="">— Select your university —</option>
                  <option v-for="u in universities" :key="u.id" :value="u.id">{{ u.name }} ({{ u.code }})</option>
                </select>
              </template>
              <p v-else class="text-sm text-gray-500 italic">
                No universities registered yet.
                <template v-if="isAdmin"> Switch to "Create New" to set one up.</template>
                <template v-else> Please contact your university administrator.</template>
              </p>
            </div>

            <!-- Create new university (admin only) -->
            <div v-else class="space-y-2">
              <p class="text-xs text-blue-700">You're setting up Shedulex for a new university.</p>
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

          <button type="submit" :disabled="loading" class="btn-primary w-full flex justify-center items-center gap-2 mt-2">
            <svg v-if="loading" class="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
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
