<template>
  <div>
    <h2>Área da Planta Baixa</h2>
    <div>
      <input type="file" accept=".dxf" @change="handleFileUpload" ref="fileInput" />
      <select v-model="selectedFloorPlanIndex" @change="selectFloorPlan" :disabled="!uploadedFloorPlans.length">
        <option v-if="!uploadedFloorPlans.length" disabled value="-1">Nenhuma planta carregada</option>
        <option v-for="(plan, index) in uploadedFloorPlans" :key="index" :value="index">
          {{ plan.name }} {{ plan.id ? `(ID: ${plan.id})` : '' }}
        </option>
      </select>
      <select v-model="selectedDeviceType">
        <option value="Ponto de Acesso">Ponto de Acesso</option>
        <option value="Switch">Switch</option>
        <option value="Computador">Computador</option>
      </select>
      <button @click="saveFloorPlan">Salvar</button>
      <button @click="saveFloorPlanAs">Salvar Como</button>
      <button @click="showFloorPlanList = true">Listar Plantas Baixas</button>
      <button @click="resetView">Restaurar Visualização</button>
      <button @click="toggleGrid">{{ showGrid ? 'Ocultar Grade' : 'Exibir Grade' }}</button>
      <button @click="toggleGridStyle">{{ gridStyle === 'dashed' ? 'Grade Contínua' : 'Grade Tracejada' }}</button>
      <button @click="exportCanvas">Exportar como PNG</button>
      <label>Tamanho da Grade: 
        <input type="number" v-model.number="baseGridSize" min="10" max="100" step="10" />
      </label>
      <label>Cor da Grade: 
        <input type="color" v-model="gridColor" />
      </label>
    </div>
    <div v-if="statusMessage" class="status" :class="{ error: isError }">
      {{ statusMessage }}
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
          <button @click="removeMarkerByIndex(index)">Excluir</button>
        </li>
      </ul>
    </div>

    <!-- Modal para entrada de nome e IP -->
    <div v-if="showMarkerModal" class="modal">
      <div class="modal-content">
        <h3>Adicionar Novo Dispositivo</h3>
        <label>Nome do Equipamento:
          <input type="text" v-model="newMarkerName" placeholder="Ex.: AP1" />
        </label>
        <label>Endereço IP:
          <input type="text" v-model="newMarkerIp" placeholder="Ex.: 192.168.1.1" />
        </label>
        <div class="modal-actions">
          <button @click="confirmMarker">Confirmar</button>
          <button @click="cancelMarker">Cancelar</button>
        </div>
      </div>
    </div>

    <!-- Modal para listar plantas baixas salvas -->
    <div v-if="showFloorPlanList" class="modal">
      <div class="modal-content">
        <h3>Selecionar Planta Baixa Salva</h3>
        <ul v-if="floorPlans.length">
          <li v-for="planId in floorPlans" :key="planId">
            Planta Baixa ID: {{ planId }}
            <button @click="loadFloorPlanById(planId)">Carregar</button>
          </li>
        </ul>
        <p v-else>Nenhuma planta baixa salva disponível.</p>
        <div class="modal-actions">
          <button @click="showFloorPlanList = false">Fechar</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted, computed, watch } from 'vue'
import DxfParser from 'dxf-parser'

interface Marker {
  x: number
  y: number
  type: string
  color: string
  name: string
  ip: string
}

interface FloorPlan {
  id?: string
  name: string
  content: string
  markers: Marker[]
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
    const uploadedFloorPlans = ref<FloorPlan[]>([])
    const selectedFloorPlanIndex = ref(-1)
    const markers = ref<Marker[]>([])
    const selectedDeviceType = ref('Ponto de Acesso')
    const statusMessage = ref<string | null>(null)
    const isError = ref(false)
    const tooltip = ref<string | null>(null)
    const tooltipX = ref(0)
    const tooltipY = ref(0)
    const showGrid = ref(true)
    const baseGridSize = ref(50)
    const gridColor = ref('#000000')
    const gridStyle = ref<'dashed' | 'solid'>('dashed')
    const showMarkerModal = ref(false)
    const newMarkerName = ref('')
    const newMarkerIp = ref('')
    const newMarkerX = ref(0)
    const newMarkerY = ref(0)
    const showFloorPlanList = ref(false)
    const floorPlans = ref<string[]>([])
    let ctx: CanvasRenderingContext2D | null = null
    let dxfData: any = null
    let baseScale: number = 1
    let offsetX: number = 0
    let offsetY: number = 0
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

    const setStatusMessage = (message: string, error: boolean = false) => {
      statusMessage.value = message
      isError.value = error
      setTimeout(() => {
        statusMessage.value = null
        isError.value = false
      }, 5000)
    }

