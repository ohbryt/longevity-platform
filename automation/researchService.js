import RSSParser from 'rss-parser';
import fetch from 'node-fetch';
import { GoogleSpreadsheet } from 'google-spreadsheet';

class ResearchCurationService {
  constructor() {
    this.sources = [
      {
        name: 'Nature Aging',
        rss: 'https://www.nature.com/nature/articles?journal=42926&type=latest&format=xml',
        filters: ['aging', 'longevity', 'senescence', 'lifespan']
      },
      {
        name: 'Cell Metabolism',
        rss: 'https://www.cell.com/cell/metabolism/current',
        filters: ['metabolism', 'metabolic', 'glucose', 'insulin']
      },
      {
        name: 'Science Translational Medicine',
        rss: 'https://www.science.org/journal/stm',
        filters: ['longevity', 'aging', 'therapeutic', 'clinical']
      },
      {
        name: 'Nature Medicine',
        rss: 'https://www.nature.com/nature/articles?type=latest&format=xml',
        filters: ['medicine', 'therapy', 'breakthrough', 'treatment']
      },
      {
        name: 'bioRxiv',
        rss: 'https://www.biorxiv.org/rss/aging.xml',
        filters: ['aging', 'longevity', 'lifespan', 'healthspan']
      }
    ];

    this.googleSheetId = process.env.GOOGLE_SHEET_ID;
    this.sheet = new GoogleSpreadsheet(this.googleSheetId);
  }

  async curateDailyResearch() {
    const allPapers = [];
    
    for (const source of this.sources) {
      console.log(`📚 Fetching from ${source.name}...`);
      const papers = await this.fetchRSSFeed(source);
      allPapers.push(...papers);
    }

    // Filter and rank papers by relevance
    const filteredPapers = this.filterRelevantPapers(allPapers);
    const rankedPapers = this.rankPapers(filteredPapers);

    // Store in Google Sheets for tracking
    await this.storeCuratedPapers(rankedPapers);

    return rankedPapers.slice(0, 10); // Top 10 for daily review
  }

  async fetchRSSFeed(source) {
    try {
      const response = await fetch(source.rss);
      const xml = await response.text();
      const feed = await RSSParser.parseString(xml);
      
      const papers = feed.items.map(item => ({
        title: item.title,
        link: item.link,
        pubDate: new Date(item.pubDate),
        journal: source.name,
        content: item.content || item.summary,
        doi: this.extractDOI(item.content || item.summary),
        authors: this.extractAuthors(item.content || item.summary),
        relevanceScore: this.calculateRelevance(item, source.filters),
      }));

      return papers;
    } catch (error) {
      console.error(`❌ Error fetching ${source.name}:`, error.message);
      return [];
    }
  }

  filterRelevantPapers(papers) {
    const relevantKeywords = [
      'aging', 'longevity', 'senescence', 'lifespan', 'healthspan',
      'metabolism', 'metabolic', 'glucose', 'insulin', 'glp-1',
      'sglt2', 'mitochondria', 'mitochondrial', 'autophagy',
      'sarcopenia', 'muscle', 'exercise', 'biohacking',
      'mTOR', 'AMPK', 'sirtuins', 'rapamycin', 'metformin'
    ];

    return papers.filter(paper => {
      const text = `${paper.title} ${paper.content}`.toLowerCase();
      const matches = relevantKeywords.filter(keyword => 
        text.includes(keyword.toLowerCase())
      ).length;
      
      return matches >= 2; // At least 2 relevant keywords
    });
  }

  rankPapers(papers) {
    return papers.sort((a, b) => {
      // Ranking criteria: Relevance, Recency, Journal Impact
      const scoreA = this.calculatePaperScore(a);
      const scoreB = this.calculatePaperScore(b);
      
      return scoreB - scoreA;
    });
  }

