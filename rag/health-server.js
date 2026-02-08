const express = require('express');
const cors = require('cors');
require('dotenv').config({ path: '.env.gemini' });

const app = express();
const PORT = process.env.GEMINI_RAG_PORT || 3003;

// Middleware
app.use(cors());
app.use(express.json());

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.json({
    status: 'ok',
    timestamp: new Date().toISOString(),
    services: {
      gemini_rag: 'ready'
    }
  });
});

// Start the server
app.listen(PORT, () => {
  console.log(`🌟 Health Check Server running on port ${PORT}`);
  console.log(`📊 Health: http://localhost:${PORT}/api/health`);
});