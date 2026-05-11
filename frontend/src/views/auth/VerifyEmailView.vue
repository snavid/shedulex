<script setup>
import { onMounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { authApi } from "@/api/client"

const route = useRoute()
const router = useRouter()
const status = ref("verifying")

onMounted(async () => {
  const token = route.query.token
  if (!token) { status.value = "error"; return }
  try {
    await authApi.verifyEmail(token)
    status.value = "success"
    setTimeout(() => router.push("/login"), 3000)
  } catch {
    status.value = "error"
  }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
    <div class="bg-white rounded-2xl shadow-xl p-10 text-center max-w-md w-full mx-4">
      <div v-if="status === 'verifying'" class="text-5xl mb-4 animate-spin">⏳</div>
      <div v-if="status === 'success'" class="text-5xl mb-4">✅</div>
      <div v-if="status === 'error'" class="text-5xl mb-4">❌</div>
      <h2 class="text-xl font-bold text-gray-900">
        {{ status === "verifying" ? "Verifying…" : status === "success" ? "Email Verified!" : "Verification Failed" }}
      </h2>
      <p class="text-gray-500 text-sm mt-2">
        {{ status === "success" ? "Redirecting to login…" : status === "error" ? "Invalid or expired link." : "Please wait." }}
      </p>
      <RouterLink v-if="status !== 'verifying'" to="/login" class="mt-4 inline-block btn-primary">Go to Login</RouterLink>
    </div>
  </div>
</template>
