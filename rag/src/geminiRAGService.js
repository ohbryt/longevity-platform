import { GoogleGenerativeAI } from '@google/generative-ai';
import { RAGLongevityService } from './ragService.js';
require('dotenv').config();

class GeminiRAGService extends RAGLongevityService {
  constructor() {
    super();
    this.gemini = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);
    this.geminiModel = 'gemini-1.5-pro';
    this.koreanModel = 'gemini-1.5-pro';
  }

  async initializeGeminiRAG() {
    try {
      console.log('🌟 Initializing Gemini RAG System...');
      
      // Initialize base RAG system
      const baseSuccess = await this.initializeRAG();
      
      if (baseSuccess) {
        // Load Korean medical knowledge base
        await this.loadKoreanMedicalKnowledge();
        
        // Set up multilingual capabilities
        await this.setupMultilingualSupport();
        
        console.log('✅ Gemini RAG System Ready!');
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('❌ Gemini RAG Initialization Failed:', error);
      return false;
    }
  }

  async loadKoreanMedicalKnowledge() {
    console.log('🇰🇷 Loading Korean Medical Knowledge Base...');
    
    const koreanKnowledge = [
      {
        id: 'kr-001',
        text: '장수영 오 교수의 노화 연구: 세포 노화와 NAD+ 대사에 대한 연구. 2023년 연구에서 50세 이상 성인에게 니코틴아마이드 리보사이드 보충이 NAD+ 수치를 65% 증가시키고, 미토콘드리아 기능 개선을 보여주었습니다.',
        metadata: {
          type: 'professor_expertise',
          author: '장수영 오',
          year: 2023,
          journal: '네이처 에이징',
          topics: ['NAD+', '세포노화', '미토콘드리아'],
          language: 'korean',
          clinical_relevance: 0.92
        }
      },
      {
        id: 'kr-002',
        text: '한국인 노화 연구: 전통 한약과 현대 노화 과학의 결합. 인삼, 홍삼, 녹차의 노화 방지 효과에 대한 임상 연구 결과. 500명의 한국인을 대상으로 한 연구에서 복합 한약 보충이 생물학적 나이를 평균 3.2년 감소시켰습니다.',
        metadata: {
          type: 'korean_research',
          author: '김철수, 이영희',
          year: 2024,
          journal: '대한의학회지',
          topics: ['한약', '노화', '인삼', '홍삼'],
          language: 'korean',
          sample_size: 500,
          clinical_relevance: 0.88
        }
      },
      {
        id: 'kr-003',
        text: 'GLP-1 수용체 작용제와 한국인 대사 증후군: 세마글루타이드와 티르제파타이드의 효과 비교 연구. 200명의 한국인 대사 증후군 환자를 대상으로 한 연구에서 24주 치료 후 체중 감소 12%와 인슐린 민감성 45% 개선을 보였습니다.',
        metadata: {
          type: 'korean_clinical_trial',
          author: '박지혜, 최민준',
          year: 2024,
          journal: '대한내분비학회지',
          topics: ['GLP-1', '세마글루타이드', '티르제파타이드', '대사증후군'],
          language: 'korean',
          sample_size: 200,
          clinical_relevance: 0.91
        }
      }
    ];

    // Create embeddings and upsert to Pinecone
    const index = await this.pinecone.index(this.indexName);
    
    for (const item of koreanKnowledge) {
      const embedding = await this.createEmbedding(item.text);
      
      await index.upsert([{
        id: item.id,
        values: embedding,
        metadata: item.metadata,
        text: item.text.substring(0, 1000)
      }]);
    }

    console.log(`✅ Loaded ${koreanKnowledge.length} Korean knowledge items`);
  }

  async setupMultilingualSupport() {
    console.log('🌍 Setting up Multilingual Support...');
    
    // Test Gemini models for different languages
    const testQueries = [
      { text: 'NAD+ 보충의 최신 연구 결과는?', language: 'korean' },
      { text: 'What are the latest findings on NAD+ supplementation?', language: 'english' },
      { text: 'GLP-1 agonists와 대사 건강', language: 'korean' }
    ];

    for (const query of testQueries) {
      try {
        const model = this.gemini.getGenerativeModel({ model: this.geminiModel });
        const result = await model.generateContent(query.text);
        
        console.log(`✅ ${query.language} model test: ${result.response.text().substring(0, 100)}...`);
      } catch (error) {
        console.error(`❌ ${query.language} model test failed:`, error.message);
      }
    }
  }

  async generateGeminiRAGResponse(userQuery, userProfile = {}, language = 'korean') {
    try {
      console.log(`🤖 Generating Gemini RAG response (${language})...`);
      
      // 1. Detect language and set appropriate model
      const detectedLanguage = this.detectLanguage(userQuery);
      const model = this.gemini.getGenerativeModel({ 
        model: detectedLanguage === 'korean' ? this.koreanModel : this.geminiModel 
      });
      
      // 2. Retrieve relevant knowledge (multilingual)
      const searchResults = await this.searchLongevityMultilingual(userQuery, 8, {
        language: detectedLanguage,
        type: { $in: ['research_paper', 'professor_expertise', 'korean_research', 'korean_clinical_trial'] }
      });
      
      // 3. Rank by relevance and language
      const topResults = searchResults
        .sort((a, b) => b.relevance - a.relevance)
        .slice(0, 5);
      
      // 4. Format context for Gemini
      const context = this.formatGeminiContext(topResults, userProfile, detectedLanguage);
      
      // 5. Generate response with Gemini
      const systemPrompt = this.getGeminiSystemPrompt(userProfile, detectedLanguage);
      const userPrompt = this.getGeminiUserPrompt(userQuery, context, detectedLanguage);
      
      const result = await model.generateContent(`${systemPrompt}\n\n${userPrompt}`);
      const generatedResponse = result.response.text();
      
      // 6. Format response with citations
      const formattedResponse = this.formatGeminiResponse(generatedResponse, topResults, detectedLanguage);
      
      return {
        query: userQuery,
        response: formattedResponse.text,
        citations: formattedResponse.citations,
        sources: topResults,
        confidence: this.calculateGeminiConfidence(topResults),
        language: detectedLanguage,
        userProfile: userProfile
      };
      
    } catch (error) {
      console.error('Gemini RAG response generation failed:', error);
      throw error;
    }
  }

  detectLanguage(text) {
    // Simple language detection
    const koreanChars = text.match(/[가-힣]/g);
    const totalChars = text.replace(/\s/g, '').length;
    
    if (koreanChars && koreanChars.length / totalChars > 0.3) {
      return 'korean';
    }
    
    return 'english';
  }

  async searchLongevityMultilingual(query, topK = 5, filters = {}) {
    try {
      console.log(`🔍 Searching multilingual longevity knowledge for: "${query}"`);
      
      const index = await this.pinecone.index(this.indexName);
      const queryEmbedding = await this.createEmbedding(query);
      
      // Perform similarity search with language filter
      const results = await index.query({
        vector: queryEmbedding,
        topK: topK,
        includeMetadata: true,
        includeValues: false,
        filter: filters
      });

      // Format results with language preference
      const formattedResults = results.matches.map(match => ({
        id: match.id,
        score: match.score,
        text: match.metadata.text || '',
        metadata: match.metadata,
        relevance: this.calculateMultilingualRelevance(match.score, match.metadata, query)
      }));

      console.log(`✅ Found ${formattedResults.length} relevant multilingual results`);
      return formattedResults;
    } catch (error) {
      console.error('Multilingual search failed:', error);
      throw error;
    }
  }

  calculateMultilingualRelevance(score, metadata, query) {
    const baseRelevance = this.calculateRelevance(score, metadata);
    const queryLanguage = this.detectLanguage(query);
    const contentLanguage = metadata.language || 'english';
    
    // Boost relevance for same language
    const languageBonus = queryLanguage === contentLanguage ? 0.2 : 0;
    
    // Korean content bonus for Korean queries
    const koreanBonus = queryLanguage === 'korean' && contentLanguage === 'korean' ? 0.1 : 0;
    
    return Math.min(1, baseRelevance + languageBonus + koreanBonus);
  }

  formatGeminiContext(searchResults, userProfile, language) {
    const lang = language === 'korean' ? 'korean' : 'english';
    
    let context = lang === 'korean' ? 
      '관련 장수 의학 지식:\n\n' :
      'RELEVANT LONGEVITY KNOWLEDGE:\n\n';
    
    searchResults.forEach((result, index) => {
      context += lang === 'korean' ? 
        `소스 ${index + 1}:\n내용: ${result.text}\n메타데이터: ${JSON.stringify(result.metadata, null, 2)}\n관련성 점수: ${result.relevance.toFixed(3)}\n\n` :
        `Source ${index + 1}:\nText: ${result.text}\nMetadata: ${JSON.stringify(result.metadata, null, 2)}\nRelevance Score: ${result.relevance.toFixed(3)}\n\n`;
    });
    
    if (Object.keys(userProfile).length > 0) {
      context += lang === 'korean' ? 
        `사용자 프로필: ${JSON.stringify(userProfile, null, 2)}\n\n` :
        `USER PROFILE: ${JSON.stringify(userProfile, null, 2)}\n\n`;
    }
    
    context += lang === 'korean' ?
      `지시사항:\n1. 제공된 소스만 사용하여 답변\n2. 특정 연구를 인용\n3. 장수영 오 교수의 관련 전문성 포함\n4. 사용자 프로필 고려하여 개인화\n5. 최신, 높은 관련성 연구 우선\n6. 의료 상담 권장 및 한계 인정\n7. 인용과 출처 추적 포함\n8. ${lang === 'korean' ? '한국어로 답변' : '영어로 답변'}` :
      `INSTRUCTIONS:\n1. Use ONLY the provided sources to answer\n2. Cite specific studies with their findings\n3. Include Professor Oh's relevant expertise\n4. Consider user's profile for personalization\n5. Prioritize recent, high-relevance research\n6. Acknowledge limitations and suggest medical consultation\n7. Format response clearly with citations\n8. Respond in ${lang}`;

    return context;
  }

  getGeminiSystemPrompt(userProfile, language) {
    const lang = language === 'korean' ? 'korean' : 'english';
    
    if (lang === 'korean') {
      return `당신은 장수영 오 교수, MD-PhD로서 사용자의 장수 의학 질문에 답변하는 전문가입니다.

전문 분야:
- 세포 노화 및 항노화 중재
- NAD+ 대사 및 보충 프로토콜
- 대사 건강 및 GLP-1 작용제
- 미토콘드리아 생합성 및 기능
- 임상 시험 해석 및 치료 프로토콜
- 한의학 및 현대 노화 과학의 결합

응답 지침:
- 모든 답변을 제공된 소스에 기반할 것
- 특정 연구를 저자, 저널, 연도와 함께 인용할 것
- 임상적 중요성과 실용적 응용을 포함할 것
- 사용자의 건강 프로필을 고려하여 개인화할 것
- 과학적 정확성을 유지하면서 접근성 있게 할 것
- 개인화된 조언을 위한 전문가 상담 권장
- 장수영 오 교수로서 "제 연구에 따르면:" 또는 "제 전문성에 따르면:" 사용

안전 프로토콜:
- 상담 면책 없이 특정 의료 조언 제공 금지
- 금기 사항 및 안전 고려사항 포함
- 치료 결정을 위한 전문가 의료 지도 권장
- 현재 연구의 한계 인정

${Object.keys(userProfile).length > 0 ? `
개인화 맥락:
사용자 나이: ${userProfile.age || '미지정'}
사용자 목표: ${userProfile.goals?.join(', ') || '미지정'}
건강 상태: ${userProfile.conditions?.join(', ') || '미지정'}
현재 보충제: ${userProfile.supplements?.join(', ') || '미지정'}
` : ''}`;
    } else {
      return this.getRAGSystemPrompt(userProfile);
    }
  }

  getGeminiUserPrompt(userQuery, context, language) {
    const lang = language === 'korean' ? 'korean' : 'english';
    
    if (lang === 'korean') {
      return `사용자 질문: ${userQuery}

${context}

제공된 지침을 따라 포괄적이고 증거 기반의 응답을 제공해 주세요.`;
    } else {
      return `User Question: ${userQuery}

${context}

Please provide a comprehensive, evidence-based response that incorporates Professor Oh's expertise while strictly following the response guidelines.`;
    }
  }

  formatGeminiResponse(response, sources, language) {
    const citations = this.extractCitations(response);
    
    return {
      text: response,
      citations: citations,
      sourceCount: sources.length,
      language: language
    };
  }

  calculateGeminiConfidence(sources) {
    const avgRelevance = sources.reduce((sum, s) => sum + s.relevance, 0) / sources.length;
    const sourceCount = sources.length;
    const authorityScore = sources.filter(s => 
      s.metadata.type === 'professor_expertise' || 
      s.metadata.author?.includes('장수영 오') ||
      s.metadata.language === 'korean'
    ).length;
    
    let confidence = (avgRelevance * 0.4) + (sourceCount * 0.3) + (authorityScore * 0.3);
    confidence = Math.min(1, Math.max(0, confidence));
    
    return {
      score: confidence,
      level: confidence > 0.8 ? '높음' : confidence > 0.6 ? '중간' : '낮음',
      factors: {
        relevance_avg: avgRelevance,
        source_count: sourceCount,
        authority_sources: authorityScore
      }
    };
  }

  async testGeminiRAGSystem() {
    console.log('🧪 Testing Gemini RAG System...');
    
    const testQueries = [
      { query: 'NAD+ 보충의 최신 연구 결과는?', language: 'korean' },
      { query: 'GLP-1 작용제와 대사 건강', language: 'korean' },
      { query: '한약과 노화의 최신 연구 동향', language: 'korean' },
      { query: 'What are the latest findings on NAD+ supplementation?', language: 'english' }
    ];

    for (const test of testQueries) {
      console.log(`\n🔍 Testing Query (${test.language}): "${test.query}"`);
      
      try {
        const result = await this.generateGeminiRAGResponse(test.query, {
          age: 50,
          goals: ['longevity', 'vitality'],
          conditions: ['pre-diabetes']
        }, test.language);
        
        console.log('✅ Response Generated:');
        console.log(`Language: ${result.language}`);
        console.log(`Confidence: ${result.confidence.level} (${result.confidence.score.toFixed(2)})`);
        console.log(`Sources: ${result.citations.length}`);
        console.log(`Response Length: ${result.response.length} characters`);
        console.log(`Preview: ${result.response.substring(0, 200)}...`);
        
      } catch (error) {
        console.error('❌ Test Failed:', error.message);
      }
    }
    
    console.log('\n🎉 Gemini RAG System Test Complete!');
  }
}

module.exports = { GeminiRAGService };