    const handleFileUpload = async (event: Event) => {
      const target = event.target as HTMLInputElement
      const file = target.files?.[0]
      if (!file) {
        setStatusMessage('Nenhum arquivo selecionado.', true)
        return
      }
      if (!file.name.toLowerCase().endsWith('.dxf')) {
        setStatusMessage('Por favor, selecione um arquivo .dxf.', true)
        return
      }

      const reader = new FileReader()
      reader.onload = async (e) => {
        try {
          const content = e.target?.result as string
          if (!content) throw new Error('Conteúdo do arquivo vazio.')

          const parser = new DxfParser()
          const parsedData = parser.parseSync(content)
          console.log('Arquivo DXF carregado:', file.name, 'Tamanho:', content.length)

          const newPlan: FloorPlan = { name: file.name, content, markers: [] }
          uploadedFloorPlans.value = [...uploadedFloorPlans.value, newPlan]
          selectedFloorPlanIndex.value = uploadedFloorPlans.value.length - 1
          dxfData = parsedData
          markers.value = newPlan.markers

          console.log('uploadedFloorPlans:', uploadedFloorPlans.value)
          console.log('selectedFloorPlanIndex:', selectedFloorPlanIndex.value)
          setStatusMessage(`Arquivo ${file.name} carregado com sucesso.`)
          resetView()
          redrawCanvas()
        } catch (error) {
          console.error('Erro ao processar arquivo .dxf:', error)
          setStatusMessage('Falha ao processar o arquivo .dxf. Verifique se o arquivo é válido.', true)
        }
      }
      reader.onerror = () => {
        setStatusMessage('Erro ao ler o arquivo .dxf.', true)
      }
      reader.readAsText(file)
      if (fileInput.value) fileInput.value = ''
    }

    const selectFloorPlan = () => {
      if (selectedFloorPlanIndex.value === -1) {
        dxfData = null
        markers.value = []
        redrawCanvas()
        setStatusMessage('Nenhuma planta baixa selecionada.')
        return
      }

      const plan = uploadedFloorPlans.value[selectedFloorPlanIndex.value]
      if (!plan) {
        setStatusMessage('Planta baixa inválida selecionada.', true)
        return
      }

      console.log('Selecionando planta:', plan.name, 'Índice:', selectedFloorPlanIndex.value)
      try {
        const parser = new DxfParser()
        dxfData = parser.parseSync(plan.content)
        markers.value = plan.markers
        resetView()
        redrawCanvas()
        setStatusMessage(`Planta baixa ${plan.name}${plan.id ? ` (ID: ${plan.id})` : ''} selecionada.`)
      } catch (error) {
        console.error('Erro ao processar planta baixa:', error)
        setStatusMessage('Falha ao carregar a planta baixa selecionada.', true)
        dxfData = null
        markers.value = []
        redrawCanvas()
      }
    }

    watch(uploadedFloorPlans, (newValue) => {
      console.log('uploadedFloorPlans atualizado:', newValue)
    }, { deep: true })

    watch(selectedFloorPlanIndex, (newValue) => {
      console.log('selectedFloorPlanIndex alterado:', newValue)
      selectFloorPlan()
    })

