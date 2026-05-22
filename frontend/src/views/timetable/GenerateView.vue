<script setup>
import { ref, onMounted, computed, watch } from "vue"
import { useRouter } from "vue-router"
import { useTimetableStore } from "@/stores/timetable"
import { resourcesApi, calendarApi, timetableApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"

const store = useTimetableStore()
const router = useRouter()
const toast = useToast()

const programs = ref([])
const templates = ref([])
const semesters = ref([])
const conflictPreview = ref(null)
const generatedId = ref(null)

const form = ref({
  name: "",
  department_id: "",
  program_id: "",
  template_id: "",
  calendar_semester_id: "",
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

// ── Progress stages ─────────────────────────────────────────────────────────
const STAGES = [
  { key: "init",        label: "Initialising genetic algorithm…",       pct: 5,  icon: "⚙️" },
  { key: "population",  label: "Creating guided initial population…",   pct: 15, icon: "🧬" },
  { key: "eval1",       label: "Running initial fitness evaluation…",   pct: 28, icon: "📊" },
  { key: "crossover",   label: "Selection, crossover & mutation…",      pct: 45, icon: "🔀" },
  { key: "evolving",    label: "Evolving across generations…",          pct: 60, icon: "📈" },
  { key: "constraint",  label: "Applying constraint penalty scoring…",  pct: 72, icon: "⚖️" },
  { key: "elitism",     label: "Elitism: preserving best solutions…",   pct: 82, icon: "🏆" },
  { key: "converge",    label: "Converging towards optimal fitness…",   pct: 91, icon: "🎯" },
  { key: "finalise",    label: "Finalising and persisting timetable…",  pct: 97, icon: "💾" },
  { key: "done",        label: "Generation complete!",                  pct: 100, icon: "✅" },
]

const filteredPrograms = computed(() =>
  form.value.department_id
    ? programs.value.filter(p => p.department_id === form.value.department_id)
    : programs.value
)

// Auto-populate semester from selected calendar semester
watch(() => form.value.calendar_semester_id, (id) => {
  const sem = semesters.value.find(s => s.id === id)
  if (sem) {
    form.value.semester = sem.semester_number
    form.value.academic_year = sem.academic_year
  }
})
watch(() => form.value.department_id, () => { form.value.program_id = "" })

onMounted(async () => {
  await store.fetchDepartments()
  const [pr, tr, sr] = await Promise.all([
    resourcesApi.programs(),
    resourcesApi.templates(),
    calendarApi.semesters(),
  ])
  programs.value = pr.data.data || []
  templates.value = tr.data.data || []
  semesters.value = sr.data.data || []
  // Pre-select current semester if available
  const current = semesters.value.find(s => s.is_current)
  if (current) form.value.calendar_semester_id = current.id
})

let stageInterval = null

function startProgressAnimation() {
  let idx = 0
  progress.value = { ...STAGES[0] }
  stageInterval = setInterval(() => {
    idx++
    if (idx < STAGES.length - 1) {
      progress.value = { ...STAGES[idx] }
    }
  }, 2200)
}

function stopProgressAnimation(success = true) {
  clearInterval(stageInterval)
  stageInterval = null
  if (success) {
    progress.value = { ...STAGES[STAGES.length - 1] }
  } else {
    progress.value = null
  }
}

async function generate() {
  if (!form.value.department_id || !form.value.name) {
    toast.error("Please fill in the timetable name and select a department.")
    return
  }
  conflictPreview.value = null
  generatedId.value = null
  startProgressAnimation()

  try {
    const payload = {
      name: form.value.name,
      department_id: form.value.department_id,
      program_id: form.value.program_id || undefined,
      template_id: form.value.template_id || undefined,
      calendar_semester_id: form.value.calendar_semester_id || undefined,
      semester: form.value.semester,
      academic_year: form.value.academic_year,
      ga_config: form.value.ga_config,
    }
    const tt = await store.generateTimetable(payload)
    stopProgressAnimation(true)
    generatedId.value = tt.id

    // Fetch violations/conflicts for preview
    try {
      const [cv, vr] = await Promise.all([
        timetableApi.conflicts(tt.id),
        timetableApi.violations(tt.id),
      ])
      const conflicts = cv.data.data || []
      const violations = vr.data.data || []
      if (conflicts.length || violations.length) {
        conflictPreview.value = { conflicts, violations }
      }
    } catch { /* non-fatal */ }

    const score = (tt.fitness_score * 100).toFixed(1)
    toast.success(`Timetable generated! Fitness: ${score}% · ${tt.generations_run} generations`)
  } catch (e) {
    stopProgressAnimation(false)
    toast.error(getErrorMessage(e, "Timetable generation failed."))
  }
}

function viewTimetable() {
  if (generatedId.value) router.push(`/timetable/${generatedId.value}`)
}
</script>

<template>
  <div class="max-w-2xl mx-auto space-y-6 animate-fade-in">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Generate Timetable</h1>
      <p class="text-gray-500 text-sm mt-1">Configure parameters and let the Genetic Algorithm optimise your schedule.</p>
    </div>

    <!-- ── Generation Progress ── -->
    <div v-if="progress" class="card">
      <div class="text-center mb-5">
        <div class="text-5xl mb-3 animate-bounce">{{ progress.icon }}</div>
        <h3 class="font-semibold text-gray-900 text-lg">{{ progress.label }}</h3>
        <p class="text-sm text-gray-500 mt-1">{{ progress.pct }}% complete</p>
      </div>
      <div class="w-full bg-gray-200 rounded-full h-3 overflow-hidden mb-3">
        <div class="bg-gradient-to-r from-blue-500 to-indigo-600 h-3 rounded-full transition-all duration-1000"
          :style="{ width: progress.pct + '%' }"></div>
      </div>

      <!-- Stage timeline -->
      <div class="flex justify-between mt-2">
        <div v-for="(stage, i) in STAGES.filter((_,i) => i % 3 === 0)" :key="i"
          class="text-center">
          <div class="w-2 h-2 rounded-full mx-auto mb-0.5"
            :class="progress.pct >= stage.pct ? 'bg-blue-600' : 'bg-gray-200'"></div>
          <span class="text-xs text-gray-400 hidden md:block">{{ stage.icon }}</span>
        </div>
      </div>
    </div>

    <!-- ── Post-generation preview ── -->
    <div v-else-if="generatedId" class="space-y-4">
      <!-- Success card -->
      <div class="card bg-green-50 border-green-200 text-center py-6">
        <div class="text-4xl mb-2">✅</div>
        <h3 class="font-semibold text-green-900 text-lg">Timetable generated successfully!</h3>
        <button class="btn-primary mt-4" @click="viewTimetable">View Timetable</button>
      </div>

      <!-- Conflict preview -->
      <div v-if="conflictPreview" class="card border-amber-200 bg-amber-50 space-y-3">
        <h4 class="font-semibold text-amber-900 flex items-center gap-2">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
          </svg>
          {{ conflictPreview.conflicts.length + conflictPreview.violations.length }} constraint notes
        </h4>
        <div class="space-y-1.5 max-h-48 overflow-y-auto">
          <div v-for="c in [...conflictPreview.violations, ...conflictPreview.conflicts]" :key="c.message"
            class="flex items-start gap-2 text-xs">
            <span :class="c.severity === 'high' ? 'text-red-600' : c.severity === 'medium' ? 'text-amber-600' : 'text-gray-500'"
              class="mt-0.5 flex-shrink-0 font-bold">
              {{ c.severity === 'high' ? '⛔' : c.severity === 'medium' ? '⚠️' : 'ℹ️' }}
            </span>
            <div>
              <span class="font-semibold text-gray-700">{{ c.rule || c.type }}</span>
              <span class="text-gray-500 ml-1">— {{ c.message }}</span>
            </div>
          </div>
        </div>
        <p class="text-xs text-amber-700">These are informational. The timetable has been saved and can be manually adjusted.</p>
      </div>

      <button class="btn-secondary w-full" @click="generatedId = null; conflictPreview = null">
        Generate Another Timetable
      </button>
    </div>

    <!-- ── Generation form ── -->
    <form v-else @submit.prevent="generate" class="space-y-6">
      <!-- Basic config -->
      <div class="card space-y-4">
        <h2 class="font-semibold text-gray-900 text-lg">Basic Configuration</h2>

        <div>
          <label class="label">Timetable Name <span class="text-red-500">*</span></label>
          <input v-model="form.name" required class="input" placeholder="e.g. CS Semester 1 – 2025/2026"/>
        </div>

        <div>
          <label class="label">Department <span class="text-red-500">*</span></label>
          <select v-model="form.department_id" required class="input">
            <option value="">Select department…</option>
            <option v-for="d in store.departments" :key="d.id" :value="d.id">{{ d.name }}</option>
          </select>
        </div>

        <div v-if="filteredPrograms.length">
          <label class="label">Programme <span class="text-xs text-gray-400">(optional)</span></label>
          <select v-model="form.program_id" class="input">
            <option value="">Entire department (all programmes)</option>
            <option v-for="p in filteredPrograms" :key="p.id" :value="p.id">
              {{ p.name }} ({{ p.code }}) — {{ p.academic_level }}
            </option>
          </select>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Academic Semester</label>
            <select v-model="form.calendar_semester_id" class="input">
              <option value="">Manual entry below</option>
              <option v-for="s in semesters" :key="s.id" :value="s.id">
                {{ s.name }} ({{ s.academic_year }}) {{ s.is_current ? "· Current" : "" }}
              </option>
            </select>
          </div>
          <div>
            <label class="label">Schedule Template</label>
            <select v-model="form.template_id" class="input">
              <option value="">Use all time slots</option>
              <option v-for="t in templates" :key="t.id" :value="t.id">
                {{ t.name }}{{ t.is_default ? " (default)" : "" }}
              </option>
            </select>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4" v-if="!form.calendar_semester_id">
          <div>
            <label class="label">Semester Number</label>
            <select v-model="form.semester" class="input">
              <option :value="1">Semester 1</option>
              <option :value="2">Semester 2</option>
            </select>
          </div>
          <div>
            <label class="label">Academic Year</label>
            <input v-model="form.academic_year" class="input" placeholder="2025/2026"/>
          </div>
        </div>
      </div>

      <!-- Advanced GA config -->
      <div class="card">
        <button type="button" @click="showAdvanced = !showAdvanced"
          class="flex items-center justify-between w-full text-left">
          <h2 class="font-semibold text-gray-900">Advanced GA Parameters</h2>
          <span class="text-gray-400 text-lg">{{ showAdvanced ? "▲" : "▼" }}</span>
        </button>

        <div v-if="showAdvanced" class="mt-4 space-y-4 border-t border-gray-100 pt-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="label">Population Size
                <span class="text-xs text-gray-400 font-normal">(20–500)</span>
              </label>
              <input v-model.number="form.ga_config.population_size" type="number" min="20" max="500" class="input"/>
            </div>
            <div>
              <label class="label">Max Generations
                <span class="text-xs text-gray-400 font-normal">(50–1000)</span>
              </label>
              <input v-model.number="form.ga_config.max_generations" type="number" min="50" max="1000" class="input"/>
            </div>
          </div>

          <div>
            <label class="label">
              Fitness Threshold: <strong>{{ (form.ga_config.fitness_threshold * 100).toFixed(0) }}%</strong>
              <span class="text-xs text-gray-400 font-normal"> — stop when this score is reached</span>
            </label>
            <input v-model.number="form.ga_config.fitness_threshold" type="range" min="0.5" max="1" step="0.01" class="w-full accent-blue-600"/>
            <div class="flex justify-between text-xs text-gray-400 mt-1">
              <span>50% Fast</span><span>75% Balanced</span><span>95% Optimal</span><span>100% Perfect</span>
            </div>
          </div>

          <div class="p-3 bg-blue-50 rounded-xl text-xs text-blue-700 space-y-1">
            <p><strong>Algorithm:</strong> Multi-strategy crossover (single-point, two-point, uniform) + guided mutation + parallel fitness evaluation.</p>
            <p><strong>Constraints loaded:</strong> All active DB constraints + template slot filtering + lecturer availability.</p>
            <p><strong>Tip:</strong> Start with pop=100, gen=300, threshold=0.95 for most departments. Increase for large universities.</p>
          </div>
        </div>
      </div>

      <button type="submit" :disabled="store.isGenerating" class="btn-primary w-full flex items-center justify-center gap-3 py-3.5 text-base">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/>
        </svg>
        Generate Timetable
      </button>
    </form>
  </div>
</template>
