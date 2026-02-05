const { RAGLongevityService } = require('./src/ragService');
require('dotenv').config();

class RAGLongevityAPI {
  constructor() {
    this.ragService = new RAGLongevityService();
    this.isInitialized = false;
  }

  async initialize() {
    try {
      console.log('🚀 Initializing RAG Longevity API...');
      this.isInitialized = await this.ragService.initializeRAG();
      
      if (this.isInitialized) {
        console.log('✅ RAG API Ready for Use!');
        return true;
      } else {
        console.log('❌ RAG API Initialization Failed');
        return false;
      }
    } catch (error) {
      console.error('RAG API Error:', error);
      return false;
    }
  }

  async handleLongevityQuery(req, res) {
    try {
      const { query, userProfile } = req.body;
      
      if (!query) {
        return res.status(400).json({ error: 'Query is required' });
      }

      if (!this.isInitialized) {
        return res.status(503).json({ error: 'RAG system not initialized' });
      }

      console.log(`🤖 Processing longevity query: "${query}"`);
      
      const result = await this.ragService.generateRAGResponse(query, userProfile);
      
      res.json({
        success: true,
        query: result.query,
        response: result.response,
        citations: result.citations,
        sources: result.sources.map(s => ({
          id: s.id,
          title: s.metadata.title || 'Unknown',
          type: s.metadata.type,
          relevance: s.relevance,
          metadata: s.metadata
        })),
        confidence: result.confidence,
        timestamp: new Date().toISOString()
      });
      
    } catch (error) {
      console.error('Query processing failed:', error);
      res.status(500).json({ 
        error: 'Failed to process query',
        message: error.message 
      });
    }
  }

  async handleSearch(req, res) {
    try {
      const { query, topK = 5, filters = {} } = req.query;
      
      if (!query) {
        return res.status(400).json({ error: 'Query parameter is required' });
      }

      if (!this.isInitialized) {
        return res.status(503).json({ error: 'RAG system not initialized' });
      }

      const results = await this.ragService.searchLongevity(query, parseInt(topK), filters);
      
      res.json({
        success: true,
        query: query,
        results: results,
        count: results.length,
        timestamp: new Date().toISOString()
      });
      
    } catch (error) {
      console.error('Search failed:', error);
      res.status(500).json({ 
        error: 'Search failed',
        message: error.message 
      });
    }
  }

  async handleUserProfile(req, res) {
    try {
      const { userId, profile } = req.body;
      
      // Store user profile for personalization
      // This would integrate with your user database
      
      res.json({
        success: true,
        message: 'User profile updated for RAG personalization',
        userId: userId,
        profile: profile
      });
      
    } catch (error) {
      console.error('Profile update failed:', error);
      res.status(500).json({ 
        error: 'Profile update failed',
        message: error.message 
      });
    }
  }

  async handleHealthCheck(req, res) {
    try {
      const status = {
        rag_initialized: this.isInitialized,
        timestamp: new Date().toISOString(),
        services: {
          openai: !!process.env.OPENAI_API_KEY,
          pinecone: !!process.env.PINECONE_API_KEY,
          database: 'connected' // Would check actual DB connection
        }
      };
      
      res.json(status);
      
    } catch (error) {
      res.status(500).json({ error: 'Health check failed' });
    }
  }

  async runTests() {
    console.log('🧪 Running RAG System Tests...');
    
    if (!this.isInitialized) {
      console.log('❌ Cannot run tests - RAG not initialized');
      return;
    }
    
    await this.ragService.testRAGSystem();
  }
}

// Express API Integration
const express = require('express');
const cors = require('cors');

function createRAGAPI() {
  const app = express();
  const ragAPI = new RAGLongevityAPI();
  
  // Middleware
  app.use(cors());
  app.use(express.json());
  
  // Initialize RAG system
  ragAPI.initialize().then(success => {
    if (success) {
      console.log('🎉 RAG Longevity API is ready!');
    }
  });
  
  // API Routes
  app.post('/api/rag/query', (req, res) => ragAPI.handleLongevityQuery(req, res));
  app.get('/api/rag/search', (req, res) => ragAPI.handleSearch(req, res));
  app.post('/api/rag/profile', (req, res) => ragAPI.handleUserProfile(req, res));
  app.get('/api/rag/health', (req, res) => ragAPI.handleHealthCheck(req, res));
  app.post('/api/rag/test', async (req, res) => {
    await ragAPI.runTests();
    res.json({ message: 'Tests completed' });
  });
  
  return app;
}

// For standalone testing
if (require.main === module) {
  const app = createRAGAPI();
  const PORT = process.env.RAG_PORT || 3002;
  
  app.listen(PORT, () => {
    console.log(`🧠 RAG Longevity API running on port ${PORT}`);
    console.log(`📊 Health Check: http://localhost:${PORT}/api/rag/health`);
    console.log(`🔍 Search API: http://localhost:${PORT}/api/rag/search?query=test`);
    console.log(`🤖 Query API: POST http://localhost:${PORT}/api/rag/query`);
  });
}

module.exports = { RAGLongevityAPI, createRAGAPI };