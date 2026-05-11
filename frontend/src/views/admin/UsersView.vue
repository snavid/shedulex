<script setup>
import { onMounted, ref } from "vue"
import { usersApi } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const users = ref([])
const roles = ref([])

async function loadData() {
  loading.value = true
  try {
    const [usersRes, rolesRes] = await Promise.all([
      usersApi.list({ per_page: 100 }),
      usersApi.roles(),
    ])
    users.value = usersRes.data.data || []
    roles.value = rolesRes.data.data || []
  } finally {
    loading.value = false
  }
}

async function toggleUser(userId) {
  await usersApi.toggleActivation(userId)
  toast.success("User status changed.")
  await loadData()
}

async function updateRole(userId, roleName) {
  await usersApi.changeRole(userId, roleName)
  toast.success("Role updated.")
  await loadData()
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">User Administration</h1>
      <p class="text-sm text-gray-500 mt-1">Manage accounts, activation state, and role permissions.</p>
    </div>

    <div class="card">
      <h2 class="font-semibold mb-3">Users</h2>
      <div v-if="loading" class="text-sm text-gray-500">Loading users...</div>
      <div v-else-if="!users.length" class="text-sm text-gray-500">No users found.</div>
      <div v-else class="space-y-2">
        <div v-for="u in users" :key="u.id" class="p-3 border border-gray-200 rounded-lg">
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="font-medium">{{ u.first_name }} {{ u.last_name }}</p>
              <p class="text-xs text-gray-500">{{ u.email }} | {{ u.username }}</p>
              <p class="text-xs text-gray-500 mt-1">Current role: {{ u.role?.name || "N/A" }}</p>
            </div>
            <div class="flex items-center gap-2">
              <select class="input !w-auto" :value="u.role?.name" @change="updateRole(u.id, $event.target.value)">
                <option v-for="r in roles" :key="r.id" :value="r.name">{{ r.name }}</option>
              </select>
              <button class="btn-secondary" @click="toggleUser(u.id)">
                {{ u.is_active ? "Deactivate" : "Activate" }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
