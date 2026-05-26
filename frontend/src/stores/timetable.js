import { defineStore } from "pinia"
import { ref } from "vue"
import { timetableApi, resourcesApi } from "@/api/client"

export const useTimetableStore = defineStore("timetable", () => {
  const timetables = ref([])
  const currentTimetable = ref(null)
  const departments = ref([])
  const rooms = ref([])
  const lecturers = ref([])
  const courses = ref([])
  const constraints = ref([])
  const conflicts = ref([])
  const isGenerating = ref(false)

  async function fetchTimetables(params = {}) {
    const { data } = await timetableApi.list(params)
    timetables.value = data.data
    return data.data
  }

  async function fetchTimetable(id) {
    const { data } = await timetableApi.get(id)
    currentTimetable.value = data.data
    return data.data
  }

  async function generateTimetable(payload) {
    isGenerating.value = true
    try {
      const { data } = await timetableApi.generate(payload)
      timetables.value.unshift(data.data)
      currentTimetable.value = data.data
      return data.data
    } finally {
      isGenerating.value = false
    }
  }

  async function detectConflicts(id) {
    const { data } = await timetableApi.conflicts(id)
    conflicts.value = data.data
    return data.data
  }

  async function swapEntries(entry1Id, entry2Id) {
    const { data } = await timetableApi.swapEntries({ entry1_id: entry1Id, entry2_id: entry2Id })
    await fetchTimetable(currentTimetable.value?.id)
    return data.data
  }

  async function fetchDepartments() {
    const { data } = await resourcesApi.departments()
    departments.value = data.data
    return data.data
  }

  async function fetchRooms() {
    const { data } = await resourcesApi.rooms()
    rooms.value = data.data
    return data.data
  }

  async function fetchLecturers() {
    const { data } = await resourcesApi.lecturers()
    lecturers.value = data.data
    return data.data
  }

  async function fetchCourses(params = {}) {
    const { data } = await resourcesApi.courses(params)
    courses.value = data.data
    return data.data
  }

  async function deleteTimetable(id) {
    await timetableApi.delete(id)
    timetables.value = timetables.value.filter(t => t.id !== id)
    if (currentTimetable.value?.id === id) currentTimetable.value = null
  }

  function setCurrentTimetable(data) {
    currentTimetable.value = data
  }

  function clearAll() {
    timetables.value = []
    currentTimetable.value = null
    departments.value = []
    rooms.value = []
    lecturers.value = []
    courses.value = []
    constraints.value = []
    conflicts.value = []
    isGenerating.value = false
  }

  return {
    timetables, currentTimetable, departments, rooms, lecturers,
    courses, constraints, conflicts, isGenerating,
    fetchTimetables, fetchTimetable, generateTimetable, detectConflicts,
    swapEntries, fetchDepartments, fetchRooms, fetchLecturers, fetchCourses,
    deleteTimetable, setCurrentTimetable, clearAll,
  }
})
