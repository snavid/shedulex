<script setup>
import { computed, reactive, ref, watch } from "vue"
import {
  LEAD_OPTIONS,
  REMINDER_CHANNELS,
  countWeeklyOccurrences,
  formatReminderTime,
  leadLabel,
  nextOccurrence,
} from "@/utils/sessionReminders"

const props = defineProps({
  open: { type: Boolean, default: false },
  entry: { type: Object, default: null },
  contact: { type: Object, default: () => ({ phone: "", email: "" }) },
  semesterEnd: { type: String, default: null },
  existingReminders: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(["close", "save", "cancel-reminder", "go-to-alerts"])

const form = reactive({
  channel: "sms",
  leadTimes: [60],
  scope: "next",
  phone: "",
})

const occurrence = computed(() => {
  if (!props.entry) return null
  return nextOccurrence(props.entry)
})

const userHasPhone = computed(() => !!props.contact?.phone?.trim())
const userHasEmail = computed(() => !!props.contact?.email?.trim())
const effectivePhone = computed(() => props.contact?.phone?.trim() || form.phone?.trim())
const channelNeedsPhone = computed(() => ["sms", "both"].includes(form.channel))
const showPhoneCapture = computed(() => channelNeedsPhone.value && !userHasPhone.value)
const weeklyCount = computed(() => {
  if (!props.entry || !props.semesterEnd || form.scope !== "semester") return 0
  return countWeeklyOccurrences(props.entry, new Date(), props.semesterEnd)
})

const canSubmit = computed(() => {
  if (!form.leadTimes.length || props.saving || !occurrence.value) return false
  if (form.channel === "email") return userHasEmail.value
  if (form.channel === "sms") return !!effectivePhone.value
  if (form.channel === "both") return !!effectivePhone.value && userHasEmail.value
  return false
})

const primaryLabel = computed(() => {
  if (props.saving) return showPhoneCapture.value && form.phone?.trim() ? "Saving…" : "Scheduling…"
  if (showPhoneCapture.value && form.phone?.trim()) return "Save phone & set reminder(s)"
  return "Set reminder(s)"
})

watch(() => props.open, (isOpen) => {
  if (!isOpen) return
  const hasPhone = userHasPhone.value
  const hasEmail = userHasEmail.value
  form.channel = hasPhone ? "sms" : (hasEmail ? "email" : "sms")
  form.leadTimes = [60]
  form.scope = "next"
  form.phone = props.contact?.phone || ""
})

function toggleLead(minutes) {
  const idx = form.leadTimes.indexOf(minutes)
  if (idx >= 0) form.leadTimes.splice(idx, 1)
  else form.leadTimes.push(minutes)
}

function setChannel(channel) {
  if (channel === "email" && !userHasEmail.value) return
  if (channel === "both" && !userHasEmail.value) return
  form.channel = channel
}

function handleSave() {
  emit("save", {
    channel: form.channel,
    leadTimes: [...form.leadTimes],
    scope: form.scope,
    phone: form.phone?.trim() || null,
    occurrence: occurrence.value,
    repeatWeeklyUntil: form.scope === "semester" ? props.semesterEnd : null,
  })
}
</script>

<template>
  <Teleport to="body">
    <Transition name="sheet-fade">
      <div v-if="open" class="fixed inset-0 z-50 flex items-end sm:items-center sm:justify-center">
        <div class="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" @click="emit('close')" />

        <div class="relative z-10 max-h-[90vh] w-full overflow-y-auto rounded-t-3xl bg-white shadow-2xl sm:max-w-lg sm:rounded-2xl">
          <div class="sticky top-0 z-10 border-b border-slate-100 bg-white px-5 pb-4 pt-3">
            <div class="mx-auto mb-3 h-1 w-10 rounded-full bg-slate-200 sm:hidden" />
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="text-[11px] font-semibold uppercase tracking-wider text-blue-600">Class reminder</p>
                <h3 class="truncate text-lg font-bold text-slate-900">
                  {{ entry?.course?.name || entry?.course?.code || "Session" }}
                </h3>
                <p v-if="occurrence" class="mt-0.5 text-sm text-slate-500">
                  Next: {{ occurrence.toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) }}
                  · {{ entry?.room?.name || "TBA" }}
                </p>
              </div>
              <button type="button" class="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600" @click="emit('close')">
                <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          <div class="space-y-5 px-5 py-4">
            <!-- Scope -->
            <div>
              <label class="text-xs font-semibold text-slate-600">When to apply</label>
              <div class="mt-2 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  class="rounded-xl border px-3 py-2.5 text-left text-sm transition"
                  :class="form.scope === 'next'
                    ? 'border-blue-300 bg-blue-50 text-blue-900 ring-1 ring-blue-200'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'"
                  @click="form.scope = 'next'"
                >
                  <span class="font-semibold">Next class only</span>
                  <span class="mt-0.5 block text-xs opacity-80">One upcoming session</span>
                </button>
                <button
                  type="button"
                  class="rounded-xl border px-3 py-2.5 text-left text-sm transition"
                  :class="form.scope === 'semester'
                    ? 'border-indigo-300 bg-indigo-50 text-indigo-900 ring-1 ring-indigo-200'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'"
                  @click="form.scope = 'semester'"
                >
                  <span class="font-semibold">Every week</span>
                  <span class="mt-0.5 block text-xs opacity-80">
                    <template v-if="weeklyCount">~{{ weeklyCount }} classes until semester end</template>
                    <template v-else>Through semester end</template>
                  </span>
                </button>
              </div>
            </div>

            <!-- Lead times -->
            <div>
              <label class="text-xs font-semibold text-slate-600">Remind me</label>
              <div class="mt-2 grid grid-cols-2 gap-2">
                <label
                  v-for="opt in LEAD_OPTIONS"
                  :key="opt.minutes"
                  class="flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2.5 text-sm transition"
                  :class="form.leadTimes.includes(opt.minutes)
                    ? 'border-blue-300 bg-blue-50 text-blue-900'
                    : 'border-slate-200 bg-white text-slate-600'"
                >
                  <input
                    type="checkbox"
                    class="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    :checked="form.leadTimes.includes(opt.minutes)"
                    @change="toggleLead(opt.minutes)"
                  />
                  {{ opt.label }}
                </label>
              </div>
            </div>

            <!-- Channel -->
            <div>
              <label class="text-xs font-semibold text-slate-600">How to notify</label>
              <div class="mt-2 flex overflow-hidden rounded-xl border border-slate-200">
                <button
                  v-for="ch in REMINDER_CHANNELS"
                  :key="ch.value"
                  type="button"
                  class="flex-1 py-2.5 text-xs font-semibold transition"
                  :class="form.channel === ch.value ? 'bg-blue-600 text-white' : 'bg-white text-slate-600 hover:bg-slate-50'"
                  @click="setChannel(ch.value)"
                >
                  {{ ch.label }}
                </button>
              </div>
            </div>

            <!-- Contact strip -->
            <div v-if="userHasPhone && channelNeedsPhone" class="rounded-xl bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
              SMS to <strong>{{ contact.phone }}</strong>
            </div>
            <div v-else-if="form.channel === 'email' && userHasEmail" class="rounded-xl bg-blue-50 px-3 py-2 text-xs text-blue-800">
              Email to <strong>{{ contact.email }}</strong>
            </div>
            <div v-else-if="form.channel === 'both' && userHasPhone && userHasEmail" class="rounded-xl bg-emerald-50 px-3 py-2 text-xs text-emerald-800">
              SMS + email to your saved contacts
            </div>
            <div v-if="showPhoneCapture" class="space-y-2 rounded-xl bg-amber-50 px-3 py-3 text-xs text-amber-900">
              <p>Enter your phone number for SMS reminders.</p>
              <input v-model="form.phone" type="tel" class="input w-full text-sm" placeholder="+255712345678" />
              <button type="button" class="text-blue-700 hover:underline" @click="emit('go-to-alerts')">
                Or update in Reminders &amp; Alerts
              </button>
            </div>

            <!-- Existing -->
            <div v-if="existingReminders.length" class="space-y-2">
              <p class="text-xs font-semibold text-slate-600">Scheduled for this class</p>
              <div
                v-for="rem in existingReminders"
                :key="rem.id"
                class="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-xs"
              >
                <span>{{ leadLabel(rem.lead_minutes) }} · {{ formatReminderTime(rem.scheduled_at) }}</span>
                <button type="button" class="font-medium text-red-600 hover:underline" @click="emit('cancel-reminder', rem.id)">
                  Cancel
                </button>
              </div>
            </div>

            <button
              type="button"
              class="btn-primary w-full py-3 text-sm font-semibold"
              :disabled="!canSubmit"
              @click="handleSave"
            >
              {{ primaryLabel }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.sheet-fade-enter-active,
.sheet-fade-leave-active {
  transition: opacity 0.2s ease;
}
.sheet-fade-enter-from,
.sheet-fade-leave-to {
  opacity: 0;
}
</style>
