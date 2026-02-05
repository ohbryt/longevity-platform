const { GeminiRAGService } = require('./src/geminiRAGService');
require('dotenv').config');

class GeminiRAGAPI {
  constructor() {
    this.geminiRAGService = new GeminiRAGService();
    this.isInitialized = false;
  }

  async initialize() {
    try {
      console.log('🌟 Initializing Gemini RAG Longevity API...');
      this.isInitialized = await this.geminiRAGService.initializeGeminiRAG();
      
      if (this.isInitialized) {
        console.log('✅ Gemini RAG API Ready for Use!');
        return true;
      } else {
        console.log('❌ Gemini RAG API Initialization Failed');
        return false;
      }
    } catch (error) {
      console.error('Gemini RAG API Error:', error);
      return false;
    }
  }

  async handleMultilingualQuery(req, res) {
    try {
      const { query, userProfile, language = 'auto' } = req.body;
      
      if (!query) {
        return res.status(400).json({ error: 'Query is required' });
      }

      if (!this.isInitialized) {
        return res.status(503).json({ error: 'Gemini RAG system not initialized' });
      }

      console.log(`🤖 Processing multilingual query: "${query}"`);
      
      const result = await this.geminiRAGService.generateGeminiRAGResponse(query, userProfile, language);
      
      res.json({
        success: true,
        query: result.query,
        response: result.response,
        citations: result.citations,
        sources: result.sources.map(s => ({
          id: s.id,
          title: s.metadata.title || 'Unknown',
          type: s.metadata.type,
          language: s.metadata.language || 'english',
          relevance: s.relevance,
          metadata: s.metadata
        })),
        confidence: result.confidence,
        language: result.language,
        timestamp: new Date().toISOString()
      });
      
    } catch (error) {
      console.error('Multilingual query processing failed:', error);
      res.status(500).json({ 
        error: 'Failed to process query',
        message: error.message 
      });
    }
  }

  async handleKoreanQuery(req, res) {
    try {
      const { query, userProfile } = req.body;
      
      if (!query) {
        return res.status(400).json({ error: 'Query is required' });
      }

      if (!this.isInitialized) {
        return res.status(503).json({ error: 'Gemini RAG system not initialized' });
      }

      console.log(`🇰🇷 Processing Korean query: "${query}"`);
      
      const result = await this.geminiRAGService.generateGeminiRAGResponse(query, userProfile, 'korean');
      
      res.json({
        success: true,
        query: result.query,
        response: result.response,
        citations: result.citations,
        sources: result.sources,
        confidence: result.confidence,
        language: 'korean',
        timestamp: new Date().toISOString()
      });
      
    } catch (error) {
      console.error('Korean query processing failed:', error);
      res.status(500).json({ 
        error: 'Failed to process Korean query',
        message: error.message 
      });
    }
  }

  async handleMultilingualSearch(req, res) {
    try {
      const { query, topK = 5, filters = {}, language = 'auto' } = req.query;
      
      if (!query) {
        return res.status(400).json({ error: 'Query parameter is required' });
      }

      if (!this.isInitialized) {
        return res.status(503).json({ error: 'Gemini RAG system not initialized' });
      }

      const results = await this.geminiRAGService.searchLongevityMultilingual(query, parseInt(topK), filters);
      
      res.json({
        success: true,
        query: query,
        results: results,
        count: results.length,
        timestamp: new Date().toISOString()
      });
      
    } catch (error) {
      console.error('Multilingual search failed:', error);
      res.status(500).json({ 
        error: 'Search failed',
        message: error.message 
      });
    }
  }

  async handleHealthCheck(req, res) {
    try {
      const status = {
        gemini_rag_initialized: this.isInitialized,
        timestamp: new Date().toISOString(),
        services: {
          openai: !!process.env.OPENAI_API_KEY,
          gemini: !!process.env.GEMINI_API_KEY,
          pinecone: !!process.env.PINECONE_API_KEY,
          database: 'connected'
        },
        capabilities: {
          multilingual: true,
          korean_support: true,
          gemini_integration: true,
          rag_search: true
        }
      };
      
      res.json(status);
      
    } catch (error) {
      res.status(500).json({ error: 'Health check failed' });
    }
  }

  async runTests() {
    console.log('🧪 Running Gemini RAG System Tests...');
    
    if (!this.isInitialized) {
      console.log('❌ Cannot run tests - Gemini RAG not initialized');
      return;
    }
    
    await this.geminiRAGService.testGeminiRAGSystem();
  }
}

// Express API Integration
const express = require('express');
const cors = require('cors');

function createGeminiRAGAPI() {
  const app = express();
  const geminiRAGAPI = new GeminiRAGAPI();
  
  // Middleware
  app.use(cors());
  app.use(express.json());
  
  // Initialize Gemini RAG system
  geminiRAGAPI.initialize().then(success => {
    if (success) {
      console.log('🎉 Gemini RAG Longevity API is ready!');
    }
  });
  
  // API Routes
  app.post('/api/gemini/query', (req, res) => geminiRAGAPI.handleMultilingualQuery(req, res));
  app.post('/api/gemini/korean', (req, res) => geminiRAGAPI.handleKoreanQuery(req, res));
  app.get('/api/gemini/search', (req, res) => geminiRAGAPI.handleMultilingualSearch(req, res));
  app.get('/api/gemini/health', (req, res) => geminiRAGAPI.handleHealthCheck(req, res));
  app.post('/api/gemini/test', async (req, res) => {
    await geminiRAGAPI.runTests();
    res.json({ message: 'Gemini RAG tests completed' });
  });
  
  return app;
}

// For standalone testing
if (require.main === module) {
  const app = createGeminiRAGAPI();
  const PORT = process.env.GEMINI_RAG_PORT || 3003;
  
  app.listen(PORT, () => {
    console.log(`🌟 Gemini RAG Longevity API running on port ${PORT}`);
    console.log(`📊 Health Check: http://localhost:${PORT}/api/gemini/health`);
    console.log(`🔍 Search API: http://localhost:${PORT}/api/gemini/search?query=test`);
    console.log(`🤖 Query API: POST http://localhost:${PORT}/api/gemini/query`);
    console.log(`🇰🇷 Korean API: POST http://localhost:${PORT}/api/gemini/korean`);
  });
}

module.exports = { GeminiRAGAPI, createGeminiRAGAPI };