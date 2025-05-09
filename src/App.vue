<template>
  <div>
    <h2>Área da Planta Baixa</h2>
    <div>
      <input type="file" accept=".dxf" @change="handleFileUpload" ref="fileInput" />
      <select v-model="selectedFloorPlanIndex" @change="confirmSelectFloorPlan" :disabled="!uploadedFloorPlans.length">
        <option v-if="!uploadedFloorPlans.length" disabled value="-1">Nenhuma planta carregada</option>
        <option v-for="(plan, index) in uploadedFloorPlans" :key="index" :value="index">
          {{ plan.name }} {{ plan.id ? `(ID: ${plan.id})` : '' }} {{ plan.isModified ? '*' : '' }}
        </option>
      </select>
      <select v-model="selectedDeviceType">
        <option value="Ponto de Acesso">Ponto de Acesso</option>
        <option value="Switch">Switch</option>
        <option value="Computador">Computador</option>
      </select>
      <select v-model="filterDeviceType" @change="redrawCanvas">
        <option value="">Todos os Dispositivos</option>
        <option value="Ponto de Acesso">Ponto de Acesso</option>
        <option value="Switch">Switch</option>
        <option value="Computador">Computador</option>
      </select>
      <button @click="saveFloorPlan">Salvar</button>
      <button @click="openSaveAsModal">Salvar Como</button>
      <button @click="showFloorPlanList = true">Listar Plantas Baixas</button>
      <button @click="resetView">Restaurar Visualização</button>
      <button @click="undo" :disabled="historyIndex <= -1 || actionHistory.length === 0">Desfazer</button>
      <button @click="redo" :disabled="historyIndex >= actionHistory.length - 1 || actionHistory.length === 0">Refazer</button>
      <button @click="toggleGrid">{{ showGrid ? 'Ocultar Grade' : 'Exibir Grade' }}</button>
      <button @click="toggleGridStyle">{{ gridStyle === 'dashed' ? 'Grade Contínua' : 'Grade Tracejada' }}</button>
      <button @click="toggleConnections">{{ showConnections ? 'Ocultar Conexões' : 'Exibir Conexões' }}</button>
      <button @click="exportCanvas">Exportar como PNG</button>
      <label>Tamanho da Grade:
        <input type="number" v-model.number="baseGridSize" min="10" max="100" step="10" />
      </label>
      <label>Cor da Grade:
        <input type="color" v-model="gridColor" />
      </label>
    </div>
    <div v-if="statusMessage" class="floating-notification" :class="{ error: isError }">
      {{ statusMessage }}
      <button @click="clearStatusMessage">×</button>
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
      @dblclick="handleDoubleClick"
    ></canvas>
    <div>
      <h3>Dispositivos Posicionados:</h3>
      <ul>
        <li v-for="(marker, index) in filteredMarkers" :key="index">
          {{ marker.type }}: {{ marker.name }} (IP: {{ marker.ip }}, Status: {{ marker.status }}) em ({{ marker.x.toFixed(2) }}, {{ marker.y.toFixed(2) }})
          Conexões: {{ formatConnections(marker.connections) }}
          <button @click="removeMarkerByIndex(index)">Excluir</button>
        </li>
      </ul>
    </div>

    <!-- Modal para entrada de nome, IP, status e conexões -->
    <div v-if="showMarkerModal" class="modal">
      <div class="modal-content">
        <h3>{{ editMode ? 'Editar Dispositivo' : 'Adicionar Novo Dispositivo' }}</h3>
        <label>Tipo do Equipamento:
          <select v-model="selectedDeviceType">
            <option value="Ponto de Acesso">Ponto de Acesso</option>
            <option value="Switch">Switch</option>
            <option value="Computador">Computador</option>
          </select>
        </label>
        <label>Nome do Equipamento:
          <input type="text" v-model="newMarkerName" placeholder="Ex.: AP1" />
        </label>
        <label>Endereço IP:
          <input type="text" v-model="newMarkerIp" placeholder="Ex.: 192.168.1.1" />
        </label>
        <label>Status:
          <select v-model="newMarkerStatus">
            <option value="online">Online</option>
            <option value="offline">Offline</option>
          </select>
        </label>
        <label>Conexões:
          <div v-for="(conn, index) in newMarkerConnections" :key="index" class="connection-entry">
            <select v-model="conn.target" @change="validateConnectionTarget(index)">
              <option value="" disabled>Selecione um dispositivo</option>
              <option v-for="marker in markers" :key="marker.name" :value="marker.name" :disabled="marker.name === newMarkerName">
                {{ marker.name }} ({{ marker.type }})
              </option>
            </select>
            <select v-model="conn.type">
              <option value="wired">Com fio</option>
              <option value="wireless">Sem fio</option>
            </select>
            <select v-model="conn.direction">
              <option value="to">Para</option>
              <option value="from">De</option>
              <option value="both">Bidirecional</option>
            </select>
            <button @click="removeConnection(index)">-</button>
          </div>
          <button @click="addConnection">+ Adicionar Conexão</button>
        </label>
        <div class="modal-actions">
          <button @click="confirmMarker">{{ editMode ? 'Salvar' : 'Confirmar' }}</button>
          <button @click="cancelMarker">Cancelar</button>
        </div>
      </div>
    </div>

    <!-- Modal para salvar como -->
    <div v-if="showSaveAsModal" class="modal">
      <div class="modal-content">
        <h3>Salvar Planta Baixa Como</h3>
        <label>Nome da Planta Baixa:
          <input type="text" v-model="newPlanName" placeholder="Ex.: Planta do Escritório" />
        </label>
        <div class="modal-actions">
          <button @click="saveFloorPlanAs">Salvar</button>
          <button @click="showSaveAsModal = false">Cancelar</button>
        </div>
      </div>
    </div>

    <!-- Modal para listar plantas baixas salvas -->
    <div v-if="showFloorPlanList" class="modal">
      <div class="modal-content">
        <h3>Selecionar Planta Baixa Salva</h3>
        <ul v-if="floorPlans.length">
          <li v-for="plan in floorPlans" :key="plan.id">
            {{ plan.name }} (ID: {{ plan.id }})
            <button @click="loadFloorPlanById(plan.id)">Carregar</button>
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
import { defineComponent, ref, onMounted, computed, reactive, watch } from 'vue'
import DxfParser from 'dxf-parser'

