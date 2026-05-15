<template>
  <div>
    <div class="card">
      <h3>📋 Журнал изменений</h3>
      <div style="display:flex;gap:8px;margin-bottom:12px">
        <select v-model="filterEntity" @change="loadAudit" style="padding:6px">
          <option value="">Все типы</option>
          <option value="TechProcess">Техпроцессы</option>
          <option value="Product">Изделия</option>
          <option value="WorkOrder">Наряды</option>
          <option value="Operation">Операции</option>
          <option value="User">Пользователи</option>
        </select>
        <select v-model="filterAction" @change="loadAudit" style="padding:6px">
          <option value="">Все действия</option>
          <option value="create">Создание</option>
          <option value="update">Изменение</option>
          <option value="delete">Удаление</option>
          <option value="approve">Утверждение</option>
          <option value="batch_approve">Массовое утв.</option>
          <option value="batch_assign">Массовое назн.</option>
        </select>
      </div>
      <table>
        <thead><tr><th>Время</th><th>Пользователь</th><th>Тип</th><th>Действие</th><th>Описание</th><th>Изменения</th></tr></thead>
        <tbody>
          <tr v-for="e in entries" :key="e.id">
            <td style="font-size:11px;white-space:nowrap">{{ e.timestamp?.slice(0,16) }}</td>
            <td>{{ e.user_name || '-' }}</td>
            <td>{{ e.entity_type }}</td>
            <td><span class="status" :class="'status-'+actionClass(e.action)">{{ e.action }}</span></td>
            <td style="font-size:12px">{{ e.description }}</td>
            <td style="font-size:11px">
              <span v-if="e.changes" style="cursor:pointer;color:#1976d2" @click="showDiff(e)">
                {{ Object.keys(e.changes).length }} пол.
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="card" v-if="diffEntry">
      <h3>Изменения полей — запись #{{ diffEntry.id }}</h3>
      <table>
        <thead><tr><th>Поле</th><th>Было</th><th>Стало</th></tr></thead>
        <tbody>
          <tr v-for="(v,k) in diffEntry.changes" :key="k">
            <td><b>{{ k }}</b></td>
            <td style="color:#c0392b">{{ v.before }}</td>
            <td style="color:#27ae60">{{ v.after }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AuditPage',
  props: ['api', 'showError'],
  data() { return { entries: [], filterEntity: '', filterAction: '', diffEntry: null } },
  methods: {
    async loadAudit() {
      const params = new URLSearchParams()
      if (this.filterEntity) params.set('entity_type', this.filterEntity)
      if (this.filterAction) params.set('action', this.filterAction)
      params.set('limit', '200')
      try { this.entries = await this.api('/api/audit?' + params) || [] } catch(e) {}
    },
    showDiff(e) { this.diffEntry = e },
    actionClass(a) {
      if (a === 'create') return 'approved'
      if (a === 'delete') return 'draft'
      if (a === 'approve' || a === 'batch_approve') return 'approved'
      return 'in-progress'
    },
  },
  async mounted() { this.loadAudit() },
}
</script>
