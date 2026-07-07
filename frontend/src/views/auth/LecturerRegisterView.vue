<script setup>
import { onMounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { lecturerInviteApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"

const route = useRoute()
const router = useRouter()
const toast = useToast()

const status = ref("loading") // "loading" | "ready" | "error"
const errorMessage = ref("")
const submitting = ref(false)

const invite = ref(null)
const form = ref({ email: "", phone: "", password: "", confirm_password: "" })

const token = route.query.token

async function loadInvite() {
  if (!token) {
    status.value = "error"
    errorMessage.value = "This registration link is missing its token."
    return
  }
  try {
    const { data } = await lecturerInviteApi.preview(token)
    invite.value = data.data
    form.value.email = invite.value.email || ""
    form.value.phone = invite.value.phone || ""
    status.value = "ready"
  } catch (e) {
    status.value = "error"
    errorMessage.value = getErrorMessage(e, "This registration link is invalid or has expired.")
  }
}

async function submit() {
  if (!form.value.email || !form.value.phone) {
    toast.error("Email and phone are required.")
    return
  }
  if (form.value.password.length < 8) {
    toast.error("Password must be at least 8 characters.")
    return
  }
  if (form.value.password !== form.value.confirm_password) {
    toast.error("Passwords do not match.")
    return
  }
  submitting.value = true
  try {
    await lecturerInviteApi.confirm({
      token,
      password: form.value.password,
      email: form.value.email.trim(),
      phone: form.value.phone.trim(),
    })
    toast.success("Account created! You can now log in.")
    router.push("/login")
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to create account."))
  } finally {
    submitting.value = false
  }
}

onMounted(loadInvite)
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 px-4">
    <div class="w-full max-w-md">
      <div class="bg-white rounded-2xl shadow-xl p-8">
        <div class="text-center mb-8">
          <div class="text-5xl mb-3">🎓</div>
          <h1 class="text-2xl font-bold text-gray-900">Lecturer Registration</h1>
          <p v-if="invite" class="text-sm text-gray-500 mt-1">
            Welcome, {{ invite.name }}<span v-if="invite.department"> · {{ invite.department }}</span>
          </p>
        </div>

        <!-- Loading -->
        <div v-if="status === 'loading'" class="text-center py-8 text-gray-400 text-sm">
          Checking your invite…
        </div>

        <!-- Error -->
        <div v-else-if="status === 'error'" class="text-center py-4 space-y-4">
          <p class="text-sm text-red-600">{{ errorMessage }}</p>
          <router-link to="/login" class="text-blue-600 hover:underline text-sm">Back to login</router-link>
        </div>

        <!-- Form -->
        <form v-else @submit.prevent="submit" class="space-y-4">
          <p class="text-xs text-gray-500">
            Confirm or update your details, then set a password to activate your account.
          </p>
          <div>
            <label class="label">Email</label>
            <input v-model="form.email" type="email" required class="input" />
          </div>
          <div>
            <label class="label">Phone</label>
            <input v-model="form.phone" required class="input" placeholder="+256 700 000 000" />
          </div>
          <div>
            <label class="label">Password</label>
            <input v-model="form.password" type="password" required minlength="8" class="input" placeholder="Min 8 characters" />
          </div>
          <div>
            <label class="label">Confirm Password</label>
            <input v-model="form.confirm_password" type="password" required minlength="8" class="input" />
          </div>
          <button type="submit" :disabled="submitting" class="btn-primary w-full">
            {{ submitting ? "Creating account…" : "Create Account" }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>
