<script setup>
import { ref, onMounted } from "vue"
import { useRouter } from "vue-router"
import { useTimetableStore } from "@/stores/timetable"
import { useToast } from "vue-toastification"

const store = useTimetableStore()
const router = useRouter()
const toast = useToast()

const form = ref({
  name: "",
  department_id: "",
  semester: 1,
  academic_year: new Date().getFullYear() + "/" + (new Date().getFullYear() + 1),
  ga_config: {
    population_size: 100,
    max_generations: 300,
    fitness_threshold: 0.95,
  },
})
const showAdvanced = ref(false)
const progress = ref(null)

onMounted(() => store.fetchDepartments())

async function generate() {
  if (!form.value.department_id || !form.value.name) {
    toast.error("Please fill all required fields.")
    return
  }
  progress.value = { status: "Initializing genetic algorithm…", pct: 10 }
  try {
    const fakeProgress = [
      { status: "Creating initial population…", pct: 25 },
      { status: "Evaluating fitness scores…", pct: 45 },
      { status: "Crossover & mutation operations…", pct: 65 },
      { status: "Applying elitism selection…", pct: 80 },
      { status: "Optimizing constraint violations…", pct: 92 },
      { status: "Finalizing timetable…", pct: 98 },
    ]
    let i = 0
    const interval = setInterval(() => {
      if (i < fakeProgress.length) { progress.value = fakeProgress[i++] }
    }, 1500)

    const tt = await store.generateTimetable(form.value)
    clearInterval(interval)
    progress.value = { status: "Generation complete!", pct: 100 }
    toast.success(`Timetable generated! Fitness: ${(tt.fitness_score * 100).toFixed(1)}%`)
    setTimeout(() => router.push(`/timetable/${tt.id}`), 800)
  } catch (e) {
    progress.value = null
    toast.error(e.response?.data?.message || "Generation failed.")
  }
}
</script>

<template>
  <div class="max-w-2xl mx-auto space-y-6 animate-fade-in">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Generate Timetable</h1>
      <p class="text-gray-500 text-sm mt-1">Configure parameters and let the Genetic Algorithm optimize your schedule.</p>
    </div>

    <!-- Generation Progress -->
    <div v-if="progress" class="card">
      <div class="text-center mb-4">
        <div class="text-4xl mb-3">⚙️</div>
        <h3 class="font-semibold text-gray-900">{{ progress.status }}</h3>
      </div>
      <div class="w-full bg-gray-200 rounded-full h-3 mb-2">
        <div class="bg-blue-600 h-3 rounded-full transition-all duration-700" :style="{ width: progress.pct + '%' }"></div>
      </div>
      <p class="text-xs text-gray-500 text-center">{{ progress.pct }}% complete</p>
    </div>

    <form v-else @submit.prevent="generate" class="space-y-6">
      <div class="card space-y-4">
        <h2 class="font-semibold text-gray-900 text-lg">Basic Configuration</h2>
        <div>
          <label class="label">Timetable Name <span class="text-red-500">*</span></label>
          <input v-model="form.name" required class="input" placeholder="e.g. CS Semester 1 – 2025/2026" />
        </div>
        <div>
          <label class="label">Department <span class="text-red-500">*</span></label>
          <select v-model="form.department_id" required class="input">
            <option value="">Select department…</option>
            <option v-for="d in store.departments" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Semester</label>
            <select v-model="form.semester" class="input">
              <option :value="1">Semester 1</option>
              <option :value="2">Semester 2</option>
            </select>
          </div>
          <div>
            <label class="label">Academic Year</label>
            <input v-model="form.academic_year" class="input" placeholder="2025/2026" />
          </div>
        </div>
      </div>

      <!-- Advanced GA Config -->
      <div class="card">
        <button type="button" @click="showAdvanced = !showAdvanced"
          class="flex items-center justify-between w-full text-left">
          <h2 class="font-semibold text-gray-900">Advanced GA Parameters</h2>
          <span class="text-gray-400">{{ showAdvanced ? "▲" : "▼" }}</span>
        </button>
        <div v-if="showAdvanced" class="mt-4 space-y-4 border-t border-gray-100 pt-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="label">Population Size</label>
              <input v-model.number="form.ga_config.population_size" type="number" min="20" max="500" class="input" />
            </div>
            <div>
              <label class="label">Max Generations</label>
              <input v-model.number="form.ga_config.max_generations" type="number" min="10" max="1000" class="input" />
            </div>
          </div>
          <div>
            <label class="label">Fitness Threshold: {{ (form.ga_config.fitness_threshold * 100).toFixed(0) }}%</label>
            <input v-model.number="form.ga_config.fitness_threshold" type="range" min="0.5" max="1" step="0.01" class="w-full" />
            <div class="flex justify-between text-xs text-gray-400 mt-1">
              <span>50% (Fast)</span>
              <span>100% (Perfect)</span>
            </div>
          </div>
          <div class="p-3 bg-blue-50 rounded-lg text-xs text-blue-700">
            <strong>GA Info:</strong> Higher population size = better quality but slower. Higher generations = more
            optimization iterations. The algorithm uses tournament selection, single-point + uniform crossover,
            adaptive mutation, and elitism.
          </div>
        </div>
      </div>

      <button type="submit" :disabled="store.isGenerating" class="btn-primary w-full flex items-center justify-center gap-2 py-3">
        <span class="text-xl">⚡</span>
        Generate Timetable
      </button>
    </form>
  </div>
</template>
