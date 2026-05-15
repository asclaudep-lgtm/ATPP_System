import { createApp } from 'vue'
import App from './App.vue'

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/static/sw.js')
}

const app = createApp(App)
app.mount('#app')
