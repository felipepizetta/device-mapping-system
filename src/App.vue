<template>
  <div id="app">
    <h1>Sistema de Mapeamento de Dispositivos</h1>
    <div class="dxf-container">
      <!-- Placeholder para visualização de DXF -->
      <p>Área para carregar e visualizar a planta baixa (DXF)</p>
      <button @click="loadDXF">Carregar Planta Baixa</button>
    </div>
  </div>
</template>

<script>
export default {
  name: 'App',
  methods: {
    loadDXF() {
      // Placeholder: Futura integração com dxf-parser ou three.js
      alert('Funcionalidade de carregamento de DXF será implementada.')
    }
  }
}
</script>

<style scoped>
.dxf-container {
  border: 1px solid #ccc;
  padding: 20px;
  margin: 20px;
  min-height: 400px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
</style>