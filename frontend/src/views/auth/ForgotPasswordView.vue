<script setup>
import { ref } from "vue"
import { authApi } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const email = ref("")
const loading = ref(false)
const sent = ref(false)

async function submit() {
  loading.value = true
  try {
    await authApi.requestReset({ email: email.value })
    sent.value = true
    toast.success("Reset link sent if email exists.")
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 px-4">
    <div class="w-full max-w-md">
      <div class="bg-white rounded-2xl shadow-xl p-8 text-center">
        <div class="text-5xl mb-4">🔐</div>
        <h1 class="text-2xl font-bold text-gray-900 mb-2">Forgot Password</h1>
        <p class="text-gray-500 text-sm mb-6">Enter your email and we'll send you a reset link.</p>

        <div v-if="sent" class="p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm mb-4">
          If that email is registered, a reset link has been sent. Check your inbox.
        </div>

        <form v-else @submit.prevent="submit" class="space-y-4 text-left">
          <div>
            <label class="label">Email Address</label>
            <input v-model="email" type="email" required class="input" placeholder="you@university.ac" />
          </div>
          <button type="submit" :disabled="loading" class="btn-primary w-full">
            {{ loading ? "Sending…" : "Send Reset Link" }}
          </button>
        </form>

        <RouterLink to="/login" class="mt-4 inline-block text-sm text-blue-600 hover:text-blue-700">← Back to sign in</RouterLink>
      </div>
    </div>
  </div>
</template>
