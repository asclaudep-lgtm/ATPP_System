<template>
  <div id="app-root">
    <!-- Login -->
    <div v-if="!token" class="login-form">
      <h2>ATPP System v14</h2>
      <input v-model="login.username" placeholder="Логин" @keyup.enter="doLogin" />
      <input v-model="login.password" type="password" placeholder="Пароль" @keyup.enter="doLogin" />
      <div class="error" v-if="loginError">{{ loginError }}</div>
      <button @click="doLogin">Войти</button>
    </div>

    <!-- Main app -->
    <div v-else>
      <header class="header">
        <h1>ATPP Web v14</h1>
        <div>
          <span>{{ user.full_name || user.username }}</span>
          <button class="logout-btn" @click="logout">Выход</button>
        </div>
      </header>

      <div v-if="error" class="error-bar">
        <span>{{ error }}</span>
        <button @click="error=''">&times;</button>
      </div>

      <nav class="nav">
        <button v-for="p in pages" :key="p.id"
          :class="{ active: page === p.id }"
          @click="switchPage(p.id)">{{ p.label }}</button>
      </nav>

      <DashboardPage v-if="page==='dashboard'" :key="'dash-'+token" :api="api" :showError="showError" />
      <ProductsPage v-if="page==='products'" :key="'prod-'+token" :api="api" :showError="showError" />
      <TPsPage v-if="page==='tps'" :key="'tps-'+token" :api="api" :showError="showError" />
      <PDOPage v-if="page==='pdo'" :key="'pdo-'+token" :api="api" :showError="showError" />
      <ProductionPage v-if="page==='production'" :key="'prod-'+token" :api="api" :showError="showError" />
      <QAPage v-if="page==='qa'" :key="'qa-'+token" :api="api" :showError="showError" />
      <ToolingPage v-if="page==='tooling'" :key="'tool-'+token" :api="api" :showError="showError" />
      <OrdersPage v-if="page==='orders'" :key="'ord-'+token" :api="api" :showError="showError" />
      <AuditPage v-if="page==='audit'" :key="'audit-'+token" :api="api" :showError="showError" />
      <BatchOpsPage v-if="page==='batch'" :key="'batch-'+token" :api="api" :showError="showError" />
    </div>
  </div>
</template>

<script>
import DashboardPage from './components/DashboardPage.vue'
import ProductsPage from './components/ProductsPage.vue'
import TPsPage from './components/TPsPage.vue'
import PDOPage from './components/PDOPage.vue'
import ProductionPage from './components/ProductionPage.vue'
import QAPage from './components/QAPage.vue'
import ToolingPage from './components/ToolingPage.vue'
import OrdersPage from './components/OrdersPage.vue'
import AuditPage from './components/AuditPage.vue'
import BatchOpsPage from './components/BatchOpsPage.vue'

export default {
  name: 'App',
  components: { DashboardPage, ProductsPage, TPsPage, PDOPage, ProductionPage, QAPage, ToolingPage, OrdersPage, AuditPage, BatchOpsPage },
  data() {
    return {
      token: localStorage.getItem('atpp_token'),
      user: JSON.parse(localStorage.getItem('atpp_user') || '{}'),
      login: { username: '', password: '' },
      loginError: '', page: 'dashboard', error: '',
      pages: [
        { id: 'dashboard', label: '📊 Дашборд' },
        { id: 'products', label: '📦 Изделия' },
        { id: 'tps', label: '📋 Техпроцессы' },
        { id: 'pdo', label: '📋 ПДО' },
        { id: 'production', label: '🏭 Производство' },
        { id: 'qa', label: '🔍 ОТК' },
        { id: 'tooling', label: '🧰 Оснастка' },
        { id: 'orders', label: '📋 Наряды' },
        { id: 'audit', label: '📋 Аудит' },
        { id: 'batch', label: '⚡ Batch-операции' },
      ],
    }
  },
  methods: {
    async api(path, opts = {}) {
      const h = { 'Content-Type': 'application/json' }
      if (this.token) h['Authorization'] = 'Bearer ' + this.token
      const r = await fetch(path, { headers: h, ...opts })
      return r.status === 204 ? null : r.json()
    },
    async doLogin() {
      this.loginError = ''
      try {
        const d = await this.api('/api/auth/login', { method: 'POST', body: JSON.stringify(this.login) })
        if (!d?.access_token) { this.loginError = 'Неверный логин/пароль'; return }
        this.token = d.access_token; this.user = d.user
        localStorage.setItem('atpp_token', this.token)
        localStorage.setItem('atpp_user', JSON.stringify(this.user))
      } catch (e) { this.loginError = 'Ошибка подключения' }
    },
    logout() { localStorage.removeItem('atpp_token'); localStorage.removeItem('atpp_user'); this.token = ''; this.user = {} },
    showError(msg) { this.error = msg; setTimeout(() => this.error = '', 8000) },
    switchPage(p) { this.page = p },
  },
}
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0 }
body { font-family: system-ui, sans-serif; background: #f0f2f5; color: #333 }
#app-root { max-width: 1200px; margin: 0 auto; padding: 16px }
.header { display: flex; justify-content: space-between; align-items: center;
  background: #fff; padding: 12px 20px; border-radius: 8px; margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,.1) }
.header h1 { font-size: 20px; color: #1976d2 }
.nav { display: flex; gap: 4px; margin-bottom: 16px; flex-wrap: wrap }
.nav button { padding: 8px 14px; border: none; border-radius: 6px; cursor: pointer;
  background: #e3e8ef; font-size: 12px; white-space: nowrap }
.nav button.active { background: #1976d2; color: #fff }
.card { background: #fff; border-radius: 8px; padding: 20px; margin-bottom: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,.08) }
.login-form { max-width: 400px; margin: 100px auto; padding: 32px; background: #fff;
  border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.15) }
.login-form input { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ddd;
  border-radius: 4px; font-size: 14px }
.login-form button { width: 100%; padding: 10px; background: #1976d2; color: #fff;
  border: none; border-radius: 4px; font-size: 16px; cursor: pointer; margin-top: 12px }
.error { color: #d32f2f; font-size: 12px; margin-top: 4px }
.error-bar { background: #ffebee; color: #c62828; padding: 10px 16px; margin-bottom: 12px;
  border-radius: 4px; display: flex; justify-content: space-between; align-items: center }
.logout-btn { padding: 4px 12px; cursor: pointer }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px }
.stat { padding: 16px; text-align: center; border-radius: 8px;
  background: linear-gradient(135deg, #667eea, #764ba2); color: #fff }
.stat .num { font-size: 28px; font-weight: bold }
.stat .lbl { font-size: 12px; opacity: .85; margin-top: 4px }
table { width: 100%; border-collapse: collapse; margin-top: 12px }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; font-size: 13px }
th { background: #f8f9fa; font-weight: 600; color: #666 }
.status { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600 }
.status-draft { background: #fff3cd; color: #856404 }
.status-approved { background: #d4edda; color: #155724 }
.status-in-progress { background: #d1ecf1; color: #0c5460 }
.chart-box { width: 100%; height: 280px; margin-top: 12px }
.barcode-input { font-size: 24px; padding: 12px; width: 100%; border: 2px solid #1976d2;
  border-radius: 8px; text-align: center; letter-spacing: 2px; margin-bottom: 16px }
</style>
