<template>
  <div>
    <h2>Área da Planta Baixa</h2>
    <div>
      <input type="file" accept=".dxf" @change="handleFileUpload" ref="fileInput" />
      <select v-model="selectedDeviceType">
        <option value="Ponto de Acesso">Ponto de Acesso</option>
        <option value="Switch">Switch</option>
        <option value="Computador">Computador</option>
      </select>
      <button @click="saveFloorPlan">Salvar Planta Baixa</button>
      <button @click="loadFloorPlanFromServer">Carregar Planta Baixa</button>
      <button @click="resetView">Redefinir Visualização</button>
      <button @click="toggleGrid">{{ showGrid ? 'Ocultar Grade' : 'Exibir Grade' }}</button>
      <button @click="toggleGridStyle">{{ gridStyle === 'dashed' ? 'Grade Sólida' : 'Grade Tracejada' }}</button>
      <button @click="exportCanvas">Exportar como PNG</button>
      <label>Tamanho da Grade: 
        <input type="number" v-model.number="baseGridSize" min="10" max="100" step="10" />
      </label>
      <label>Cor da Grade: 
        <input type="color" v-model="gridColor" />
      </label>
    </div>
    <div v-if="errorMessage" class="error">
      {{ errorMessage }}
    </div>
    <div v-if="tooltip" class="tooltip" :style="tooltipStyle">
      {{ tooltip }}
    </div>
    <canvas 
      id="floor-plan-canvas" 
      ref="canvas" 
      width="800" 
      height="600" 
      style="border: 1px solid black;" 
      @mousedown="handleMouseDown"
      @mousemove="handleMouseMove"
      @mouseup="handleMouseUp"
      @contextmenu.prevent="removeMarker"
      @wheel="zoom"
    ></canvas>
    <div>
      <h3>Dispositivos Posicionados:</h3>
      <ul>
        <li v-for="(marker, index) in markers" :key="index">
          {{ marker.type }}: {{ marker.name }} (IP: {{ marker.ip }}) em ({{ marker.x.toFixed(2) }}, {{ marker.y.toFixed(2) }})
          <button @click="removeMarkerByIndex(index)">Remover</button>
        </li>
      </ul>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted, computed } from 'vue'
import DxfParser from 'dxf-parser'

interface Marker {
  x: number
  y: number
  type: string
  color: string
  name: string
  ip: string
}

interface Bounds {
  minX: number
  minY: number
  maxX: number
  maxY: number
}

