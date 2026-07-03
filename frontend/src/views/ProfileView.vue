<script setup>
import { computed, onMounted, ref, watch } from "vue"
import { useAuthStore } from "@/stores/auth"
import { authApi, resourcesApi, usersApi, getErrorMessage, validatePhone, isInvalidStoredPhone } from "@/api/client"
import { useToast } from "vue-toastification"

const auth = useAuthStore()
const toast = useToast()
const loading = ref(true)
const saving = ref(false)
const passwordForm = ref({ current_password: "", new_password: "" })
const profileForm = ref({
  email: "",
  phone: "",
  department_id: "",
  program_id: "",
  student_group_id: "",
})

const departments = ref([])
const programs = ref([])
const studentGroups = ref([])
const isStudent = computed(() => auth.user?.role?.name === "student")
const needsDepartment = computed(() => isStudent.value || auth.user?.role?.name === "hod")
const phoneHint = ref("")

async function loadResources() {
  if (!auth.user?.university_id) return
  try {
    const { data } = await resourcesApi.departments({ university_id: auth.user.university_id })
    departments.value = data.data || []
  } catch {}
}

watch(() => profileForm.value.department_id, async (deptId) => {
  programs.value = []
  studentGroups.value = []
  if (!deptId) return
  try {
    const { data } = await resourcesApi.programs({ department_id: deptId })
    programs.value = data.data || []
  } catch {}
})

watch(() => profileForm.value.program_id, async (progId) => {
  studentGroups.value = []
  if (!progId) return
  try {
    const { data } = await resourcesApi.studentGroups({ program_id: progId })
    studentGroups.value = data.data || []
  } catch {}
})

async function loadProfile() {
  loading.value = true
  try {
    await auth.fetchMe()
    const storedPhone = auth.user?.phone || ""
    phoneHint.value = isInvalidStoredPhone(storedPhone)
      ? "Previous phone value was invalid — enter a valid number."
      : ""
    profileForm.value = {
      email: auth.user?.email || "",
      phone: isInvalidStoredPhone(storedPhone) ? "" : storedPhone,
      department_id: auth.user?.department_id || "",
      program_id: auth.user?.program_id || "",
      student_group_id: auth.user?.student_group_id || "",
    }
    await loadResources()
    if (profileForm.value.department_id) {
      const { data } = await resourcesApi.programs({ department_id: profileForm.value.department_id })
      programs.value = data.data || []
    }
    if (profileForm.value.program_id) {
      const { data } = await resourcesApi.studentGroups({ program_id: profileForm.value.program_id })
      studentGroups.value = data.data || []
    }
  } finally {
    loading.value = false
  }
}

async function saveProfile() {
  if (!auth.user?.id) return
  if (!profileForm.value.email?.trim()) {
    toast.error("Email is required.")
    return
  }
  const phoneError = validatePhone(profileForm.value.phone)
  if (phoneError) {
    toast.error(phoneError)
    return
  }
  saving.value = true
  try {
    const payload = {
      email: profileForm.value.email.trim(),
      phone: profileForm.value.phone.trim(),
    }
    if (needsDepartment.value && profileForm.value.department_id) {
      payload.department_id = profileForm.value.department_id
    }
    if (isStudent.value) {
      if (profileForm.value.program_id) payload.program_id = profileForm.value.program_id
      if (profileForm.value.student_group_id) payload.student_group_id = profileForm.value.student_group_id
    }
    await usersApi.update(auth.user.id, payload)
    await auth.fetchMe()
    phoneHint.value = ""
    toast.success("Profile updated.")
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to update profile."))
  } finally {
    saving.value = false
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
      <p class="text-sm text-gray-500 mt-1">Account details, enrollment, and credential management.</p>
    </div>

    <div class="card" v-if="loading">
      <p class="text-sm text-gray-500">Loading profile...</p>
    </div>

    <template v-else>
      <div class="card space-y-2">
        <h2 class="font-semibold">Account Information</h2>
        <p class="text-sm"><strong>Name:</strong> {{ auth.user?.first_name }} {{ auth.user?.last_name }}</p>
        <p class="text-sm"><strong>Username:</strong> {{ auth.user?.username }}</p>
        <p class="text-sm"><strong>Role:</strong> {{ auth.user?.role?.name || "N/A" }}</p>
        <p class="text-sm"><strong>Department:</strong> {{ auth.user?.department || "N/A" }}</p>
      </div>

      <div class="card space-y-3">
        <h2 class="font-semibold">Contact & Enrollment</h2>
        <div>
          <label class="label">Email *</label>
          <input v-model="profileForm.email" type="email" required class="input" placeholder="you@university.ac" />
        </div>
        <div>
          <label class="label">Phone *</label>
          <input v-model="profileForm.phone" required class="input" placeholder="+255700000000" />
          <p v-if="phoneHint" class="text-xs text-amber-600 mt-1">{{ phoneHint }}</p>
        </div>
        <div v-if="needsDepartment">
          <label class="label">Department</label>
          <select v-model="profileForm.department_id" class="input">
            <option value="">— Select department —</option>
            <option v-for="d in departments" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
        </div>
        <div v-if="isStudent">
          <label class="label">Program</label>
          <select v-model="profileForm.program_id" class="input">
            <option value="">— Select program —</option>
            <option v-for="p in programs" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </div>
        <div v-if="isStudent && studentGroups.length">
          <label class="label">Student Group</label>
          <select v-model="profileForm.student_group_id" class="input">
            <option value="">— Optional —</option>
            <option v-for="g in studentGroups" :key="g.id" :value="g.id">{{ g.name }}</option>
          </select>
        </div>
        <button class="btn-primary" :disabled="saving" @click="saveProfile">
          {{ saving ? "Saving..." : "Save Profile" }}
        </button>
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
