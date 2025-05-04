<template>
  <div>
    <h2>Mapa de Dispositivos</h2>
    <div>
      <input type="file" accept=".dxf" @change="handleFileUpload" ref="fileInput" />
      <select v-model="selectedDeviceType">
        <option value="Access Point">Access Point</option>
        <option value="Switch">Switch</option>
        <option value="Computer">Computer</option>
      </select>
    </div>
    <div v-if="errorMessage" class="error">
      {{ errorMessage }}
    </div>
    <canvas 
      id="floor-plan-canvas" 
      ref="canvas" 
      width="800" 
      height="600" 
      style="border: 1px solid black;" 
      @click="placeMarker"
      @contextmenu.prevent="removeMarker"
    ></canvas>
    <div>
      <h3>Dispositivos:</h3>
      <ul>
        <li v-for="(marker, index) in markers" :key="index">
          {{ marker.type }} at ({{ marker.x }}, {{ marker.y }})
          <button @click="removeMarkerByIndex(index)">Remove</button>
        </li>
      </ul>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue'
import DxfParser from 'dxf-parser'

interface Marker {
  x: number
  y: number
  type: string
  color: string
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
    const selectedDeviceType = ref('Access Point')
    const errorMessage = ref<string | null>(null)
    let ctx: CanvasRenderingContext2D | null = null
    let dxfData: any = null

    const deviceColors: { [key: string]: string } = {
      'Access Point': 'red',
      'Switch': 'blue',
      'Computer': 'green'
    }

    const handleFileUpload = (event: Event) => {
      const target = event.target as HTMLInputElement
      const file = target.files?.[0]
      if (!file) return

      const reader = new FileReader()
      reader.onload = async (e) => {
        try {
          const parser = new DxfParser()
          dxfData = await parser.parse(e.target?.result as string) // Use async parsing
          console.log('Parsed DXF Data:', dxfData)
          errorMessage.value = null
          await loadFloorPlan()
        } catch (error) {
          console.error('Error parsing .dxf file:', error)
          errorMessage.value = 'Failed to parse .dxf file. Check console for details or ensure it is a valid .dxf file.'
        }
      }
      reader.readAsText(file)
    }

