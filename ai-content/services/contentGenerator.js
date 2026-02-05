import OpenAI from 'openai';
import { Anthropic } from 'anthropic';
import fs from 'fs/promises';
import { researchService } from '../automation/researchService.js';

class AIContentService {
  constructor() {
    this.openai = new OpenAI({
      apiKey: process.env.OPENAI_API_KEY,
    });
    this.anthropic = new Anthropic({
      apiKey: process.env.ANTHROPIC_API_KEY,
    });
  }

  async transformResearch({ papers, style = 'professor-oh', contentType = 'newsletter' }) {
    const researchContext = papers.map(paper => ({
      title: paper.title,
      abstract: paper.abstract,
      keyFindings: paper.keyFindings,
      journal: paper.journal,
      date: paper.publicationDate,
    })).join('\n\n');

    const systemPrompt = this.getSystemPrompt(style, contentType);
    const userPrompt = this.getUserPrompt(researchContext, contentType);

    try {
      // Use GPT-4 for analytical content, Claude for creative writing
      const model = contentType === 'newsletter' ? 'gpt-4' : 'claude-3-sonnet';
      
      const response = model === 'gpt-4' 
        ? await this.generateWithOpenAI(systemPrompt, userPrompt)
        : await this.generateWithAnthropic(systemPrompt, userPrompt);

      return {
        title: response.title,
        body: response.body,
        keyInsights: response.keyInsights,
        practicalApplications: response.practicalApplications,
        sources: papers,
      };
    } catch (error) {
      console.error('AI Content Generation Error:', error);
      throw new Error('Failed to generate AI content');
    }
  }

  getSystemPrompt(style, contentType) {
    const basePrompt = `You are Professor Chang-Myung Oh, MD-PhD, a renowned longevity scientist with expertise in aging research, metabolic health, and biohacking.

WRITING STYLE:
- Authority-driven yet accessible
- Data-focused with practical implications  
- Incorporates cutting-edge research citations
- Balanced skepticism and optimism
- Uses precise medical terminology
- Highlights mechanisms and pathways

RESEARCH EXPERTISE:
- Senescence and cellular aging
- Metabolic interventions (GLP-1, SGLT2, etc.)
- Mitochondrial biogenesis and function
- Sarcopenia and muscle preservation
- Longevity pathways (mTOR, AMPK, sirtuins)
- Clinical trial interpretation
- Biohacking interventions

CONTENT GUIDELINES:
- Always cite specific studies and mechanisms
- Translate complex science into actionable insights
- Maintain scientific accuracy while being engaging
- Include practical applications for readers
- Acknowledge limitations and future directions`;

    switch (contentType) {
      case 'newsletter':
        return `${basePrompt}

FORMAT FOR NEWSLETTER:
- Engaging headline with hook
- 3-4 key research highlights with citations
- Practical takeaways for biohackers
- Brief mention of commercial implications
- 400-600 words total`;

      case 'deep-dive':
        return `${basePrompt}

FORMAT FOR DEEP DIVE:
- Comprehensive analysis of 1-2 key studies
- Mechanism explanations with pathway diagrams
- Clinical relevance and applications  
- Future research directions
- 800-1200 words`;

      case 'vod-lecture':
        return `${basePrompt}

FORMAT FOR VOD LECTURE:
- Introduction with hook
- 5-7 key research concepts
- Visual aids descriptions
- Case studies and examples
- Q&A style common questions
- Script for 15-20 minute video`;

      default:
        return basePrompt;
    }
  }

  getUserPrompt(researchContext, contentType) {
    return `Based on the following cutting-edge research papers, generate ${contentType} content:

RESEARCH CONTEXT:
${researchContext}

Please create content that:
1. Synthesizes findings across multiple papers
2. Identifies breakthrough patterns
3. Provides practical longevity insights
4. Maintains Professor Oh's authoritative voice
5. Includes specific mechanisms and pathways discussed

Ensure all scientific claims are grounded in the provided research and include practical applications for health optimization and longevity.`;
  }

  async generateWithOpenAI(systemPrompt, userPrompt) {
    const response = await this.openai.chat.completions.create({
      model: 'gpt-4',
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt }
      ],
      temperature: 0.7,
      max_tokens: 2000,
    });

    const content = response.choices[0].message.content;
    return this.parseResponse(content);
  }

  async generateWithAnthropic(systemPrompt, userPrompt) {
    const response = await this.anthropic.messages.create({
      model: 'claude-3-sonnet-20240229',
      max_tokens: 2000,
      temperature: 0.7,
      messages: [
        { role: 'user', content: `${systemPrompt}\n\n${userPrompt}` }
      ]
    });

    const content = response.content[0].text;
    return this.parseResponse(content);
  }

  parseResponse(content) {
    // Parse structured response from AI
    const titleMatch = content.match(/TITLE:\s*(.+)/i);
    const bodyMatch = content.match(/BODY:\s*((?:.|\s)*?)(?=\n\n|\nKEY INSIGHTS:|END)/i);
    const insightsMatch = content.match(/KEY INSIGHTS:\s*((?:.|\s)*?)(?=\n\n|\nPRACTICAL|END)/i);
    const practicalMatch = content.match(/PRACTICAL APPLICATIONS:\s*((?:.|\s)*?)(?=\n\n|\nEND|$)/i);

    return {
      title: titleMatch ? titleMatch[1].trim() : 'Latest Longevity Research',
      body: bodyMatch ? bodyMatch[1].trim() : content,
      keyInsights: insightsMatch ? insightsMatch[1].trim() : '',
      practicalApplications: practicalMatch ? practicalMatch[1].trim() : '',
    };
  }

  async generateContentSeries(topic, weeks = 4) {
    const contentSeries = [];
    
    for (let week = 1; week <= weeks; week++) {
      const researchPapers = await researchService.getWeeklyResearch(topic, week);
      const content = await this.transformResearch({
        papers: researchPapers,
        style: 'professor-oh',
        contentType: 'newsletter',
      });
      
      contentSeries.push({
        week,
        content,
        publishDate: this.getPublishDate(week),
      });
    }
    
    return contentSeries;
  }

  getPublishDate(week) {
    const now = new Date();
    const publishDate = new Date(now.getTime() + (week - 1) * 7 * 24 * 60 * 60 * 1000);
    return publishDate.toISOString().split('T')[0];
  }

  async optimizeForSEO(content) {
    const keywords = await this.extractKeywords(content.body);
    const metaDescription = content.body.substring(0, 160);
    
    return {
      ...content,
      seo: {
        title: content.title,
        description: metaDescription,
        keywords: keywords.join(', '),
        metaTitle: `${content.title} | Professor Chang-Myung Oh`,
      },
    };
  }

  async extractKeywords(text) {
    const response = await this.openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [
        {
          role: 'system',
          content: 'Extract 5-7 SEO keywords from longevity research content. Focus on scientific terms and biohacking concepts.'
        },
        {
          role: 'user',
          content: `Extract keywords from: ${text.substring(0, 1000)}...`
        }
      ],
      temperature: 0.3,
    });

    const keywords = response.choices[0].message.content
      .split(',')
      .map(k => k.trim().toLowerCase())
      .filter(k => k.length > 2);
    
    return keywords;
  }
}

export { AIContentService };