export default defineComponent({
  name: 'App',
  setup() {
    const canvas = ref<HTMLCanvasElement | null>(null)
    const fileInput = ref<HTMLInputElement | null>(null)
    const markers = ref<Marker[]>([])
    const selectedDeviceType = ref('Ponto de Acesso')
    const errorMessage = ref<string | null>(null)
    const tooltip = ref<string | null>(null)
    const tooltipX = ref(0)
    const tooltipY = ref(0)
    const showGrid = ref(true)
    const baseGridSize = ref(50)
    const gridColor = ref('#000000')
    const gridStyle = ref<'dashed' | 'solid'>('dashed')
    let ctx: CanvasRenderingContext2D | null = null
    let dxfData: any = null
    let baseScale: number = 1
    let offsetX: number = 0
    let offsetY: number = 0
    let currentDxfContent: string | null = null
    let zoomLevel: number = 1
    let panOffsetX: number = 0
    let panOffsetY: number = 0
    let isPanning: boolean = false
    let startPanX: number = 0
    let startPanY: number = 0
    let isDragging: boolean = false
    let mouseDownX: number = 0
    let mouseDownY: number = 0
    let hoverGridPoint: { x: number; y: number } | null = null

    const deviceColors: { [key: string]: string } = {
      'Ponto de Acesso': 'red',
      'Switch': 'blue',
      'Computador': 'green'
    }

    const effectiveGridSize = computed(() => {
      const factor = Math.max(0.5, Math.min(2, 1 / zoomLevel))
      return baseGridSize.value * factor
    })

    const tooltipStyle = computed(() => ({
      position: 'absolute',
      left: `${tooltipX.value}px`,
      top: `${tooltipY.value}px`,
      background: 'rgba(0, 0, 0, 0.8)',
      color: 'white',
      padding: '5px',
      borderRadius: '3px',
      pointerEvents: 'none'
    }))

    const handleFileUpload = (event: Event) => {
      const target = event.target as HTMLInputElement
      const file = target.files?.[0]
      if (!file) return

      const reader = new FileReader()
      reader.onload = async (e) => {
        try {
          currentDxfContent = e.target?.result as string
          const parser = new DxfParser()
          dxfData = await parser.parse(currentDxfContent)
          console.log('Dados DXF Processados:', dxfData)
          errorMessage.value = null
          resetView()
          await loadFloorPlan()
        } catch (error) {
          console.error('Erro ao processar arquivo .dxf:', error)
          errorMessage.value = 'Falha ao processar o arquivo .dxf. Verifique o console para detalhes ou assegure-se de que é um arquivo .dxf válido.'
        }
      }
      reader.readAsText(file)
    }

    const loadFloorPlan = async () => {
      if (!canvas.value) return
      ctx = canvas.value.getContext('2d')
      if (!ctx) return

      redrawCanvas()
      try {
        errorMessage.value = null
        const response = await fetch('http://localhost:5000/api/markers')
        if (response.ok) {
          const data = await response.json()
          markers.value = data.map((m: any) => ({
            x: m.x,
            y: m.y,
            type: m.type,
            color: deviceColors[m.type],
            name: m.name,
            ip: m.ip
          }))
          redrawCanvas()
        } else {
          errorMessage.value = 'Falha ao carregar marcadores do servidor'
        }
      } catch (error) {
        console.error('Erro ao buscar marcadores:', error)
        errorMessage.value = 'Não foi possível conectar ao servidor. Verifique se o backend está em execução em http://localhost:5000'
      }
    }

    const saveFloorPlan = async () => {
      if (!currentDxfContent) {
        errorMessage.value = 'Nenhum arquivo .dxf carregado para salvar'
        return
      }

      try {
        errorMessage.value = null
        const response = await fetch('http://localhost:5000/api/floorplan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            dxfContent: currentDxfContent,
            markers: markers.value.map(m => ({ x: m.x, y: m.y, type: m.type, name: m.name, ip: m.ip }))
          })
        })
        if (response.ok) {
          const data = await response.json()
          errorMessage.value = `Planta baixa salva com ID: ${data.id}`
        } else {
          throw new Error('Falha ao salvar a planta baixa')
        }
      } catch (error) {
        console.error('Erro ao salvar planta baixa:', error)
        errorMessage.value = 'Não foi possível salvar a planta baixa. Verifique se o backend está em execução em http://localhost:5000'
      }
    }

    const loadFloorPlanFromServer = async () => {
      const id = prompt('Digite o ID da planta baixa para carregar:')
      if (!id) return

      try {
        errorMessage.value = null
        const response = await fetch(`http://localhost:5000/api/floorplan/${id}`)
        if (response.ok) {
          const data = await response.json()
          currentDxfContent = data.dxfContent
          const parser = new DxfParser()
          dxfData = await parser.parse(currentDxfContent)
          markers.value = data.markers.map((m: any) => ({
            x: m.x,
            y: m.y,
            type: m.type,
            color: deviceColors[m.type],
            name: m.name,
            ip: m.ip
          }))
          resetView()
          await loadFloorPlan()
        } else {
          throw new Error('Falha ao carregar a planta baixa')
        }
      } catch (error) {
        console.error('Erro ao carregar planta baixa:', error)
        errorMessage.value = 'Não foi possível carregar a planta baixa. Verifique o ID ou assegure-se de que o backend está em execução em http://localhost:5000'
      }
    }

    const exportCanvas = () => {
      if (!canvas.value) return
      const dataUrl = canvas.value.toDataURL('image/png')
      const link = document.createElement('a')
      link.href = dataUrl
      link.download = 'planta_baixa.png'
      link.click()
      errorMessage.value = 'Planta baixa exportada como PNG'
    }

    const getDxfBounds = (dxf: any): Bounds => {
      let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
      dxf.entities.forEach((entity: any) => {
        if (entity.type === 'LINE' || entity.type === 'POLYLINE' || entity.type === 'LWPOLYLINE') {
          entity.vertices.forEach((vertex: any) => {
            minX = Math.min(minX, vertex.x)
            minY = Math.min(minY, vertex.y)
            maxX = Math.max(maxX, vertex.x)
            maxY = Math.max(maxY, vertex.y)
          })
        } else if (entity.type === 'CIRCLE' || entity.type === 'ARC') {
          minX = Math.min(minX, entity.center.x - entity.radius)
          minY = Math.min(minY, entity.center.y - entity.radius)
          maxX = Math.max(maxX, entity.center.x + entity.radius)
          maxY = Math.max(maxY, entity.center.y + entity.radius)
        }
      })
      return { minX, minY, maxX, maxY }
    }

    const handleMouseDown = (event: MouseEvent) => {
      if (!canvas.value) return
      const rect = canvas.value.getBoundingClientRect()
      mouseDownX = event.clientX - rect.left
      mouseDownY = event.clientY - rect.top
      isDragging = false

      if (event.button === 0) {
        isPanning = true
        startPanX = event.clientX - panOffsetX
        startPanY = event.clientY - panOffsetY
      }
    }

    const handleMouseUp = (event: MouseEvent) => {
      if (!canvas.value) return
      const rect = canvas.value.getBoundingClientRect()
      const mouseUpX = event.clientX - rect.left
      const mouseUpY = event.clientY - rect.top

      if (event.button === 0) {
        isPanning = false
        if (!isDragging && Math.hypot(mouseUpX - mouseDownX, mouseUpY - mouseDownY) < 5) {
          placeMarker(event)
        }
      }
    }

    const handleMouseMove = (event: MouseEvent) => {
      if (!canvas.value || !ctx) return
      const rect = canvas.value.getBoundingClientRect()
      const x = (event.clientX - rect.left - panOffsetX) / (baseScale * zoomLevel)
      const y = (event.clientY - rect.top - panOffsetY) / (baseScale * zoomLevel)

      if (showGrid.value) {
        hoverGridPoint = {
          x: Math.round(x / effectiveGridSize.value) * effectiveGridSize.value,
          y: Math.round(y / effectiveGridSize.value) * effectiveGridSize.value
        }
      } else {
        hoverGridPoint = null
      }

      if (isPanning) {
        isDragging = true
        panOffsetX = event.clientX - startPanX
        panOffsetY = event.clientY - startPanY
        redrawCanvas()
      }

      const hoveredMarker = markers.value.find(m =>
        Math.hypot(m.x - x, m.y - y) < 10 / (baseScale * zoomLevel)
      )
      if (hoveredMarker) {
        tooltip.value = `${hoveredMarker.type}: ${hoveredMarker.name} (IP: ${hoveredMarker.ip}) em (${hoveredMarker.x.toFixed(2)}, ${hoveredMarker.y.toFixed(2)})`
        tooltipX.value = event.clientX + 10
        tooltipY.value = event.clientY + 10
      } else {
        tooltip.value = null
      }

      redrawCanvas()
    }

    const placeMarker = async (event: MouseEvent) => {
      if (!canvas.value || !ctx) return

      const rect = canvas.value.getBoundingClientRect()
      let x = (event.clientX - rect.left - panOffsetX) / (baseScale * zoomLevel)
      let y = (event.clientY - rect.top - panOffsetY) / (baseScale * zoomLevel)

      x = Math.round(x / effectiveGridSize.value) * effectiveGridSize.value
      y = Math.round(y / effectiveGridSize.value) * effectiveGridSize.value

      const name = prompt('Digite o nome do equipamento:')?.trim()
      if (!name) {
        errorMessage.value = 'O nome do equipamento é obrigatório'
        return
      }
      const ip = prompt('Digite o endereço IP:')?.trim()
      if (!ip || !/^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$/.test(ip)) {
        errorMessage.value = 'É necessário um endereço IP válido (por exemplo, 192.168.1.1)'
        return
      }

      const newMarker: Marker = {
        x,
        y,
        type: selectedDeviceType.value,
        color: deviceColors[selectedDeviceType.value],
        name,
        ip
      }
      markers.value.push(newMarker)

      try {
        errorMessage.value = null
        const response = await fetch('http://localhost:5000/api/markers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ x, y, type: selectedDeviceType.value, name, ip })
        })
        if (!response.ok) throw new Error('Failed to save marker')
      } catch (error) {
        console.error('Erro ao salvar marcador:', error)
        errorMessage.value = 'Não foi possível salvar o marcador. Verifique se o backend está em execução em http://localhost:5000'
      }

      redrawCanvas()
    }

    const removeMarker = (event: MouseEvent) => {
      if (!canvas.value || !ctx) return

      const rect = canvas.value.getBoundingClientRect()
      const x = (event.clientX - rect.left - panOffsetX) / (baseScale * zoomLevel)
      const y = (event.clientY - rect.top - panOffsetY) / (baseScale * zoomLevel)

      const index = markers.value.findIndex(m =>
        Math.hypot(m.x - x, m.y - y) < 10 / (baseScale * zoomLevel)
      )
      if (index !== -1) {
        removeMarkerByIndex(index)
      }
    }

    const removeMarkerByIndex = async (index: number) => {
      if (index < 0 || index >= markers.value.length) return

      try {
        errorMessage.value = null
        const response = await fetch(`http://localhost:5000/api/markers/${index}`, {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' }
        })
        if (!response.ok) throw new Error('Failed to delete marker')
        markers.value.splice(index, 1)
        redrawCanvas()
      } catch (error) {
        console.error('Erro ao excluir marcador:', error)
        errorMessage.value = 'Não foi possível excluir o marcador. Verifique se o backend está em execução em http://localhost:5000'
      }
    }

    const toggleGrid = () => {
      showGrid.value = !showGrid.value
      redrawCanvas()
    }

    const toggleGridStyle = () => {
      gridStyle.value = gridStyle.value === 'dashed' ? 'solid' : 'dashed'
      redrawCanvas()
    }

    const zoom = (event: WheelEvent) => {
      event.preventDefault()
      if (!canvas.value) return

      const rect = canvas.value.getBoundingClientRect()
      const mouseX = event.clientX - rect.left
      const mouseY = event.clientY - rect.top

      const zoomFactor = event.deltaY < 0 ? 1.1 : 0.9
      const newZoomLevel = Math.max(0.5, Math.min(zoomLevel * zoomFactor, 5))

      const worldXBefore = (mouseX - panOffsetX) / (baseScale * zoomLevel)
      const worldYBefore = (mouseY - panOffsetY) / (baseScale * zoomLevel)

      zoomLevel = newZoomLevel

      panOffsetX = mouseX - worldXBefore * baseScale * zoomLevel
      panOffsetY = mouseY - worldYBefore * baseScale * zoomLevel

      redrawCanvas()
    }

    const resetView = () => {
      zoomLevel = 1
      panOffsetX = 0
      panOffsetY = 0
      redrawCanvas()
    }

    const redrawCanvas = () => {
      if (!ctx || !canvas.value) return
      ctx.clearRect(0, 0, canvas.value.width, canvas.value.height)
      ctx.save()
      ctx.translate(panOffsetX, panOffsetY)
      ctx.scale(baseScale * zoomLevel, baseScale * zoomLevel)

      ctx.fillStyle = '#f0f0f0'
      ctx.fillRect(0, 0, canvas.value.width / (baseScale * zoomLevel), canvas.value.height / (baseScale * zoomLevel))

      if (showGrid.value) {
        ctx.strokeStyle = gridColor.value
        ctx.lineWidth = 0.5 / (baseScale * zoomLevel)
        if (gridStyle.value === 'dashed') {
          ctx.setLineDash([2 / (baseScale * zoomLevel), 2 / (baseScale * zoomLevel)])
        } else {
          ctx.setLineDash([])
        }

        const viewMinX = -panOffsetX / (baseScale * zoomLevel)
        const viewMinY = -panOffsetY / (baseScale * zoomLevel)
        const viewMaxX = (canvas.value.width - panOffsetX) / (baseScale * zoomLevel)
        const viewMaxY = (canvas.value.height - panOffsetY) / (baseScale * zoomLevel)

        const gridSize = effectiveGridSize.value
        const startX = Math.floor(viewMinX / gridSize) * gridSize
        const startY = Math.floor(viewMinY / gridSize) * gridSize
        const endX = Math.ceil(viewMaxX / gridSize) * gridSize
        const endY = Math.ceil(viewMaxY / gridSize) * gridSize

        for (let x = startX; x <= endX; x += gridSize) {
          ctx.beginPath()
          ctx.moveTo(x, viewMinY)
          ctx.lineTo(x, viewMaxY)
          ctx.stroke()
        }
        for (let y = startY; y <= endY; y += gridSize) {
          ctx.beginPath()
          ctx.moveTo(viewMinX, y)
          ctx.lineTo(viewMaxX, y)
          ctx.stroke()
        }
        ctx.setLineDash([])

        if (hoverGridPoint) {
          ctx.beginPath()
          ctx.arc(hoverGridPoint.x, hoverGridPoint.y, 3 / (baseScale * zoomLevel), 0, 2 * Math.PI)
          ctx.fillStyle = 'rgba(255, 165, 0, 0.5)'
          ctx.fill()
        }
      }

      if (dxfData) {
        const bounds = getDxfBounds(dxfData)
        const dxfWidth = bounds.maxX - bounds.minX
        const dxfHeight = bounds.maxY - bounds.minY
        const canvasWidth = canvas.value.width
        const canvasHeight = canvas.value.height

        const scaleX = canvasWidth / dxfWidth
        const scaleY = canvasHeight / dxfHeight
        baseScale = Math.min(scaleX, scaleY) * 0.9

        const scaledWidth = dxfWidth * baseScale
        const scaledHeight = dxfHeight * baseScale
        offsetX = (canvasWidth - scaledWidth) / 2 - bounds.minX * baseScale
        offsetY = (canvasHeight - scaledHeight) / 2 - bounds.minY * baseScale

        ctx.strokeStyle = '#000'
        ctx.lineWidth = 1 / (baseScale * zoomLevel)

        dxfData.entities.forEach((entity: any) => {
          if (entity.type === 'LINE') {
            const x1 = entity.vertices[0].x
            const y1 = entity.vertices[0].y
            const x2 = entity.vertices[1].x
            const y2 = entity.vertices[1].y
            ctx.beginPath()
            ctx.moveTo(x1, y1)
            ctx.lineTo(x2, y2)
            ctx.stroke()
          } else if (entity.type === 'POLYLINE' || entity.type === 'LWPOLYLINE') {
            ctx.beginPath()
            entity.vertices.forEach((vertex: any, index: number) => {
              const x = vertex.x
              const y = vertex.y
              if (index === 0) {
                ctx.moveTo(x, y)
              } else {
                ctx.lineTo(x, y)
              }
            })
            if (entity.shape) ctx.closePath()
            ctx.stroke()
          } else if (entity.type === 'CIRCLE') {
            const cx = entity.center.x
            const cy = entity.center.y
            const r = entity.radius
            ctx.beginPath()
            ctx.arc(cx, cy, r, 0, 2 * Math.PI)
            ctx.stroke()
          } else if (entity.type === 'ARC') {
            const cx = entity.center.x
            const cy = entity.center.y
            const r = entity.radius
            const startAngle = entity.startAngle * Math.PI / 180
            const endAngle = entity.endAngle * Math.PI / 180
            ctx.beginPath()
            ctx.arc(cx, cy, r, startAngle, endAngle)
            ctx.stroke()
          }
        })
      } else {
        ctx.strokeStyle = '#000'
        ctx.lineWidth = 2 / (baseScale * zoomLevel)
        ctx.strokeRect(50 / baseScale, 50 / baseScale, 700 / baseScale, 500 / baseScale)
        ctx.strokeRect(200 / baseScale, 100 / baseScale, 150 / baseScale, 100 / baseScale)
        ctx.strokeRect(400 / baseScale, 100 / baseScale, 150 / baseScale, 100 / baseScale)
      }

      markers.value.forEach(marker => {
        const canvasX = marker.x
        const canvasY = marker.y

        ctx.beginPath()
        ctx.arc(canvasX, canvasY, 5 / (baseScale * zoomLevel), 0, 2 * Math.PI)
        ctx.fillStyle = marker.color
        ctx.fill()
        ctx.strokeStyle = 'black'
        ctx.stroke()

        ctx.font = `${12 / (baseScale * zoomLevel)}px Arial`
        ctx.fillStyle = 'black'
        ctx.textAlign = 'center'
        ctx.fillText(marker.name, canvasX, canvasY - 10 / (baseScale * zoomLevel))
      })

      ctx.restore()
    }

    onMounted(() => {
      if (canvas.value) {
        ctx = canvas.value.getContext('2d')
      }
    })

    return {
      canvas,
      fileInput,
      markers,
      selectedDeviceType,
      errorMessage,
      tooltip,
      tooltipStyle,
      showGrid,
      baseGridSize,
      gridColor,
      gridStyle,
      handleFileUpload,
      loadFloorPlan,
      saveFloorPlan,
      loadFloorPlanFromServer,
      exportCanvas,
      handleMouseDown,
      handleMouseUp,
      handleMouseMove,
      placeMarker,
      removeMarker,
      removeMarkerByIndex,
      toggleGrid,
      toggleGridStyle,
      zoom,
      resetView
    }
  }
})
</script>

<style scoped>
#floor-plan-canvas {
  background-color: #f0f0f0;
  margin-top: 10px;
}
input[type="file"], input[type="color"] {
  margin: 10px 5px;
}
select {
  margin: 10px 5px;
  padding: 5px;
  border-radius: 3px;
}
button {
  margin: 10px 5px;
  padding: 5px 10px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 3px;
  cursor: pointer;
}
button:hover {
  background-color: #0056b3;
}
li button {
  margin-left: 10px;
  background-color: #dc3545;
}
li button:hover {
  background-color: #c82333;
}
.error {
  color: red;
  margin: 10px 0;
}
.tooltip {
  z-index: 1000;
}
label {
  margin: 10px 5px;
}
input[type="number"] {
  width: 60px;
  padding: 5px;
  border-radius: 3px;
  border: 1px solid #ccc;
}
</style>