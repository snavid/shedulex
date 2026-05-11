<script setup>
import { ref } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "@/stores/auth"
import { useToast } from "vue-toastification"

const auth = useAuthStore()
const router = useRouter()
const toast = useToast()

const form = ref({
  email: "", username: "", password: "", first_name: "", last_name: "",
  phone: "", department: "", role_name: "student",
})
const loading = ref(false)
const error = ref("")

async function submit() {
  error.value = ""
  loading.value = true
  try {
    await auth.register(form.value)
    toast.success("Account created! Please verify your email.")
    router.push("/dashboard")
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
      <div class="bg-white rounded-2xl shadow-xl p-8">
        <div class="text-center mb-8">
          <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-600 text-white text-3xl mb-4">📅</div>
          <h1 class="text-2xl font-bold text-gray-900">Create Account</h1>
          <p class="text-gray-500 text-sm mt-1">Join Shedulex today</p>
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
              <label class="label">Phone (optional)</label>
              <input v-model="form.phone" class="input" placeholder="+255700000000" />
            </div>
            <div>
              <label class="label">Department (optional)</label>
              <input v-model="form.department" class="input" placeholder="Computer Science" />
            </div>
          </div>
          <div>
            <label class="label">Role</label>
            <select v-model="form.role_name" class="input">
              <option value="student">Student</option>
              <option value="lecturer">Lecturer</option>
              <option value="timetable_officer">Timetable Officer</option>
              <option value="hod">Head of Department</option>
            </select>
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
