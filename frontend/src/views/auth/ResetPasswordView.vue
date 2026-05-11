<script setup>
import { ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { authApi } from "@/api/client"
import { useToast } from "vue-toastification"

const route = useRoute()
const router = useRouter()
const toast = useToast()
const password = ref("")
const loading = ref(false)

async function submit() {
  loading.value = true
  try {
    await authApi.confirmReset({ token: route.query.token, password: password.value })
    toast.success("Password reset successfully!")
    router.push("/login")
  } catch (e) {
    toast.error(e.response?.data?.message || "Reset failed.")
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 px-4">
    <div class="w-full max-w-md">
      <div class="bg-white rounded-2xl shadow-xl p-8">
        <div class="text-center mb-8">
          <div class="text-5xl mb-3">🔑</div>
          <h1 class="text-2xl font-bold text-gray-900">Set New Password</h1>
        </div>
        <form @submit.prevent="submit" class="space-y-4">
          <div>
            <label class="label">New Password</label>
            <input v-model="password" type="password" required minlength="8" class="input" placeholder="Min 8 chars, 1 uppercase, 1 digit" />
          </div>
          <button type="submit" :disabled="loading" class="btn-primary w-full">{{ loading ? "Resetting…" : "Reset Password" }}</button>
        </form>
      </div>
    </div>
  </div>
</template>
