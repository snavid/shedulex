<script setup>
import { onMounted, ref, computed } from "vue"
import { usersApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const users = ref([])
const pendingUsers = ref([])
const roles = ref([])
const activeTab = ref("all")  // "all" | "pending"

const pendingCount = computed(() => pendingUsers.value.length)

async function loadData() {
  loading.value = true
  try {
    const [usersRes, rolesRes, pendingRes] = await Promise.all([
      usersApi.list({ per_page: 100 }),
      usersApi.roles(),
      usersApi.list({ pending: "true", per_page: 100 }),
    ])
    users.value = (usersRes.data.data || []).filter(u => u.is_approved)
    pendingUsers.value = pendingRes.data.data || []
    roles.value = rolesRes.data.data || []
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load users."))
  } finally {
    loading.value = false
  }
}

async function toggleUser(userId) {
  try {
    await usersApi.toggleActivation(userId)
    toast.success("User status changed.")
    await loadData()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to change user status."))
  }
}

async function updateRole(userId, roleName) {
  try {
    await usersApi.changeRole(userId, roleName)
    toast.success("Role updated.")
    await loadData()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to update role."))
  }
}

async function approveUser(userId, name) {
  try {
    await usersApi.approveUser(userId)
    toast.success(`${name} approved and activated.`)
    await loadData()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to approve user."))
  }
}

async function rejectUser(userId, name) {
  if (!window.confirm(`Reject registration for ${name}? They will not be able to log in.`)) return
  try {
    await usersApi.rejectUser(userId)
    toast.success(`${name}'s registration rejected.`)
    await loadData()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to reject user."))
  }
}

function roleBadgeClass(roleName) {
  const map = {
    admin: "bg-red-100 text-red-700",
    timetable_officer: "bg-blue-100 text-blue-700",
    hod: "bg-indigo-100 text-indigo-700",
    lecturer: "bg-green-100 text-green-700",
    student: "bg-gray-100 text-gray-600",
  }
  return map[roleName] || "bg-gray-100 text-gray-600"
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-start justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">User Administration</h1>
        <p class="text-sm text-gray-500 mt-1">Manage accounts, approve registrations, and assign roles.</p>
      </div>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 p-1 bg-gray-100 rounded-xl w-fit">
      <button
        @click="activeTab = 'all'"
        :class="activeTab === 'all' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
        class="px-4 py-2 rounded-lg text-sm font-semibold transition-all"
      >
        All Users
        <span v-if="!loading" class="ml-1.5 text-xs text-gray-400">({{ users.length }})</span>
      </button>
      <button
        @click="activeTab = 'pending'"
        :class="activeTab === 'pending' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
        class="px-4 py-2 rounded-lg text-sm font-semibold transition-all relative"
      >
        Pending Approval
        <span
          v-if="pendingCount > 0"
          class="ml-1.5 inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full bg-amber-500 text-white text-xs font-bold"
        >{{ pendingCount }}</span>
        <span v-else-if="!loading" class="ml-1.5 text-xs text-gray-400">(0)</span>
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="card">
      <div class="space-y-3">
        <div v-for="i in 5" :key="i" class="h-16 bg-gray-100 rounded-lg animate-pulse"></div>
      </div>
    </div>

    <!-- Pending Approvals tab -->
    <div v-else-if="activeTab === 'pending'">
      <div v-if="!pendingUsers.length" class="card text-center py-14">
        <div class="w-12 h-12 mx-auto bg-green-50 rounded-2xl flex items-center justify-center mb-3">
          <svg class="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h3 class="font-semibold text-gray-900 mb-1">All clear!</h3>
        <p class="text-sm text-gray-500">No registrations pending approval.</p>
      </div>
      <div v-else class="space-y-3">
        <div
          v-for="u in pendingUsers"
          :key="u.id"
          class="card border-amber-100 bg-amber-50/30 flex flex-col sm:flex-row sm:items-center gap-4"
        >
          <div class="flex items-center gap-3 flex-1 min-w-0">
            <div class="w-10 h-10 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
              {{ (u.first_name?.[0] || "") + (u.last_name?.[0] || "") }}
            </div>
            <div class="min-w-0">
              <p class="font-semibold text-gray-900">{{ u.first_name }} {{ u.last_name }}</p>
              <p class="text-xs text-gray-500 truncate">{{ u.email }}</p>
              <span :class="roleBadgeClass(u.role?.name)" class="inline-block mt-1 text-xs font-semibold px-2 py-0.5 rounded-full capitalize">
                {{ (u.role?.name || "").replace(/_/g, " ") }}
              </span>
            </div>
          </div>
          <div class="flex gap-2 flex-shrink-0">
            <button
              class="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm font-semibold transition-colors"
              @click="approveUser(u.id, `${u.first_name} ${u.last_name}`)"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
              Approve
            </button>
            <button
              class="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 text-sm font-semibold transition-colors"
              @click="rejectUser(u.id, `${u.first_name} ${u.last_name}`)"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
              Reject
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- All Users tab -->
    <div v-else class="card">
      <div v-if="!users.length" class="text-center py-10">
        <p class="text-sm text-gray-500">No approved users found.</p>
      </div>
      <div v-else class="space-y-2">
        <div
          v-for="u in users"
          :key="u.id"
          class="flex flex-col sm:flex-row sm:items-center gap-3 p-3 rounded-xl border border-gray-100 hover:border-gray-200 hover:bg-gray-50 transition-colors"
        >
          <div class="flex items-center gap-3 flex-1 min-w-0">
            <div class="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
              {{ (u.first_name?.[0] || "") + (u.last_name?.[0] || "") }}
            </div>
            <div class="min-w-0">
              <p class="font-medium text-gray-900 truncate">{{ u.first_name }} {{ u.last_name }}</p>
              <p class="text-xs text-gray-500 truncate">{{ u.email }}</p>
            </div>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            <span
              :class="u.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
              class="text-xs font-semibold px-2 py-0.5 rounded-full"
            >
              {{ u.is_active ? "Active" : "Inactive" }}
            </span>
            <select
              class="input !w-auto text-sm py-1.5"
              :value="u.role?.name"
              @change="updateRole(u.id, $event.target.value)"
            >
              <option v-for="r in roles" :key="r.id" :value="r.name">{{ r.name }}</option>
            </select>
            <button class="btn-secondary text-sm py-1.5" @click="toggleUser(u.id)">
              {{ u.is_active ? "Deactivate" : "Activate" }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
