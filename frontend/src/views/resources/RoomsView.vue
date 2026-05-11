<script setup>
import { onMounted, ref } from "vue"
import { resourcesApi } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const rooms = ref([])
const form = ref({
  name: "",
  code: "",
  capacity: 40,
  room_type: "lecture",
  building: "",
  floor: 1,
})

async function loadRooms() {
  loading.value = true
  try {
    const { data } = await resourcesApi.rooms()
    rooms.value = data.data || []
  } finally {
    loading.value = false
  }
}

async function createRoom() {
  await resourcesApi.createRoom(form.value)
  toast.success("Room created.")
  form.value = { name: "", code: "", capacity: 40, room_type: "lecture", building: "", floor: 1 }
  await loadRooms()
}

async function removeRoom(id) {
  await resourcesApi.deleteRoom(id)
  toast.success("Room deleted.")
  await loadRooms()
}

onMounted(loadRooms)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Rooms</h1>
      <p class="text-sm text-gray-500 mt-1">Lecture halls, labs, and venue capacities.</p>
    </div>

    <div class="card space-y-3">
      <h2 class="font-semibold">Create Room</h2>
      <div class="grid md:grid-cols-3 gap-3">
        <input v-model="form.name" class="input" placeholder="Room name" />
        <input v-model="form.code" class="input" placeholder="Code" />
        <input v-model.number="form.capacity" type="number" class="input" placeholder="Capacity" />
        <select v-model="form.room_type" class="input">
          <option value="lecture">Lecture</option>
          <option value="lab">Lab</option>
          <option value="seminar">Seminar</option>
        </select>
        <input v-model="form.building" class="input" placeholder="Building" />
        <input v-model.number="form.floor" type="number" class="input" placeholder="Floor" />
      </div>
      <button class="btn-primary" @click="createRoom">Create</button>
    </div>

    <div class="card">
      <h2 class="font-semibold mb-3">All Rooms</h2>
      <div v-if="loading" class="text-sm text-gray-500">Loading...</div>
      <div v-else-if="!rooms.length" class="text-sm text-gray-500">No rooms found.</div>
      <div v-else class="space-y-2">
        <div v-for="room in rooms" :key="room.id" class="flex items-center justify-between p-3 border border-gray-200 rounded-lg">
          <div>
            <p class="font-medium">{{ room.name }} ({{ room.code }})</p>
            <p class="text-xs text-gray-500">{{ room.room_type }} | Capacity {{ room.capacity }} | {{ room.building || "N/A" }}</p>
          </div>
          <button class="btn-danger" @click="removeRoom(room.id)">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>
