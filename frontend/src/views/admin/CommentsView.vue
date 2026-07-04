<script setup>
import { onMounted, ref } from "vue"
import { adminCommentsApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const comments = ref([])
const savingId = ref("")

async function loadComments() {
  loading.value = true
  try {
    const { data } = await adminCommentsApi.list({ per_page: 100 })
    comments.value = data.data || []
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load comments."))
  } finally {
    loading.value = false
  }
}

async function hideComment(comment) {
  savingId.value = comment.id
  try {
    const { data } = await adminCommentsApi.update(comment.id, { status: "hidden" })
    const idx = comments.value.findIndex((c) => c.id === comment.id)
    if (idx >= 0) comments.value[idx] = data.data
    toast.success("Comment hidden.")
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to update comment."))
  } finally {
    savingId.value = ""
  }
}

async function showComment(comment) {
  savingId.value = comment.id
  try {
    const { data } = await adminCommentsApi.update(comment.id, { status: "visible" })
    const idx = comments.value.findIndex((c) => c.id === comment.id)
    if (idx >= 0) comments.value[idx] = data.data
    toast.success("Comment restored.")
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to update comment."))
  } finally {
    savingId.value = ""
  }
}

function sessionLabel(entry) {
  if (!entry) return "—"
  const slot = entry.time_slot
  const course = entry.course?.name || entry.course?.code || "Class"
  return `${slot?.day || "?"} ${slot?.start_time || ""} — ${course}`
}

onMounted(loadComments)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">Student Comments</h1>
      <p class="text-sm text-gray-500 mt-1">Feedback submitted by students through the public portal.</p>
    </div>

    <div v-if="loading" class="card">
      <div class="space-y-3">
        <div v-for="i in 4" :key="i" class="h-16 bg-gray-100 rounded-lg animate-pulse" />
      </div>
    </div>

    <div v-else-if="!comments.length" class="card text-center py-12 text-sm text-gray-500">
      No student comments yet.
    </div>

    <div v-else class="space-y-3">
      <div
        v-for="comment in comments"
        :key="comment.id"
        class="card flex flex-col lg:flex-row lg:items-start gap-4"
      >
        <div class="flex-1 min-w-0 space-y-2">
          <div class="flex flex-wrap items-center gap-2">
            <p class="font-semibold text-gray-900">{{ comment.student_name || comment.registration_number }}</p>
            <span
              :class="comment.status === 'visible' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
              class="text-xs font-semibold px-2 py-0.5 rounded-full capitalize"
            >
              {{ comment.status }}
            </span>
          </div>
          <p class="text-sm text-gray-700">{{ comment.body }}</p>
          <p class="text-xs text-gray-500">
            {{ sessionLabel(comment.entry) }} · {{ new Date(comment.created_at).toLocaleString() }}
          </p>
        </div>
        <div class="flex gap-2 flex-shrink-0">
          <button
            v-if="comment.status === 'visible'"
            class="btn-secondary text-sm"
            :disabled="savingId === comment.id"
            @click="hideComment(comment)"
          >
            Hide
          </button>
          <button
            v-else
            class="btn-secondary text-sm"
            :disabled="savingId === comment.id"
            @click="showComment(comment)"
          >
            Show
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
