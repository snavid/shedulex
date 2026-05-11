<script setup>
import { onMounted, ref } from "vue"
import { useAuthStore } from "@/stores/auth"
import { authApi } from "@/api/client"
import { useToast } from "vue-toastification"

const auth = useAuthStore()
const toast = useToast()
const loading = ref(true)
const passwordForm = ref({
  current_password: "",
  new_password: "",
})

async function loadProfile() {
  loading.value = true
  try {
    await auth.fetchMe()
  } finally {
    loading.value = false
  }
}

async function changePassword() {
  await authApi.changePassword(passwordForm.value)
  toast.success("Password changed.")
  passwordForm.value = { current_password: "", new_password: "" }
}

onMounted(loadProfile)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">My Profile</h1>
      <p class="text-sm text-gray-500 mt-1">Account details, role, and credential management.</p>
    </div>

    <div class="card" v-if="loading">
      <p class="text-sm text-gray-500">Loading profile...</p>
    </div>

    <template v-else>
      <div class="card space-y-2">
        <h2 class="font-semibold">Account Information</h2>
        <p class="text-sm"><strong>Name:</strong> {{ auth.user?.first_name }} {{ auth.user?.last_name }}</p>
        <p class="text-sm"><strong>Email:</strong> {{ auth.user?.email }}</p>
        <p class="text-sm"><strong>Username:</strong> {{ auth.user?.username }}</p>
        <p class="text-sm"><strong>Role:</strong> {{ auth.user?.role?.name || "N/A" }}</p>
        <p class="text-sm"><strong>Department:</strong> {{ auth.user?.department || "N/A" }}</p>
      </div>

      <div class="card space-y-3">
        <h2 class="font-semibold">Change Password</h2>
        <input v-model="passwordForm.current_password" type="password" class="input" placeholder="Current password" />
        <input v-model="passwordForm.new_password" type="password" class="input" placeholder="New password" />
        <button class="btn-primary" @click="changePassword">Update Password</button>
      </div>
    </template>
  </div>
</template>