  calculatePaperScore(paper) {
    const now = new Date();
    const daysOld = (now - paper.pubDate) / (1000 * 60 * 60 * 24);
    
    // Relevance: 40% weight
    const relevanceScore = paper.relevanceScore * 0.4;
    
    // Recency: 30% weight (newer is better)
    const recencyScore = Math.max(0, 100 - daysOld) * 0.3;
    
    // Journal impact: 30% weight (simplified journal ranking)
    const journalScore = this.getJournalScore(paper.journal) * 0.3;
    
    return relevanceScore + recencyScore + journalScore;
  }

  getJournalScore(journal) {
    const journalRankings = {
      'Nature Aging': 95,
      'Cell Metabolism': 90,
      'Nature Medicine': 95,
      'Science Translational Medicine': 85,
      'bioRxiv': 60,
    };
    
    return journalRankings[journal] || 50;
  }

  calculateRelevance(item, filters) {
    const text = `${item.title} ${item.content}`.toLowerCase();
    const matches = filters.filter(keyword => text.includes(keyword.toLowerCase()));
    
    // Calculate relevance based on keyword density and position
    const titleMatches = filters.filter(keyword => 
      item.title.toLowerCase().includes(keyword.toLowerCase())
    ).length;
    
    const contentMatches = matches.length;
    
    // Title matches get 2x weight
    return (titleMatches * 2) + contentMatches;
  }

  extractDOI(content) {
    const doiMatch = content.match(/doi[:\s]*(10\.[\d]+\/[^\s]+)/i);
    return doiMatch ? doiMatch[1] : null;
  }

  extractAuthors(content) {
    const authorMatch = content.match(/(?:by|authors?[:\s]*)([^.\n]+)/i);
    return authorMatch ? authorMatch[1].split(',').map(a => a.trim()) : [];
  }

  async storeCuratedPapers(papers) {
    try {
      const rows = papers.map(paper => [
        new Date().toISOString(), // Curation date
        paper.title,
        paper.authors.join('; '),
        paper.journal,
        paper.pubDate.toISOString(),
        paper.link,
        paper.doi || '',
        this.calculateRelevanceText(paper),
        paper.relevanceScore,
        this.calculatePaperScore(paper),
      ]);

      await this.sheet.addRow(rows);
      console.log(`✅ Stored ${papers.length} papers in Google Sheets`);
    } catch (error) {
      console.error('❌ Error storing papers:', error.message);
    }
  }

  calculateRelevanceText(paper) {
    if (paper.relevanceScore >= 8) return 'Highly Relevant';
    if (paper.relevanceScore >= 5) return 'Moderately Relevant';
    return 'Minimally Relevant';
  }

  async getWeeklyResearch(topic, week) {
    // Get papers from the last 7 days
    const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    const recentPapers = await this.curateDailyResearch();
    
    return recentPapers.filter(paper => {
      const paperDate = new Date(paper.pubDate);
      return paperDate >= sevenDaysAgo;
    });
  }

  async generateMakeScenarios(papers) {
    const scenarios = [
      {
        name: 'Daily Newsletter Curation',
        trigger: 'Daily at 6 AM',
        actions: [
          'Extract top 5 papers from RSS feeds',
          'Filter for longevity relevance',
          'Generate AI summary using Professor Oh persona',
          'Store in content database',
          'Send to email list'
        ]
      },
      {
        name: 'Breaking Research Alert',
        trigger: 'Nature Aging + Cell Metabolism new papers',
        actions: [
          'Check for high-impact papers (score > 85)',
          'Generate urgent AI analysis',
          'Send immediate email alert',
          'Post to social media'
        ]
      },
      {
        name: 'Monthly Deep Dive',
        trigger: 'First Monday of month',
        actions: [
          'Select top breakthrough paper',
          'Generate comprehensive 1500-word analysis',
          'Create VOD script outline',
          'Schedule video recording'
        ]
      }
    ];

    return scenarios.map(scenario => ({
      ...scenario,
      paperCount: papers.length,
      topPapers: papers.slice(0, 3),
    }));
  }
}

export { ResearchCurationService };