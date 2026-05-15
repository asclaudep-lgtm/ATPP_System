<template>
  <div :style="{marginLeft:'20px',padding:'4px 0'}">
    <span :style="{fontWeight:node.has_tp?'bold':'normal'}">
      📦 {{ node.designation }} — {{ node.name }}
    </span>
    <span style="color:#666;font-size:12px;margin-left:8px">
      {{ node.level }} ×{{ node.quantity }}
      <span v-if="node.position">({{ node.position }})</span>
      <span class="badge" :style="{background:node.has_tp?'#d4edda':'#fff3cd'}">{{ node.has_tp?'ТП есть':'Нет ТП'}}</span>
    </span>
    <BomNode v-for="c in node.children" :key="c.id" :node="c" />
  </div>
</template>

<script>
export default {
  name: 'BomNode',
  props: ['node'],
}
</script>

<style scoped>
.badge { display:inline-block; padding:2px 6px; border-radius:3px; font-size:10px; margin-left:4px }
</style>
