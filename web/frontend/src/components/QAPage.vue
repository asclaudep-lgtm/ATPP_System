<template>
  <div>
    <div class="card">
      <h3>🔍 Ожидают контроля ОТК</h3>
      <table v-if="qaPending.length">
        <thead><tr><th>Операция</th><th>Участок</th><th>Завершена</th></tr></thead>
        <tbody>
          <tr v-for="s in qaPending" :key="s.id">
            <td>{{ s.operation }}</td><td>{{ s.workshop }}</td>
            <td>{{ s.actual_end || '—' }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else style="color:#999;padding:20px;text-align:center">Нет операций, ожидающих ОТК.</p>
    </div>
    <div class="card">
      <h3>Последние проблемы производства</h3>
      <table v-if="issues.length">
        <thead><tr><th>Наряд</th><th>Проблема</th><th>Категория</th><th>Статус</th></tr></thead>
        <tbody>
          <tr v-for="i in issues" :key="i.id">
            <td>{{ i.work_order_id }}</td><td>{{ i.title }}</td>
            <td>{{ i.category }}</td><td>{{ i.status }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else style="color:#999;padding:20px;text-align:center">Проблем не зарегистрировано.</p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'QAPage',
  props: ['api', 'showError'],
  data() { return { qaPending: [], issues: [] } },
  async mounted() {
    try {
      this.qaPending = await this.api('/api/production/qa/pending') || []
      this.issues = await this.api('/api/production/issues') || []
    } catch(e) {}
  },
}
</script>
