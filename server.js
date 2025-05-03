// server.js
import express from 'express';
import cors from 'cors';

const app = express();
const port = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// Rota inicial
app.get('/api', (req, res) => {
  res.json({ message: 'API para mapeamento de dispositivos' });
});

// Placeholder para upload de DXF
app.post('/api/upload-dxf', (req, res) => {
  res.json({ message: 'Upload de DXF será implementado' });
});

app.listen(port, () => {
  console.log(`Servidor rodando em http://localhost:${port}`);
});