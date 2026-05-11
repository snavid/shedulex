<script setup>
import { ref } from "vue"
import { useRouter, useRoute } from "vue-router"
import { useAuthStore } from "@/stores/auth"
import { useToast } from "vue-toastification"

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const toast = useToast()

const form = ref({ email: "", password: "" })
const loading = ref(false)
const error = ref("")

async function submit() {
  error.value = ""
  loading.value = true
  try {
    await auth.login(form.value.email, form.value.password)
    toast.success("Welcome back!")
    const redirect = route.query.redirect || "/dashboard"
    router.push(redirect)
  } catch (e) {
    error.value = e.response?.data?.message || "Login failed. Please try again."
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 px-4">
    <div class="w-full max-w-md">
      <!-- Card -->
      <div class="bg-white rounded-2xl shadow-xl p-8">
        <!-- Logo -->
        <div class="text-center mb-8">
          <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-600 text-white text-3xl mb-4">📅</div>
          <h1 class="text-2xl font-bold text-gray-900">Welcome to Shedulex</h1>
          <p class="text-gray-500 text-sm mt-1">Intelligent Academic Timetable System</p>
        </div>

        <!-- Error -->
        <div v-if="error" class="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{{ error }}</div>

        <!-- Form -->
        <form @submit.prevent="submit" class="space-y-5">
          <div>
            <label class="label">Email Address</label>
            <input v-model="form.email" type="email" required class="input" placeholder="you@university.ac" />
          </div>
          <div>
            <label class="label">Password</label>
            <input v-model="form.password" type="password" required class="input" placeholder="••••••••" />
          </div>
          <div class="flex items-center justify-between text-sm">
            <label class="flex items-center gap-2 text-gray-600 cursor-pointer">
              <input type="checkbox" class="rounded" /> Remember me
            </label>
            <RouterLink to="/forgot-password" class="text-blue-600 hover:text-blue-700 font-medium">Forgot password?</RouterLink>
          </div>
          <button type="submit" :disabled="loading" class="btn-primary w-full justify-center flex items-center gap-2">
            <svg v-if="loading" class="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            {{ loading ? "Signing in…" : "Sign In" }}
          </button>
        </form>

        <p class="text-center text-sm text-gray-600 mt-6">
          Don't have an account?
          <RouterLink to="/register" class="text-blue-600 hover:text-blue-700 font-medium">Register here</RouterLink>
        </p>
      </div>
    </div>
  </div>
</template>