    const saveFloorPlanAs = async () => {
      if (selectedFloorPlanIndex.value === -1) {
        setStatusMessage('Nenhum arquivo .dxf carregado para salvar.', true)
        return
      }
      const currentPlan = uploadedFloorPlans.value[selectedFloorPlanIndex.value]
      if (!currentPlan.markers.length) {
        setStatusMessage('Adicione pelo menos um marcador antes de salvar a planta baixa.', true)
        return
      }

      try {
        setStatusMessage('Salvando nova planta baixa...')
        const response = await fetch('http://localhost:5000/api/floorplan', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            dxfContent: currentPlan.content,
            markers: currentPlan.markers
          })
        })
        if (response.ok) {
          const data = await response.json()
          uploadedFloorPlans.value[selectedFloorPlanIndex.value].id = data.id
          setStatusMessage(`Nova planta baixa salva com ID: ${data.id}. Lista de plantas atualizada.`)
          await fetchFloorPlans()
        } else {
          throw new Error('Falha ao salvar a planta baixa.')
        }
      } catch (error) {
        console.error('Erro ao salvar planta baixa:', error)
        setStatusMessage('Não foi possível salvar a planta baixa. Verifique se o backend está ativo em http://localhost:5000.', true)
      }
    }

    const updateFloorPlan = async () => {
      if (selectedFloorPlanIndex.value === -1) {
        setStatusMessage('Nenhum arquivo .dxf carregado para salvar.', true)
        return
      }
      const currentPlan = uploadedFloorPlans.value[selectedFloorPlanIndex.value]
      if (!currentPlan.markers.length) {
        setStatusMessage('Adicione pelo menos um marcador antes de salvar a planta baixa.', true)
        return
      }
      if (!currentPlan.id) {
        setStatusMessage('Nenhuma ID associada à planta. Use "Salvar Como" para criar uma nova planta.', true)
        return
      }

      try {
        setStatusMessage(`Atualizando planta baixa ID: ${currentPlan.id}...`)
        const response = await fetch(`http://localhost:5000/api/floorplan/${currentPlan.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            dxfContent: currentPlan.content,
            markers: currentPlan.markers
          })
        })
        if (response.ok) {
          const data = await response.json()
          setStatusMessage(`Planta baixa ID: ${data.id} atualizada com sucesso.`)
          await fetchFloorPlans()
        } else {
          throw new Error('Falha ao atualizar a planta baixa.')
        }
      } catch (error) {
        console.error('Erro ao atualizar planta baixa:', error)
        setStatusMessage('Não foi possível atualizar a planta baixa. Verifique se o backend está ativo em http://localhost:5000.', true)
      }
    }

    const saveFloorPlan = async () => {
      const currentPlan = uploadedFloorPlans.value[selectedFloorPlanIndex.value]
      if (currentPlan?.id) {
        await updateFloorPlan()
      } else {
        await saveFloorPlanAs()
      }
    }

    const fetchFloorPlans = async () => {
      try {
        setStatusMessage('Buscando plantas baixas...')
        const response = await fetch('http://localhost:5000/api/floorplans')
        if (response.ok) {
          const data = await response.json()
          floorPlans.value = [...data.floorPlans]
          console.log('floorPlans atualizado:', floorPlans.value)
          setStatusMessage('Plantas baixas carregadas com sucesso.')
        } else {
          throw new Error('Falha ao listar plantas baixas.')
        }
      } catch (error) {
        console.error('Erro ao buscar plantas baixas:', error)
        setStatusMessage('Não foi possível listar plantas baixas. Verifique se o backend está ativo em http://localhost:5000.', true)
      }
    }

    const loadFloorPlanById = async (id: string) => {
      try {
        setStatusMessage(`Carregando planta baixa ID: ${id}...`)
        const response = await fetch(`http://localhost:5000/api/floorplan/${id}`)
        if (response.ok) {
          const data = await response.json()
          const parser = new DxfParser()
          dxfData = parser.parseSync(data.dxfContent)
          const newPlan: FloorPlan = {
            id,
            name: `Planta Baixa ID ${id}`,
            content: data.dxfContent,
            markers: data.markers.map((m: any) => ({
              x: m.x,
              y: m.y,
              type: m.type,
              color: deviceColors[m.type] || 'gray',
              name: m.name,
              ip: m.ip
            }))
          }
          uploadedFloorPlans.value = [...uploadedFloorPlans.value, newPlan]
          selectedFloorPlanIndex.value = uploadedFloorPlans.value.length - 1
          markers.value = newPlan.markers
          resetView()
          redrawCanvas()
          showFloorPlanList.value = false
          setStatusMessage(`Planta baixa ID: ${id} carregada com sucesso.`)
        } else {
          throw new Error('Falha ao carregar a planta baixa.')
        }
      } catch (error) {
        console.error('Erro ao carregar planta baixa:', error)
        setStatusMessage('Não foi possível carregar a planta baixa. Verifique o ID ou confirme se o backend está ativo em http://localhost:5000.', true)
      }
    }

    const exportCanvas = () => {
      if (!canvas.value) return
      const dataUrl = canvas.value.toDataURL('image/png')
      const link = document.createElement('a')
      link.href = dataUrl
      link.download = 'planta_baixa.png'
      link.click()
      setStatusMessage('Planta baixa exportada como PNG.')
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
          openMarkerModal(event)
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

    const openMarkerModal = (event: MouseEvent) => {
      if (!canvas.value || !ctx) return
      const rect = canvas.value.getBoundingClientRect()
      newMarkerX.value = (event.clientX - rect.left - panOffsetX) / (baseScale * zoomLevel)
      newMarkerY.value = (event.clientY - rect.top - panOffsetY) / (baseScale * zoomLevel)
      newMarkerName.value = ''
      newMarkerIp.value = ''
      showMarkerModal.value = true
    }

    const confirmMarker = async () => {
      if (!newMarkerName.value.trim()) {
        setStatusMessage('O nome do equipamento é obrigatório.', true)
        return
      }
      if (!newMarkerIp.value.trim() || !/^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$/.test(newMarkerIp.value)) {
        setStatusMessage('É necessário um endereço IP válido (exemplo: 192.168.1.1).', true)
        return
      }

      let x = newMarkerX.value
      let y = newMarkerY.value
      if (showGrid.value) {
        x = Math.round(x / effectiveGridSize.value) * effectiveGridSize.value
        y = Math.round(y / effectiveGridSize.value) * effectiveGridSize.value
      }

      const newMarker: Marker = {
        x,
        y,
        type: selectedDeviceType.value,
        color: deviceColors[selectedDeviceType.value],
        name: newMarkerName.value,
        ip: newMarkerIp.value
      }

      if (selectedFloorPlanIndex.value !== -1) {
        uploadedFloorPlans.value[selectedFloorPlanIndex.value].markers.push(newMarker)
        markers.value = uploadedFloorPlans.value[selectedFloorPlanIndex.value].markers
      }

      try {
        setStatusMessage('Salvando marcador...')
        const response = await fetch('http://localhost:5000/api/markers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ x, y, type: selectedDeviceType.value, name: newMarkerName.value, ip: newMarkerIp.value })
        })
        if (!response.ok) throw new Error('Failed to save marker')
        setStatusMessage('Marcador adicionado com sucesso.')
      } catch (error) {
        console.error('Erro ao salvar marcador:', error)
        setStatusMessage('Não foi possível salvar o marcador. Verifique se o backend está ativo em http://localhost:5000.', true)
      }

      showMarkerModal.value = false
      redrawCanvas()
    }

    const cancelMarker = () => {
      showMarkerModal.value = false
      newMarkerName.value = ''
      newMarkerIp.value = ''
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
      if (index < 0 || index >= markers.value.length || selectedFloorPlanIndex.value === -1) return

      try {
        setStatusMessage('Excluindo marcador...')
        const response = await fetch(`http://localhost:5000/api/markers/${index}`, {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' }
        })
        if (!response.ok) throw new Error('Failed to delete marker')
        uploadedFloorPlans.value[selectedFloorPlanIndex.value].markers.splice(index, 1)
        markers.value = uploadedFloorPlans.value[selectedFloorPlanIndex.value].markers
        setStatusMessage('Marcador excluído com sucesso.')
        redrawCanvas()
      } catch (error) {
        console.error('Erro ao excluir marcador:', error)
        setStatusMessage('Não foi possível excluir o marcador. Verifique se o backend está ativo em http://localhost:5000.', true)
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

    onMounted(async () => {
      if (canvas.value) {
        ctx = canvas.value.getContext('2d')
      }
      await fetchFloorPlans()
    })

    return {
      canvas,
      fileInput,
      uploadedFloorPlans,
      selectedFloorPlanIndex,
      markers,
      selectedDeviceType,
      statusMessage,
      isError,
      tooltip,
      tooltipStyle,
      showGrid,
      baseGridSize,
      gridColor,
      gridStyle,
      showMarkerModal,
      newMarkerName,
      newMarkerIp,
      showFloorPlanList,
      floorPlans,
      handleFileUpload,
      selectFloorPlan,
      saveFloorPlan,
      saveFloorPlanAs,
      updateFloorPlan,
      fetchFloorPlans,
      loadFloorPlanById,
      exportCanvas,
      handleMouseDown,
      handleMouseUp,
      handleMouseMove,
      openMarkerModal,
      confirmMarker,
      cancelMarker,
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
  width: 200px;
}
select:disabled {
  background-color: #e9ecef;
  cursor: not-allowed;
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
.status {
  margin: 10px 0;
  padding: 10px;
  border-radius: 3px;
}
.status.error {
  color: red;
  background-color: #f8d7da;
}
.status:not(.error) {
  color: green;
  background-color: #d4edda;
}
.tooltip {
  z-index: 1000;
}
label {
  margin: 10px 5px;
}
input[type="number"], input[type="text"] {
  width: 100px;
  padding: 5px;
  border-radius: 3px;
  border: 1px solid #ccc;
}
.modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 2000;
}
.modal-content {
  background: white;
  padding: 20px;
  border-radius: 5px;
  max-width: 400px;
  width: 100%;
}
.modal-content h3 {
  margin-top: 0;
}
.modal-content label {
  display: block;
  margin: 10px 0;
}
.modal-content input {
  width: 100%;
  box-sizing: border-box;
}
.modal-actions {
  margin-top: 20px;
  text-align: right;
}
.modal-actions button {
  margin-left: 10px;
}
.modal ul {
  list-style: none;
  padding: 0;
}
.modal li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 10px 0;
}
.modal li button {
  background-color: #28a745;
}
.modal li button:hover {
  background-color: #218838;
}
</style>