    const loadFloorPlan = async () => {
      if (!canvas.value) return
      ctx = canvas.value.getContext('2d')
      if (!ctx) return

      // Clear the canvas
      ctx.fillStyle = '#f0f0f0'
      ctx.fillRect(0, 0, canvas.value.width, canvas.value.height)

      // Render .dxf data if available
      if (dxfData) {
        const bounds = getDxfBounds(dxfData)
        console.log('DXF Bounds:', bounds)
        if (bounds.maxX === -Infinity || bounds.minX === Infinity) {
          throw new Error('Invalid or empty .dxf file bounds')
        }
        const scaleX = canvas.value.width / (bounds.maxX - bounds.minX)
        const scaleY = canvas.value.height / (bounds.maxY - bounds.minY)
        const scale = Math.min(scaleX, scaleY) * 0.9

        ctx.strokeStyle = '#000'
        ctx.lineWidth = 1

        dxfData.entities.forEach((entity: any) => {
          if (entity.type === 'LINE') {
            const x1 = (entity.vertices[0].x - bounds.minX) * scale
            const y1 = (entity.vertices[0].y - bounds.minY) * scale
            const x2 = (entity.vertices[1].x - bounds.minX) * scale
            const y2 = (entity.vertices[1].y - bounds.minY) * scale
            ctx.beginPath()
            ctx.moveTo(x1, canvas.value.height - y1) // Invert Y-axis for correct rendering
            ctx.lineTo(x2, canvas.value.height - y2)
            ctx.stroke()
          } else if (entity.type === 'POLYLINE' || entity.type === 'LWPOLYLINE') {
            ctx.beginPath()
            entity.vertices.forEach((vertex: any, index: number) => {
              const x = (vertex.x - bounds.minX) * scale
              const y = (vertex.y - bounds.minY) * scale
              if (index === 0) {
                ctx.moveTo(x, canvas.value.height - y)
              } else {
                ctx.lineTo(x, canvas.value.height - y)
              }
            })
            if (entity.shape) ctx.closePath() // Close the path if it's a closed polyline
            ctx.stroke()
          }
        })
      } else {
        // Fallback to placeholder if no .dxf loaded
        ctx.strokeStyle = '#000'
        ctx.lineWidth = 2
        ctx.strokeRect(50, 50, 700, 500)
        ctx.strokeRect(200, 100, 150, 100)
        ctx.strokeRect(400, 100, 150, 100)
      }

      // Fetch existing markers from backend
      try {
        errorMessage.value = null
        const response = await fetch('http://localhost:5000/api/markers')
        if (response.ok) {
          const data = await response.json()
          markers.value = data.map((m: any) => ({
            x: m.x,
            y: m.y,
            type: m.type,
            color: deviceColors[m.type]
          }))
          redrawMarkers()
        } else {
          errorMessage.value = 'Failed to load markers from server'
        }
      } catch (error) {
        console.error('Error fetching markers:', error)
        errorMessage.value = 'Unable to connect to the server. Please ensure the backend is running on http://localhost:5000'
      }
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
        }
      })
      return { minX, minY, maxX, maxY }
    }

    const placeMarker = async (event: MouseEvent) => {
      if (!canvas.value || !ctx) return

      const rect = canvas.value.getBoundingClientRect()
      const x = event.clientX - rect.left
      const y = canvas.value.height - (event.clientY - rect.top) // Invert Y for consistency with DXF

      const newMarker: Marker = {
        x,
        y,
        type: selectedDeviceType.value,
        color: deviceColors[selectedDeviceType.value]
      }
      markers.value.push(newMarker)

      try {
        errorMessage.value = null
        const response = await fetch('http://localhost:5000/api/markers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ x, y, type: selectedDeviceType.value })
        })
        if (!response.ok) throw new Error('Failed to save marker')
        const data = await response.json()
        newMarker.x = data.x
        newMarker.y = data.y
      } catch (error) {
        console.error('Error saving marker:', error)
        errorMessage.value = 'Unable to save marker. Please ensure the backend is running on http://localhost:5000'
      }

      ctx.beginPath()
      ctx.arc(x, canvas.value.height - y, 5, 0, 2 * Math.PI)
      ctx.fillStyle = newMarker.color
      ctx.fill()
      ctx.strokeStyle = 'black'
      ctx.stroke()
    }

    const removeMarker = (event: MouseEvent) => {
      if (!canvas.value || !ctx) return

      const rect = canvas.value.getBoundingClientRect()
      const x = event.clientX - rect.left
      const y = canvas.value.height - (event.clientY - rect.top)

      const index = markers.value.findIndex(m =>
        Math.hypot(m.x - x, m.y - (canvas.value.height - y)) < 10
      )
      if (index !== -1) {
        removeMarkerByIndex(index)
      }
    }

    const removeMarkerByIndex = async (index: number) => {
      if (index < 0 || index >= markers.value.length) return

      const marker = markers.value[index]
      try {
        errorMessage.value = null
        const response = await fetch(`http://localhost:5000/api/markers/${index}`, {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' }
        })
        if (!response.ok) throw new Error('Failed to delete marker')
        markers.value.splice(index, 1)
        redrawMarkers()
      } catch (error) {
        console.error('Error deleting marker:', error)
        errorMessage.value = 'Unable to delete marker. Please ensure the backend is running on http://localhost:5000'
      }
    }

    const redrawMarkers = () => {
      if (!ctx) return
      ctx.clearRect(0, 0, canvas.value!.width, canvas.value!.height)
      if (dxfData) {
        const bounds = getDxfBounds(dxfData)
        const scaleX = canvas.value!.width / (bounds.maxX - bounds.minX)
        const scaleY = canvas.value!.height / (bounds.maxY - bounds.minY)
        const scale = Math.min(scaleX, scaleY) * 0.9

        ctx.fillStyle = '#f0f0f0'
        ctx.fillRect(0, 0, canvas.value!.width, canvas.value!.height)
        ctx.strokeStyle = '#000'
        ctx.lineWidth = 1

        dxfData.entities.forEach((entity: any) => {
          if (entity.type === 'LINE') {
            const x1 = (entity.vertices[0].x - bounds.minX) * scale
            const y1 = (entity.vertices[0].y - bounds.minY) * scale
            const x2 = (entity.vertices[1].x - bounds.minX) * scale
            const y2 = (entity.vertices[1].y - bounds.minY) * scale
            ctx.beginPath()
            ctx.moveTo(x1, canvas.value!.height - y1)
            ctx.lineTo(x2, canvas.value!.height - y2)
            ctx.stroke()
          } else if (entity.type === 'POLYLINE' || entity.type === 'LWPOLYLINE') {
            ctx.beginPath()
            entity.vertices.forEach((vertex: any, index: number) => {
              const x = (vertex.x - bounds.minX) * scale
              const y = (vertex.y - bounds.minY) * scale
              if (index === 0) {
                ctx.moveTo(x, canvas.value!.height - y)
              } else {
                ctx.lineTo(x, canvas.value!.height - y)
              }
            })
            if (entity.shape) ctx.closePath()
            ctx.stroke()
          }
        })
      } else {
        ctx.fillStyle = '#f0f0f0'
        ctx.fillRect(0, 0, canvas.value!.width, canvas.value!.height)
        ctx.strokeStyle = '#000'
        ctx.lineWidth = 2
        ctx.strokeRect(50, 50, 700, 500)
        ctx.strokeRect(200, 100, 150, 100)
        ctx.strokeRect(400, 100, 150, 100)
      }
      markers.value.forEach(marker => {
        ctx!.beginPath()
        ctx!.arc(marker.x, canvas.value!.height - marker.y, 5, 0, 2 * Math.PI)
        ctx!.fillStyle = marker.color
        ctx!.fill()
        ctx!.strokeStyle = 'black'
        ctx!.stroke()
      })
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
      handleFileUpload,
      loadFloorPlan,
      placeMarker,
      removeMarker,
      removeMarkerByIndex
    }
  }
})
</script>

<style scoped>
#floor-plan-canvas {
  background-color: #f0f0f0;
  margin-top: 10px;
}
input[type="file"] {
  margin: 10px 5px;
}
select {
  margin: 10px 5px;
  padding: 5px;
  border-radius: 3px;
}
li button {
  margin-left: 10px;
  background-color: #dc3545;
  padding: 5px 10px;
  color: white;
  border: none;
  border-radius: 3px;
  cursor: pointer;
}
li button:hover {
  background-color: #c82333;
}
.error {
  color: red;
  margin: 10px 0;
}
</style>