import { ref, computed } from "vue"
import { defineStore } from "pinia"
import { academicYearsApi } from "@/api/client"

export const useAcademicYearStore = defineStore("academicYear", () => {
  const years = ref([])
  const currentYearId = ref(localStorage.getItem("currentAcademicYearId") || null)
  const currentSemester = ref(parseInt(localStorage.getItem("currentSemester") || "1"))
  const universityId = ref(localStorage.getItem("cachedUniversityId") || null)
  const loading = ref(false)

  const currentYear = computed(() =>
    years.value.find((y) => y.id === currentYearId.value) || null,
  )

  const semesterLabel = computed(() =>
    `Sem ${currentSemester.value}`,
  )

  const semesterDates = computed(() => {
    const yr = currentYear.value
    if (!yr) return null
    return currentSemester.value === 1
      ? { start: yr.sem1_start, end: yr.sem1_end }
      : { start: yr.sem2_start, end: yr.sem2_end }
  })

  async function loadYears(uniId) {
    if (!uniId) return  // caller already resolved the ID
    universityId.value = uniId
    localStorage.setItem("cachedUniversityId", uniId)
    loading.value = true
    try {
      const { data } = await academicYearsApi.list({ university_id: uniId })
      years.value = data.data || []
      if (!currentYearId.value || !years.value.find((y) => y.id === currentYearId.value)) {
        const active = years.value.find((y) => y.is_current) || years.value[0]
        if (active) setCurrentYear(active.id)
      }
    } finally {
      loading.value = false
    }
  }

  function setCurrentYear(id) {
    currentYearId.value = id
    localStorage.setItem("currentAcademicYearId", id)
  }

  function setSemester(n) {
    currentSemester.value = n
    localStorage.setItem("currentSemester", String(n))
  }

  async function createYear(data) {
    const res = await academicYearsApi.create(data)
    const newYear = res.data.data
    years.value.unshift(newYear)
    if (data.is_current) {
      years.value = years.value.map((y) => ({ ...y, is_current: y.id === newYear.id }))
    }
    return newYear
  }

  async function updateYear(id, data) {
    const res = await academicYearsApi.update(id, data)
    const updated = res.data.data
    const idx = years.value.findIndex((y) => y.id === id)
    if (idx !== -1) years.value[idx] = updated
    return updated
  }

  async function activateYear(id) {
    const res = await academicYearsApi.activate(id)
    const activated = res.data.data
    years.value = years.value.map((y) => ({ ...y, is_current: y.id === id }))
    const idx = years.value.findIndex((y) => y.id === id)
    if (idx !== -1) years.value[idx] = activated
    setCurrentYear(id)
    return activated
  }

  async function deleteYear(id) {
    await academicYearsApi.delete(id)
    years.value = years.value.filter((y) => y.id !== id)
    if (currentYearId.value === id) {
      const next = years.value[0] || null
      if (next) setCurrentYear(next.id)
      else {
        currentYearId.value = null
        localStorage.removeItem("currentAcademicYearId")
      }
    }
  }

  function clearAll() {
    years.value = []
    currentYearId.value = null
    localStorage.removeItem("currentAcademicYearId")
  }

  return {
    years, currentYearId, currentYear, currentSemester, semesterLabel,
    semesterDates, universityId, loading, loadYears, setCurrentYear, setSemester,
    createYear, updateYear, activateYear, deleteYear, clearAll,
  }
})