interface Connection {
  target: string // Nome do marcador conectado
  type: 'wired' | 'wireless'
  direction: 'to' | 'from' | 'both'
}

interface Marker {
  x: number
  y: number
  type: string
  color: string
  name: string
  ip: string
  status: 'online' | 'offline'
  connections: Connection[]
}

interface FloorPlan {
  id?: string
  name: string
  content: string
  markers: Marker[]
  isModified: boolean
}

interface Bounds {
  minX: number
  minY: number
  maxX: number
  maxY: number
}

interface Settings {
  showGrid: boolean
  showConnections: boolean
  gridStyle: 'dashed' | 'solid'
  baseGridSize: number
  gridColor: string
}

interface Action {
  type: string // 'add' | 'edit' | 'move' | 'delete' | 'toggle_grid' | 'toggle_connections' | 'toggle_grid_style' | 'change_grid_size' | 'change_grid_color'
  previousState: {
    markers: Marker[]
    settings: Settings
  }
  newState: {
    markers: Marker[]
    settings: Settings
  }
}

export default defineComponent({
  name: 'App',
  setup() {
    // Constantes
    const BACKEND_URL = 'http://localhost:5000'
    const DEVICE_COLORS: { [key: string]: string } = {
      'Ponto de Acesso': 'red',
      'Switch': 'blue',
      'Computador': 'green'
    }
    const STATUS_COLORS: { [key: string]: string } = {
      'online': 'green',
      'offline': 'gray'
    }
    const CONNECTION_STYLES = {
      wired: { lineWidth: 3, dash: [], colorActive: '#00ff00', colorInactive: '#ff0000' },
      wireless: { lineWidth: 2, dash: [5, 5], colorActive: '#00ccff', colorInactive: '#ff6666' }
    }
    const MINIMUM_DISTANCE = 10
    const MAX_HISTORY = 10

    // Estado reativo
    const canvas = ref<HTMLCanvasElement | null>(null)
    const fileInput = ref<HTMLInputElement | null>(null)
    const uploadedFloorPlans = reactive<FloorPlan[]>([])
    const selectedFloorPlanIndex = ref(-1)
    const markers = ref<Marker[]>([])
    const selectedDeviceType = ref('Ponto de Acesso')
    const filterDeviceType = ref<string>('')
    const statusMessage = ref<string | null>(null)
    const isError = ref(false)
    const tooltip = ref<string | null>(null)
    const tooltipX = ref(0)
    const tooltipY = ref(0)
    const showGrid = ref(true)
    const showConnections = ref(true)
    const baseGridSize = ref(50)
    const gridColor = ref('#000000')
    const gridStyle = ref<'dashed' | 'solid'>('dashed')
    const showMarkerModal = ref(false)
    const newMarkerName = ref('')
    const newMarkerIp = ref('')
    const newMarkerX = ref(0)
    const newMarkerY = ref(0)
    const newMarkerStatus = ref<'online' | 'offline'>('online')
    const newMarkerConnections = ref<Connection[]>([])
    const editMode = ref(false)
    const editMarkerIndex = ref<number | null>(null)
    const showFloorPlanList = ref(false)
    const showSaveAsModal = ref(false)
    const newPlanName = ref('')
    const floorPlans = ref<{ id: string; name: string }[]>([])
    const actionHistory = ref<Action[]>([])
    const historyIndex = ref(-1)
    const hoveredMarker = ref<Marker | null>(null)
    let ctx: CanvasRenderingContext2D | null = null
    let dxfData: any = null
    let baseScale = 1
    let offsetX = 0
    let offsetY = 0
    let zoomLevel = 1
    let panOffsetX = 0
    let panOffsetY = 0
    let isPanning = false
    let startPanX = 0
    let startPanY = 0
    let isDragging = false
    let draggedMarkerIndex = ref<number | null>(null)
    let mouseDownX = 0
    let mouseDownY = 0
    let hoverGridPoint: { x: number; y: number } | null = null
    let lastClickTime = 0
    const blinkState = ref(true)

    // Computados
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

    const currentPlan = computed(() => {
      return selectedFloorPlanIndex.value !== -1 ? uploadedFloorPlans[selectedFloorPlanIndex.value] : null
    })

    const filteredMarkers = computed(() => {
      if (!filterDeviceType.value) {
        return markers.value
      }
      return markers.value.filter(marker => marker.type === filterDeviceType.value)
    })

    // Funções utilitárias
    const setStatusMessage = (message: string, error = false) => {
      statusMessage.value = message
      isError.value = error
      setTimeout(() => {
        statusMessage.value = null
        isError.value = false
      }, 10000)
    }

    const clearStatusMessage = () => {
      statusMessage.value = null
      isError.value = false
    }

    const markPlanAsModified = () => {
      if (selectedFloorPlanIndex.value !== -1) {
        uploadedFloorPlans[selectedFloorPlanIndex.value].isModified = true
      }
    }

    const getNearestMarkerIndex = (x: number, y: number, excludeIndex: number | null = null) => {
      let nearestIndex = -1
      let minDistance = MINIMUM_DISTANCE / (baseScale * zoomLevel)

      markers.value.forEach((marker, index) => {
        if (excludeIndex !== null && index === excludeIndex) return
        const distance = Math.hypot(marker.x - x, marker.y - y)
        if (distance < minDistance) {
          minDistance = distance
          nearestIndex = index
        }
      })

      return nearestIndex
    }

    const formatConnections = (connections: Connection[]) => {
      if (!connections.length) return 'Nenhuma'
      return connections.map(c => `${c.target} (${c.type}, ${c.direction})`).join(', ')
    }

    // Funções de conexão
    const addConnection = () => {
      newMarkerConnections.value.push({ target: '', type: 'wired', direction: 'both' })
    }

    const removeConnection = (index: number) => {
      newMarkerConnections.value.splice(index, 1)
    }

    const validateConnectionTarget = (index: number) => {
      const conn = newMarkerConnections.value[index]
      if (conn.target === newMarkerName.value) {
        conn.target = ''
        setStatusMessage('Um dispositivo não pode se conectar a si mesmo.', true)
      }
      // Remove duplicatas
      const targets = newMarkerConnections.value.map(c => c.target)
      if (targets.indexOf(conn.target) !== targets.lastIndexOf(conn.target)) {
        conn.target = ''
        setStatusMessage('Conexão duplicada detectada.', true)
      }
    }

    // Funções de Desfazer/Refazer
    const getCurrentSettings = (): Settings => ({
      showGrid: showGrid.value,
      showConnections: showConnections.value,
      gridStyle: gridStyle.value,
      baseGridSize: baseGridSize.value,
      gridColor: gridColor.value
    })

    const deepCopyMarkers = (markers: Marker[]): Marker[] => {
      return markers.map(marker => ({
        ...marker,
        connections: marker.connections.map(c => ({ ...c }))
      }))
    }

    const addActionToHistory = (actionType: string, previousMarkers: Marker[], newMarkers: Marker[], previousSettings: Settings, newSettings: Settings) => {
      if (historyIndex.value < actionHistory.value.length - 1) {
        actionHistory.value.splice(historyIndex.value + 1)
      }
      actionHistory.value.push({
        type: actionType,
        previousState: {
          markers: deepCopyMarkers(previousMarkers),
          settings: { ...previousSettings }
        },
        newState: {
          markers: deepCopyMarkers(newMarkers),
          settings: { ...newSettings }
        }
      })
      historyIndex.value = actionHistory.value.length - 1

      if (actionHistory.value.length > MAX_HISTORY) {
        actionHistory.value.shift()
        historyIndex.value--
      }
      console.log('Histórico atualizado:', actionType, 'Índice:', historyIndex.value)
    }

    const undo = () => {
      if (historyIndex.value < 0 || actionHistory.value.length === 0 || selectedFloorPlanIndex.value === -1) {
        console.log('Não é possível desfazer: sem ações ou sem planta selecionada.')
        return
      }

      const action = actionHistory.value[historyIndex.value]
      console.log('Desfazendo ação:', action.type)

      markers.value = deepCopyMarkers(action.previousState.markers)
      uploadedFloorPlans[selectedFloorPlanIndex.value].markers = [...markers.value]
      showGrid.value = action.previousState.settings.showGrid
      showConnections.value = action.previousState.settings.showConnections
      gridStyle.value = action.previousState.settings.gridStyle
      baseGridSize.value = action.previousState.settings.baseGridSize
      gridColor.value = action.previousState.settings.gridColor

      historyIndex.value--
      markPlanAsModified()
      redrawCanvas()
      setStatusMessage(`Ação desfeita: ${action.type.replace('_', ' ')}.`)
    }

    const redo = () => {
      if (historyIndex.value >= actionHistory.value.length - 1 || actionHistory.value.length === 0 || selectedFloorPlanIndex.value === -1) {
        console.log('Não é possível refazer: sem ações futuras ou sem planta selecionada.')
        return
      }

      historyIndex.value++
      const action = actionHistory.value[historyIndex.value]
      console.log('Refazendo ação:', action.type)

      markers.value = deepCopyMarkers(action.newState.markers)
      uploadedFloorPlans[selectedFloorPlanIndex.value].markers = [...markers.value]
      showGrid.value = action.newState.settings.showGrid
      showConnections.value = action.newState.settings.showConnections
      gridStyle.value = action.newState.settings.gridStyle
      baseGridSize.value = action.newState.settings.baseGridSize
      gridColor.value = action.newState.settings.gridColor

      markPlanAsModified()
      redrawCanvas()
      setStatusMessage(`Ação refeita: ${action.type.replace('_', ' ')}.`)
    }

    // Manipulação de arquivo DXF
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

          const newPlan: FloorPlan = { name: file.name, content, markers: [], isModified: false }
          uploadedFloorPlans.push(newPlan)
          selectedFloorPlanIndex.value = uploadedFloorPlans.length - 1
          dxfData = parsedData
          markers.value = newPlan.markers
          actionHistory.value = []
          historyIndex.value = -1

          console.log('uploadedFloorPlans:', uploadedFloorPlans.map(p => ({ name: p.name, id: p.id })))
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

    // Seleção de planta
    const confirmSelectFloorPlan = () => {
      if (currentPlan.value?.isModified) {
        if (!confirm('Alterações não salvas na planta atual serão perdidas. Deseja continuar?')) {
          selectedFloorPlanIndex.value = uploadedFloorPlans.findIndex(p => p === currentPlan.value)
          return
        }
      }
      actionHistory.value = []
      historyIndex.value = -1
      selectFloorPlan()
    }

    const selectFloorPlan = () => {
      if (selectedFloorPlanIndex.value === -1) {
        dxfData = null
        markers.value = []
        actionHistory.value = []
        historyIndex.value = -1
        redrawCanvas()
        setStatusMessage('Nenhuma planta baixa selecionada.')
        return
      }

      const plan = uploadedFloorPlans[selectedFloorPlanIndex.value]
      if (!plan) {
        setStatusMessage('Planta baixa inválida selecionada.', true)
        return
      }

      console.log('Selecionando planta:', plan.name, 'Índice:', selectedFloorPlanIndex.value, 'ID:', plan.id || 'Nenhum')
      try {
        const parser = new DxfParser()
        dxfData = parser.parseSync(plan.content)
        markers.value = plan.markers
        actionHistory.value = []
        historyIndex.value = -1
        resetView()
        redrawCanvas()
        setStatusMessage(`Planta baixa ${plan.name}${plan.id ? ` (ID: ${plan.id})` : ''} selecionada.`)
      } catch (error) {
        console.error('Erro ao processar planta baixa:', error)
        setStatusMessage('Falha ao carregar a planta baixa selecionada.', true)
        dxfData = null
        markers.value = []
        actionHistory.value = []
        historyIndex.value = -1
        redrawCanvas()
      }
    }

    // Salvamento
    const openSaveAsModal = () => {
      if (!currentPlan.value) {
        setStatusMessage('Nenhum arquivo .dxf carregado para salvar.', true)
        return
      }
      newPlanName.value = currentPlan.value.name
      showSaveAsModal.value = true
    }

    const saveFloorPlanAs = async () => {
      if (!currentPlan.value) {
        setStatusMessage('Nenhum arquivo .dxf carregado para salvar.', true)
        showSaveAsModal.value = false
        return
      }
      if (!currentPlan.value.markers.length) {
        setStatusMessage('Adicione pelo menos um marcador antes de salvar a planta baixa.', true)
        showSaveAsModal.value = false
        return
      }
      if (!newPlanName.value.trim()) {
        setStatusMessage('O nome da planta baixa é obrigatório.', true)
        return
      }

      try {
        setStatusMessage(`Salvando nova planta baixa: ${newPlanName.value}...`)
        console.log('Enviando POST /api/floorplan:', { name: newPlanName.value, markersCount: currentPlan.value.markers.length })
        const response = await fetch(`${BACKEND_URL}/api/floorplan`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: newPlanName.value,
            dxfContent: currentPlan.value.content,
            markers: currentPlan.value.markers
          })
        })
        if (response.ok) {
          const data = await response.json()
          uploadedFloorPlans[selectedFloorPlanIndex.value].id = data.id
          uploadedFloorPlans[selectedFloorPlanIndex.value].name = newPlanName.value
          uploadedFloorPlans[selectedFloorPlanIndex.value].isModified = false
          setStatusMessage(`Planta baixa ${newPlanName.value} salva com ID: ${data.id}.`)
          console.log('Planta salva:', { id: data.id, name: newPlanName.value })
          await fetchFloorPlans()
          showSaveAsModal.value = false
          newPlanName.value = ''
        } else {
          const errorData = await response.json()
          throw new Error(errorData.error || 'Falha ao salvar a planta baixa.')
        }
      } catch (error: any) {
        console.error('Erro ao salvar planta baixa:', error)
        const message = error.message.includes('Failed to fetch')
          ? 'Não foi possível conectar ao servidor. Verifique se o backend está ativo e CORS está configurado.'
          : `Erro ao salvar planta baixa: ${error.message}`
        setStatusMessage(message, true)
      }
    }

    const updateFloorPlan = async () => {
      if (!currentPlan.value) {
        setStatusMessage('Nenhum arquivo .dxf carregado para salvar.', true)
        return
      }
      if (!currentPlan.value.markers.length) {
        setStatusMessage('Adicione pelo menos um marcador antes de salvar a planta baixa.', true)
        return
      }
      if (!currentPlan.value.id) {
        setStatusMessage('Nenhuma ID associada. Use "Salvar Como" para criar uma nova planta.', true)
        return
      }

      try {
        setStatusMessage(`Atualizando planta baixa ID: ${currentPlan.value.id}...`)
        console.log('Enviando PUT /api/floorplan/', currentPlan.value.id)
        const response = await fetch(`${BACKEND_URL}/api/floorplan/${currentPlan.value.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: currentPlan.value.name,
            dxfContent: currentPlan.value.content,
            markers: currentPlan.value.markers
          })
        })
        if (response.ok) {
          const data = await response.json()
          uploadedFloorPlans[selectedFloorPlanIndex.value].isModified = false
          setStatusMessage(`Planta baixa ${currentPlan.value.name} atualizada com sucesso.`)
          console.log('Planta atualizada:', { id: data.id, name: currentPlan.value.name })
          await fetchFloorPlans()
        } else {
          const errorData = await response.json()
          throw new Error(errorData.error || 'Falha ao atualizar a planta baixa.')
        }
      } catch (error: any) {
        console.error('Erro ao atualizar planta baixa:', error)
        const message = error.message.includes('Failed to fetch')
          ? 'Não foi possível conectar ao servidor. Verifique se o backend está ativo e CORS está configurado.'
          : `Erro ao atualizar planta baixa: ${error.message}`
        setStatusMessage(message, true)
      }
    }

    const saveFloorPlan = async () => {
      if (!currentPlan.value) {
        setStatusMessage('Nenhum arquivo .dxf carregado para salvar.', true)
        return
      }
      if (currentPlan.value.id) {
        await updateFloorPlan()
      } else {
        openSaveAsModal()
      }
    }

    // Carregamento de plantas salvas
    const fetchFloorPlans = async () => {
      try {
        setStatusMessage('Buscando plantas baixas...')
        const response = await fetch(`${BACKEND_URL}/api/floorplans`)
        if (response.ok) {
          const data = await response.json()
          floorPlans.value = data.floorPlans
          console.log('floorPlans atualizado:', floorPlans.value)
          setStatusMessage('Plantas baixas carregadas com sucesso.')
        } else {
          const errorData = await response.json()
          throw new Error(errorData.error || 'Falha ao listar plantas baixas.')
        }
      } catch (error: any) {
        console.error('Erro ao buscar plantas baixas:', error)
        const message = error.message.includes('Failed to fetch')
          ? 'Não foi possível conectar ao servidor. Verifique se o backend está ativo e CORS está configurado.'
          : `Erro ao listar plantas baixas: ${error.message}`
        setStatusMessage(message, true)
      }
    }

    const loadFloorPlanById = async (id: string) => {
      if (currentPlan.value?.isModified) {
        if (!confirm('Alterações não salvas na planta atual serão perdidas. Deseja continuar?')) {
          return
        }
      }

      try {
        setStatusMessage(`Carregando planta baixa ID: ${id}...`)
        const response = await fetch(`${BACKEND_URL}/api/floorplan/${id}`)
        if (response.ok) {
          const data = await response.json()
          const parser = new DxfParser()
          dxfData = parser.parseSync(data.dxfContent)
          const newPlan: FloorPlan = {
            id,
            name: data.name,
            content: data.dxfContent,
            markers: data.markers.map((m: any) => ({
              x: m.x,
              y: m.y,
              type: m.type,
              color: DEVICE_COLORS[m.type] || 'gray',
              name: m.name,
              ip: m.ip,
              status: m.status || 'online',
              connections: m.connections || []
            })),
            isModified: false
          }
          uploadedFloorPlans.push(newPlan)
          selectedFloorPlanIndex.value = uploadedFloorPlans.length - 1
          markers.value = newPlan.markers
          actionHistory.value = []
          historyIndex.value = -1
          resetView()
          redrawCanvas()
          showFloorPlanList.value = false
          setStatusMessage(`Planta baixa ${data.name} carregada com sucesso.`)
        } else {
          const errorData = await response.json()
          throw new Error(errorData.error || 'Falha ao carregar a planta baixa.')
        }
      } catch (error: any) {
        console.error('Erro ao carregar planta baixa:', error)
        const message = error.message.includes('Failed to fetch')
          ? 'Não foi possível conectar ao servidor. Verifique se o backend está ativo e CORS está configurado.'
          : `Erro ao carregar planta baixa: ${error.message}`
        setStatusMessage(message, true)
      }
    }

    // Exportação
    const exportCanvas = () => {
      if (!canvas.value) return
      const dataUrl = canvas.value.toDataURL('image/png')
      const link = document.createElement('a')
      link.href = dataUrl
      link.download = currentPlan.value ? `${currentPlan.value.name}.png` : 'Planta baixa.png'
      link.click()
      setStatusMessage('Planta baixa exportada como PNG.')
    }

    // Manipulação do canvas
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

    const drawArrow = (ctx: CanvasRenderingContext2D, fromX: number, fromY: number, toX: number, toY: number, style: any) => {
      const headLength = 10 / (baseScale * zoomLevel)
      const dx = toX - fromX
      const dy = toY - fromY
      const angle = Math.atan2(dy, dx)
      const offset = 8 / (baseScale * zoomLevel) // Para não sobrepor o marcador

      const adjustedToX = toX - Math.cos(angle) * offset
      const adjustedToY = toY - Math.sin(angle) * offset

      ctx.beginPath()
      ctx.moveTo(fromX, fromY)
      ctx.lineTo(adjustedToX, adjustedToY)
      ctx.strokeStyle = style.color
      ctx.lineWidth = style.lineWidth / (baseScale * zoomLevel)
      ctx.setLineDash(style.dash.map(d => d / (baseScale * zoomLevel)))
      ctx.stroke()

      ctx.beginPath()
      ctx.moveTo(adjustedToX, adjustedToY)
      ctx.lineTo(
        adjustedToX - headLength * Math.cos(angle - Math.PI / 6),
        adjustedToY - headLength * Math.sin(angle - Math.PI / 6)
      )
      ctx.lineTo(
        adjustedToX - headLength * Math.cos(angle + Math.PI / 6),
        adjustedToY - headLength * Math.sin(angle + Math.PI / 6)
      )
      ctx.closePath()
      ctx.fillStyle = style.color
      ctx.fill()
      ctx.setLineDash([])
    }

    const handleMouseDown = (event: MouseEvent) => {
      if (!canvas.value) return
      const rect = canvas.value.getBoundingClientRect()
      mouseDownX = event.clientX - rect.left
      mouseDownY = event.clientY - rect.top
      isDragging = false

      const x = (mouseDownX - panOffsetX) / (baseScale * zoomLevel)
      const y = (mouseDownY - panOffsetY) / (baseScale * zoomLevel)

      const index = getNearestMarkerIndex(x, y)
      if (index !== -1) {
        draggedMarkerIndex.value = index
        return
      }

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
      const currentTime = Date.now()

      if (draggedMarkerIndex.value !== null) {
        const x = (mouseUpX - panOffsetX) / (baseScale * zoomLevel)
        const y = (mouseUpY - panOffsetY) / (baseScale * zoomLevel)
        let newX = x
        let newY = y

        if (showGrid.value) {
          newX = Math.round(newX / effectiveGridSize.value) * effectiveGridSize.value
          newY = Math.round(newY / effectiveGridSize.value) * effectiveGridSize.value
        }

        const previousState = deepCopyMarkers(markers.value)
        const previousSettings = getCurrentSettings()
        markers.value[draggedMarkerIndex.value].x = newX
        markers.value[draggedMarkerIndex.value].y = newY
        if (selectedFloorPlanIndex.value !== -1) {
          uploadedFloorPlans[selectedFloorPlanIndex.value].markers = [...markers.value]
          addActionToHistory('move_marker', previousState, deepCopyMarkers(markers.value), previousSettings, getCurrentSettings())
          markPlanAsModified()
          setStatusMessage(`Marcador ${markers.value[draggedMarkerIndex.value].name} movido para (${newX.toFixed(2)}, ${newY.toFixed(2)}).`)
        }

        draggedMarkerIndex.value = null
        redrawCanvas()
        return
      }

      if (event.button === 0) {
        isPanning = false
        if (!isDragging && Math.hypot(mouseUpX - mouseDownX, mouseUpY - mouseDownY) < 5 && (currentTime - lastClickTime) > 300) {
          openMarkerModal(mouseUpX, mouseUpY)
        }
      }
      lastClickTime = currentTime
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

      if (draggedMarkerIndex.value !== null) {
        isDragging = true
        let newX = x
        let newY = y

        if (showGrid.value) {
          newX = Math.round(newX / effectiveGridSize.value) * effectiveGridSize.value
          newY = Math.round(newY / effectiveGridSize.value) * effectiveGridSize.value
        }

        markers.value[draggedMarkerIndex.value].x = newX
        markers.value[draggedMarkerIndex.value].y = newY
        if (selectedFloorPlanIndex.value !== -1) {
          uploadedFloorPlans[selectedFloorPlanIndex.value].markers = [...markers.value]
        }
        redrawCanvas()
      }

      if (isPanning) {
        isDragging = true
        panOffsetX = event.clientX - startPanX
        panOffsetY = event.clientY - startPanY
        redrawCanvas()
      }

      const marker = filteredMarkers.value.find(m =>
        Math.hypot(m.x - x, m.y - y) < 10 / (baseScale * zoomLevel)
      )
      hoveredMarker.value = marker || null
      if (marker) {
        tooltip.value = `${marker.type}: ${marker.name} (IP: ${marker.ip}, Status: ${marker.status}) em (${marker.x.toFixed(2)}, ${marker.y.toFixed(2)})\nConexões: ${formatConnections(marker.connections)}`
        tooltipX.value = event.clientX + 10
        tooltipY.value = event.clientY + 10
      } else {
        tooltip.value = null
      }

      redrawCanvas()
    }

    const handleDoubleClick = (event: MouseEvent) => {
      if (!canvas.value || !ctx) return
      const rect = canvas.value.getBoundingClientRect()
      const x = (event.clientX - rect.left - panOffsetX) / (baseScale * zoomLevel)
      const y = (event.clientY - rect.top - panOffsetY) / (baseScale * zoomLevel)

      const index = getNearestMarkerIndex(x, y)
      if (index !== -1) {
        editMarkerIndex.value = index
        const marker = markers.value[index]
        selectedDeviceType.value = marker.type
        newMarkerName.value = marker.name
        newMarkerIp.value = marker.ip
        newMarkerX.value = marker.x
        newMarkerY.value = marker.y
        newMarkerStatus.value = marker.status
        newMarkerConnections.value = marker.connections.map(c => ({ ...c }))
        editMode.value = true
        showMarkerModal.value = true
        setStatusMessage(`Editando marcador ${marker.name}.`)
      }
    }

    const openMarkerModal = (clientX: number, clientY: number) => {
      if (!canvas.value || !ctx) return
      const rect = canvas.value.getBoundingClientRect()
      const x = (clientX - panOffsetX) / (baseScale * zoomLevel)
      const y = (clientY - panOffsetY) / (baseScale * zoomLevel)

      newMarkerX.value = x
      newMarkerY.value = y
      if (showGrid.value) {
        newMarkerX.value = Math.round(newMarkerX.value / effectiveGridSize.value) * effectiveGridSize.value
        newMarkerY.value = Math.round(newMarkerY.value / effectiveGridSize.value) * effectiveGridSize.value
      }
      newMarkerName.value = ''
      newMarkerIp.value = ''
      newMarkerStatus.value = 'online'
      newMarkerConnections.value = []
      editMode.value = false
      editMarkerIndex.value = null
      showMarkerModal.value = true
    }

    const confirmMarker = () => {
      if (!newMarkerName.value.trim()) {
        setStatusMessage('O nome do equipamento é obrigatório.', true)
        return
      }
      if (!newMarkerIp.value.trim() || !/^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$/.test(newMarkerIp.value)) {
        setStatusMessage('É necessário um endereço IP válido (exemplo: 192.168.1.1).', true)
        return
      }
      if (newMarkerConnections.value.some(c => !c.target)) {
        setStatusMessage('Todas as conexões devem ter um dispositivo selecionado.', true)
        return
      }

      let x = newMarkerX.value
      let y = newMarkerY.value
      if (showGrid.value) {
        x = Math.round(x / effectiveGridSize.value) * effectiveGridSize.value
        y = Math.round(y / effectiveGridSize.value) * effectiveGridSize.value
      }

      const previousState = deepCopyMarkers(markers.value)
      const previousSettings = getCurrentSettings()
      const updatedMarker: Marker = {
        x,
        y,
        type: selectedDeviceType.value,
        color: DEVICE_COLORS[selectedDeviceType.value],
        name: newMarkerName.value,
        ip: newMarkerIp.value,
        status: newMarkerStatus.value,
        connections: newMarkerConnections.value.map(c => ({ ...c }))
      }

      if (selectedFloorPlanIndex.value !== -1) {
        if (editMode.value && editMarkerIndex.value !== null) {
          const oldMarker = markers.value[editMarkerIndex.value]
          oldMarker.connections.forEach(conn => {
            const connectedMarker = markers.value.find(m => m.name === conn.target)
            if (connectedMarker && connectedMarker.name !== newMarkerName.value) {
              connectedMarker.connections = connectedMarker.connections.filter(c => c.target !== oldMarker.name)
            }
          })
        }

        newMarkerConnections.value.forEach(conn => {
          const connectedMarker = markers.value.find(m => m.name === conn.target)
          if (connectedMarker) {
            const existingConn = connectedMarker.connections.find(c => c.target === newMarkerName.value)
            if (!existingConn) {
              connectedMarker.connections.push({
                target: newMarkerName.value,
                type: conn.type,
                direction: conn.direction === 'to' ? 'from' : conn.direction === 'from' ? 'to' : 'both'
              })
            }
          }
        })
      }

      if (editMode.value && editMarkerIndex.value !== null && selectedFloorPlanIndex.value !== -1) {
        markers.value[editMarkerIndex.value] = { ...updatedMarker }
        uploadedFloorPlans[selectedFloorPlanIndex.value].markers = [...markers.value]
        addActionToHistory('edit_marker', previousState, deepCopyMarkers(markers.value), previousSettings, getCurrentSettings())
        markPlanAsModified()
        setStatusMessage(`Marcador ${newMarkerName.value} atualizado em ${currentPlan.value?.name}.`)
      } else if (selectedFloorPlanIndex.value !== -1) {
        markers.value.push({ ...updatedMarker })
        uploadedFloorPlans[selectedFloorPlanIndex.value].markers = [...markers.value]
        addActionToHistory('add_marker', previousState, deepCopyMarkers(markers.value), previousSettings, getCurrentSettings())
        markPlanAsModified()
        setStatusMessage(`Marcador ${newMarkerName.value} adicionado à ${currentPlan.value?.name}.`)
      } else {
        setStatusMessage('Nenhuma planta selecionada para adicionar ou editar o marcador.', true)
      }

      showMarkerModal.value = false
      newMarkerName.value = ''
      newMarkerIp.value = ''
      newMarkerStatus.value = 'online'
      newMarkerConnections.value = []
      editMode.value = false
      editMarkerIndex.value = null
      redrawCanvas()
    }

    const cancelMarker = () => {
      showMarkerModal.value = false
      newMarkerName.value = ''
      newMarkerIp.value = ''
      newMarkerStatus.value = 'online'
      newMarkerConnections.value = []
      editMode.value = false
      editMarkerIndex.value = null
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

    const removeMarkerByIndex = (index: number) => {
      if (index < 0 || index >= markers.value.length || selectedFloorPlanIndex.value === -1) return

      const previousState = deepCopyMarkers(markers.value)
      const previousSettings = getCurrentSettings()
      const markerName = markers.value[index].name

      markers.value[index].connections.forEach(conn => {
        const connectedMarker = markers.value.find(m => m.name === conn.target)
        if (connectedMarker) {
          connectedMarker.connections = connectedMarker.connections.filter(c => c.target !== markerName)
        }
      })

      markers.value.splice(index, 1)
      uploadedFloorPlans[selectedFloorPlanIndex.value].markers = [...markers.value]
      addActionToHistory('delete_marker', previousState, deepCopyMarkers(markers.value), previousSettings, getCurrentSettings())
      markPlanAsModified()
      console.log('Marcador removido localmente:', { index, name: markerName })
      setStatusMessage(`Marcador ${markerName} removido de ${currentPlan.value?.name}.`)
      redrawCanvas()
    }

    const toggleGrid = () => {
      const previousState = deepCopyMarkers(markers.value)
      const previousSettings = getCurrentSettings()
      showGrid.value = !showGrid.value
      addActionToHistory('toggle_grid', previousState, deepCopyMarkers(markers.value), previousSettings, getCurrentSettings())
      markPlanAsModified()
      redrawCanvas()
      setStatusMessage(`Grade ${showGrid.value ? 'exibida' : 'oculta'}.`)
    }

    const toggleGridStyle = () => {
      const previousState = deepCopyMarkers(markers.value)
      const previousSettings = getCurrentSettings()
      gridStyle.value = gridStyle.value === 'dashed' ? 'solid' : 'dashed'
      addActionToHistory('toggle_grid_style', previousState, deepCopyMarkers(markers.value), previousSettings, getCurrentSettings())
      markPlanAsModified()
      redrawCanvas()
      setStatusMessage(`Estilo da grade alterado para ${gridStyle.value === 'dashed' ? 'tracejado' : 'contínuo'}.`)
    }

    const toggleConnections = () => {
      const previousState = deepCopyMarkers(markers.value)
      const previousSettings = getCurrentSettings()
      showConnections.value = !showConnections.value
      addActionToHistory('toggle_connections', previousState, deepCopyMarkers(markers.value), previousSettings, getCurrentSettings())
      markPlanAsModified()
      redrawCanvas()
      setStatusMessage(`Conexões ${showConnections.value ? 'exibidas' : 'ocultas'}.`)
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
        ctx.globalAlpha = 0.8
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
        ctx.globalAlpha = 1

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

      if (showConnections.value) {
        const drawnConnections = new Set<string>()
        filteredMarkers.value.forEach((marker, index) => {
          marker.connections.forEach(conn => {
            const targetMarker = filteredMarkers.value.find(m => m.name === conn.target)
            if (targetMarker) {
              const connectionKey = [marker.name, conn.target].sort().join('-')
              const isActive = marker.status === 'online' && targetMarker.status === 'online'
              const style = {
                ...CONNECTION_STYLES[conn.type],
                color: isActive ? CONNECTION_STYLES[conn.type].colorActive : CONNECTION_STYLES[conn.type].colorInactive
              }
              const isHighlighted = hoveredMarker.value && (hoveredMarker.value.name === marker.name || hoveredMarker.value.name === conn.target)

              if (!drawnConnections.has(connectionKey) || conn.direction !== 'both') {
                drawnConnections.add(connectionKey)
                if (conn.direction === 'to' || conn.direction === 'both') {
                  drawArrow(ctx, marker.x, marker.y, targetMarker.x, targetMarker.y, {
                    ...style,
                    lineWidth: isHighlighted ? style.lineWidth * 1.5 : style.lineWidth
                  })
                }
                if (conn.direction === 'from' || (conn.direction === 'both' && !drawnConnections.has(`${conn.target}-${marker.name}`))) {
                  drawArrow(ctx, targetMarker.x, targetMarker.y, marker.x, marker.y, {
                    ...style,
                    lineWidth: isHighlighted ? style.lineWidth * 1.5 : style.lineWidth
                  })
                }
              }
            }
          })
        })
      }

      filteredMarkers.value.forEach((marker, index) => {
        const canvasX = marker.x
        const canvasY = marker.y

        ctx.beginPath()
        ctx.arc(canvasX, canvasY, 5 / (baseScale * zoomLevel), 0, 2 * Math.PI)
        ctx.fillStyle = marker.color
        if (draggedMarkerIndex.value === index) {
          ctx.globalAlpha = 0.5
        } else if (hoveredMarker.value && (hoveredMarker.value.name === marker.name || hoveredMarker.value.connections.some(c => c.target === marker.name))) {
          ctx.globalAlpha = 0.8
        }
        ctx.fill()
        ctx.globalAlpha = 1
        ctx.strokeStyle = 'black'
        ctx.stroke()

        ctx.beginPath()
        ctx.arc(canvasX, canvasY, 8 / (baseScale * zoomLevel), 0, 2 * Math.PI)
        ctx.strokeStyle = STATUS_COLORS[marker.status]
        ctx.lineWidth = 2 / (baseScale * zoomLevel)
        if (marker.status === 'online') {
          ctx.globalAlpha = blinkState.value ? 1 : 0.2
        } else {
          ctx.globalAlpha = 1
        }
        ctx.stroke()
        ctx.globalAlpha = 1

        ctx.font = `${12 / (baseScale * zoomLevel)}px Arial`
        ctx.fillStyle = 'black'
        ctx.textAlign = 'center'
        ctx.fillText(marker.name, canvasX, canvasY - 10 / (baseScale * zoomLevel))
      })

      ctx.restore()
    }

    // Inicialização
    onMounted(async () => {
      if (canvas.value) {
        ctx = canvas.value.getContext('2d')
      }
      await fetchFloorPlans()
      setInterval(() => {
        blinkState.value = !blinkState.value
        redrawCanvas()
      }, 500)
    })

    // Watchers para alterações em configurações
    watch(baseGridSize, (newValue, oldValue) => {
      if (selectedFloorPlanIndex.value !== -1) {
        const previousState = deepCopyMarkers(markers.value)
        const previousSettings = getCurrentSettings()
        previousSettings.baseGridSize = oldValue
        addActionToHistory('change_grid_size', previousState, deepCopyMarkers(markers.value), previousSettings, getCurrentSettings())
        markPlanAsModified()
        redrawCanvas()
        setStatusMessage(`Tamanho da grade alterado para ${newValue}.`)
      }
    })

    watch(gridColor, (newValue, oldValue) => {
      if (selectedFloorPlanIndex.value !== -1) {
        const previousState = deepCopyMarkers(markers.value)
        const previousSettings = getCurrentSettings()
        previousSettings.gridColor = oldValue
        addActionToHistory('change_grid_color', previousState, deepCopyMarkers(markers.value), previousSettings, getCurrentSettings())
        markPlanAsModified()
        redrawCanvas()
        setStatusMessage(`Cor da grade alterada.`)
      }
    })

    watch(uploadedFloorPlans, (newValue) => {
      console.log('uploadedFloorPlans atualizado:', newValue.map(p => ({ name: p.name, id: p.id, markers: p.markers.length, isModified: p.isModified })))
    }, { deep: true })

    return {
      canvas,
      fileInput,
      uploadedFloorPlans,
      selectedFloorPlanIndex,
      markers,
      selectedDeviceType,
      filterDeviceType,
      filteredMarkers,
      statusMessage,
      isError,
      tooltip,
      tooltipStyle,
      showGrid,
      showConnections,
      baseGridSize,
      gridColor,
      gridStyle,
      showMarkerModal,
      newMarkerName,
      newMarkerIp,
      newMarkerX,
      newMarkerY,
      newMarkerStatus,
      newMarkerConnections,
      editMode,
      editMarkerIndex,
      showFloorPlanList,
      showSaveAsModal,
      newPlanName,
      floorPlans,
      actionHistory,
      historyIndex,
      handleFileUpload,
      confirmSelectFloorPlan,
      saveFloorPlan,
      saveFloorPlanAs,
      openSaveAsModal,
      updateFloorPlan,
      fetchFloorPlans,
      loadFloorPlanById,
      exportCanvas,
      handleMouseDown,
      handleMouseUp,
      handleMouseMove,
      handleDoubleClick,
      openMarkerModal,
      confirmMarker,
      cancelMarker,
      removeMarker,
      removeMarkerByIndex,
      toggleGrid,
      toggleGridStyle,
      toggleConnections,
      zoom,
      resetView,
      redrawCanvas,
      clearStatusMessage,
      addConnection,
      removeConnection,
      validateConnectionTarget,
      formatConnections,
      undo,
      redo
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
button:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}
button:hover:not(:disabled) {
  background-color: #0056b3;
}
li button {
  margin-left: 10px;
  background-color: #dc3545;
}
li button:hover {
  background-color: #c82333;
}
.floating-notification {
  position: fixed;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 20px;
  background-color: #d4edda;
  color: green;
  border-radius: 5px;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
  z-index: 3000;
  display: flex;
  align-items: center;
  gap: 10px;
}
.floating-notification.error {
  background-color: #f8d7da;
  color: red;
}
.floating-notification button {
  background: none;
  border: none;
  color: inherit;
  font-size: 16px;
  cursor: pointer;
  padding: 0;
  margin-left: 10px;
}
.tooltip {
  z-index: 1000;
  white-space: pre-wrap;
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
  max-width: 500px;
  width: 100%;
}
.modal-content h3 {
  margin-top: 0;
}
.modal-content label {
  display: block;
  margin: 10px 0;
}
.modal-content input, .modal-content select {
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
.connection-entry {
  display: flex;
  gap: 5px;
  margin-bottom: 5px;
}
.connection-entry select {
  width: 150px;
}
.connection-entry button {
  background-color: #dc3545;
  width: 30px;
}
.connection-entry button:hover {
  background-color: #c82333;
}
</style>