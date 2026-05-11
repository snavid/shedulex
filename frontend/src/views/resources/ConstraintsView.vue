<script setup>
import { onMounted, ref } from "vue"
import { resourcesApi } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const constraints = ref([])
const form = ref({
  name: "",
  constraint_type: "soft",
  category: "department",
  weight: 1.0,
  config: "{}",
})

async function loadConstraints() {
  loading.value = true
  try {
    const { data } = await resourcesApi.constraints()
    constraints.value = data.data || []
  } finally {
    loading.value = false
  }
}

async function createConstraint() {
  let configObj = {}
  try {
    configObj = form.value.config ? JSON.parse(form.value.config) : {}
  } catch {
    toast.error("Config must be valid JSON.")
    return
  }
  await resourcesApi.createConstraint({
    name: form.value.name,
    constraint_type: form.value.constraint_type,
    category: form.value.category,
    weight: Number(form.value.weight),
    config: configObj,
  })
  toast.success("Constraint created.")
  form.value = { name: "", constraint_type: "soft", category: "department", weight: 1.0, config: "{}" }
  await loadConstraints()
}

onMounted(loadConstraints)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Constraints</h1>
      <p class="text-sm text-gray-500 mt-1">Hard and soft scheduling rules with weight tuning.</p>
    </div>

    <div class="card space-y-3">
      <h2 class="font-semibold">Create Constraint</h2>
      <div class="grid md:grid-cols-2 gap-3">
        <input v-model="form.name" class="input" placeholder="Constraint name" />
        <select v-model="form.constraint_type" class="input">
          <option value="hard">Hard</option>
          <option value="soft">Soft</option>
        </select>
        <select v-model="form.category" class="input">
          <option value="lecturer">Lecturer</option>
          <option value="room">Room</option>
          <option value="student">Student</option>
          <option value="department">Department</option>
        </select>
        <input v-model.number="form.weight" type="number" step="0.1" min="0" class="input" placeholder="Weight" />
      </div>
      <textarea v-model="form.config" rows="4" class="input" placeholder='{"max_consecutive_hours": 3}' />
      <button class="btn-primary" @click="createConstraint">Create</button>
    </div>

    <div class="card">
      <h2 class="font-semibold mb-3">Active Constraints</h2>
      <div v-if="loading" class="text-sm text-gray-500">Loading...</div>
      <div v-else-if="!constraints.length" class="text-sm text-gray-500">No constraints found.</div>
      <div v-else class="space-y-2">
        <div v-for="c in constraints" :key="c.id" class="p-3 border border-gray-200 rounded-lg">
          <p class="font-medium">{{ c.name }}</p>
          <p class="text-xs text-gray-500">{{ c.constraint_type }} | {{ c.category }} | weight {{ c.weight }}</p>
        </div>
      </div>
    </div>
  </div>
</template>
