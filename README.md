# Sistema de Mapeamento de Dispositivos

Sistema web para mapear dispositivos (Access Points, Switches, Computadores) em uma planta baixa empresarial no formato DXF, utilizando Vue.js (Vite) no frontend e Node.js (Express) no backend.

## Pré-requisitos
- Node.js (v16 ou superior)
- npm ou yarn

## Configuração do Frontend
1. Navegue até a pasta do frontend:
   ```bash
   cd frontend
   ```
2. Instale as dependências:
   ```bash
   npm install
   ```
3. Inicie o servidor de desenvolvimento:
   ```bash
   npm run dev
   ```
4. Acesse `http://localhost:5173` no navegador.

## Configuração do Backend
1. Navegue até a pasta do backend:
   ```bash
   cd backend
   ```
2. Instale as dependências:
   ```bash
   npm install
   ```
3. Inicie o servidor:
   ```bash
   node server.js
   ```
4. A API estará disponível em `http://localhost:3000`.

## Estrutura do Projeto
- `frontend/`: Contém o projeto Vue.js com Vite.
  - `src/main.js`: Ponto de entrada do frontend.
  - `src/App.vue`: Componente principal com placeholder para visualização de DXF.
- `backend/`: Contém o projeto Node.js com Express.
  - `server.js`: Configuração inicial da API.

## Próximos Passos
- Implementar upload e parsing de arquivos DXF no backend (`ezdxf` ou similar).
- Integrar biblioteca de visualização de DXF no frontend (`dxf-parser` ou `three.js`).
- Desenvolver funcionalidade de marcação de dispositivos na planta baixa.

## Princípios SOLID
- **SRP**: Componente `App.vue` foca apenas na interface inicial.
- **OCP**: Backend estruturado para extensões (ex.: novas rotas para dispositivos).
- **DIP**: Futuros serviços (ex.: parsing de DXF) serão injetados como dependências.