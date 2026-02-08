#!/usr/bin/env python3
"""
자동화된 콘텐츠 파이프라인
Automated Content Pipeline for Longevity Knowledge Platform

논문 수집 → AI 요약/해석 → 팩트체크 → 발행 준비

Components:
1. Paper Discovery (PubMed, RSS feeds)
2. Document Processing (Docling)
3. Content Generation (Gemini/GPT-4)
4. Fact Checking (GPT-4)
5. Publishing Preparation
"""

import os
import re
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
from dotenv import load_dotenv


def parse_json_response(text: str) -> dict:
    """Parse JSON from AI response, stripping markdown code blocks if present"""
    # Strip ```json ... ``` or ``` ... ```
    cleaned = re.sub(r'^```(?:json)?\s*\n?', '', text.strip())
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract JSON object from mixed text
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            return json.loads(match.group())
        raise

# Load .env file
load_dotenv()

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
KIMI_API_KEY = os.getenv("KIMI_API_KEY")  # Moonshot AI - much cheaper alternative


@dataclass
class Paper:
    """Research paper metadata"""
    title: str
    authors: List[str]
    abstract: str
    journal: str
    doi: str
    pub_date: str
    url: str
    full_text: Optional[str] = None
    relevance_score: float = 0.0
    topics: List[str] = None


@dataclass
class ContentDraft:
    """AI-generated content draft"""
    paper: Paper
    content_type: str  # newsletter, blog, youtube_script, vod_lecture
    korean_title: str
    korean_summary: str
    korean_body: str
    english_title: str
    english_summary: str
    key_insights: List[str]
    practical_applications: List[str]
    citations: List[Dict]
    fact_check_notes: List[str]
    confidence_score: float
    created_at: str
    status: str  # draft, reviewed, published
    source: str = ""  # pubmed, biorxiv, medrxiv, clinical_trial


@dataclass
class ClinicalTrial:
    """Clinical trial metadata"""
    nct_id: str
    title: str
    status: str
    phase: str
    conditions: List[str]
    interventions: List[str]
    summary: str
    start_date: str
    url: str
    relevance_score: float = 0.0


class PaperDiscovery:
    """
    통합 논문 발견 시스템
    Multi-source paper discovery: PubMed, bioRxiv, medRxiv, ClinicalTrials.gov

    Integrates with MCP servers:
    - pubmed: PubMed indexed papers
    - biorxiv: bioRxiv/medRxiv preprints
    - clinical-trials: ClinicalTrials.gov
    - scholar-gateway: Academic papers
    """

    LONGEVITY_KEYWORDS = [
        # Core longevity
        "NAD+ metabolism", "senolytics", "cellular senescence",
        "mitochondrial dysfunction", "autophagy aging",
        "longevity interventions", "healthspan", "lifespan extension",
        "metabolic aging", "epigenetic clock", "telomere attrition",
        # Therapeutics
        "GLP-1 agonist aging", "rapamycin longevity", "metformin aging",
        "NMN supplementation", "resveratrol", "spermidine",
        # Emerging
        "senostatics", "SASP inhibitors", "inflammaging",
        # Cancer diagnosis & therapeutics
        "liquid biopsy cancer", "immunotherapy checkpoint",
        "CAR-T cell therapy", "cancer biomarker early detection",
        "targeted therapy oncology", "tumor microenvironment",
        # Korean research focus
        "Korean longevity", "Asian metabolic disease",
    ]

    # Broader keywords for clinical trials (more general terms work better)
    CLINICAL_TRIAL_KEYWORDS = [
        "aging", "longevity", "senolytic", "NAD+", "NMN",
        "rapamycin", "metformin anti-aging", "GLP-1",
        "healthspan", "biological age", "caloric restriction",
        "nicotinamide riboside", "senolytics dasatinib quercetin",
        # Cancer
        "immunotherapy cancer", "CAR-T", "liquid biopsy",
        "checkpoint inhibitor", "targeted therapy cancer",
    ]

    RELEVANT_JOURNALS = [
        "Nature Aging", "Cell Metabolism", "Aging Cell",
        "GeroScience", "Lancet Healthy Longevity",
        "Nature Medicine", "Cell", "Nature", "Science",
        "Journal of Clinical Investigation", "JAMA",
        "bioRxiv", "medRxiv",  # Preprint servers
    ]

    def __init__(self):
        self.pubmed_base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.biorxiv_base = "https://api.biorxiv.org"
        self.clinicaltrials_base = "https://clinicaltrials.gov/api/v2"

    # ============ PubMed Integration ============
    async def search_pubmed(
        self,
        query: str,
        max_results: int = 20,
        days_back: int = 7
    ) -> List[Paper]:
        """Search PubMed for recent papers"""
        import aiohttp

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        date_filter = f"{start_date.strftime('%Y/%m/%d')}:{end_date.strftime('%Y/%m/%d')}[dp]"

        search_url = f"{self.pubmed_base}/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": f"({query}) AND {date_filter}",
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                ids = data.get("esearchresult", {}).get("idlist", [])

        if not ids:
            return []

        return await self._fetch_pubmed_details(ids)

    async def _fetch_pubmed_details(self, pmids: List[str]) -> List[Paper]:
        """Fetch paper details from PubMed"""
        import aiohttp
        import xml.etree.ElementTree as ET

        fetch_url = f"{self.pubmed_base}/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml"
        }

        papers = []
        async with aiohttp.ClientSession() as session:
            async with session.get(fetch_url, params=params) as resp:
                if resp.status != 200:
                    return []
                xml_text = await resp.text()

        try:
            root = ET.fromstring(xml_text)
            for article in root.findall(".//PubmedArticle"):
                paper = self._parse_pubmed_article(article)
                if paper:
                    paper.topics = ["pubmed"]
                    papers.append(paper)
        except ET.ParseError:
            pass

        return papers

    def _parse_pubmed_article(self, article) -> Optional[Paper]:
        """Parse PubMed XML article"""
        try:
            medline = article.find(".//MedlineCitation")
            article_data = medline.find(".//Article")

            title = article_data.findtext(".//ArticleTitle", "")
            abstract = article_data.findtext(".//Abstract/AbstractText", "")

            authors = []
            for author in article_data.findall(".//Author"):
                last = author.findtext("LastName", "")
                first = author.findtext("ForeName", "")
                if last:
                    authors.append(f"{last} {first}".strip())

            journal = article_data.findtext(".//Journal/Title", "")
            pmid = medline.findtext(".//PMID", "")
            doi_elem = article_data.find(".//ELocationID[@EIdType='doi']")
            doi = doi_elem.text if doi_elem is not None else ""
            pub_date = medline.findtext(".//DateCompleted/Year", "")

            return Paper(
                title=title,
                authors=authors[:5],
                abstract=abstract,
                journal=journal,
                doi=doi,
                pub_date=pub_date,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                topics=[]
            )
        except Exception:
            return None

    # ============ bioRxiv/medRxiv Integration ============
    async def search_biorxiv(
        self,
        query: str,
        max_results: int = 20,
        days_back: int = 30,
        server: str = "biorxiv"  # or "medrxiv"
    ) -> List[Paper]:
        """
        Search bioRxiv/medRxiv for preprints

        Note: bioRxiv API returns papers by date range, then we filter by query
        """
        import aiohttp

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # bioRxiv API endpoint for recent papers
        # Format: /details/[server]/[start_date]/[end_date]/[cursor]
        url = f"{self.biorxiv_base}/details/{server}/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}/0/json"

        papers = []
        try:
            async with aiohttp.ClientSession() as session:
                # Paginate up to 3 pages (300 papers) for better coverage
                for cursor in range(0, 300, 100):
                    page_url = f"{self.biorxiv_base}/details/{server}/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}/{cursor}/json"
                    async with session.get(page_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status != 200:
                            break
                        data = await resp.json()

                    collection = data.get("collection", [])
                    if not collection:
                        break

                    # Filter by query keywords (flexible word matching)
                    query_words = [w.lower().strip("+") for w in query.split() if len(w) >= 3]
                    for item in collection:
                        title = item.get("title", "").lower()
                        abstract = item.get("abstract", "").lower()
                        text = title + " " + abstract

                        # Match: ALL query words must appear (AND logic)
                        matches = sum(1 for w in query_words if w in text)
                        if query_words and matches >= len(query_words):
                            paper = Paper(
                                title=item.get("title", ""),
                                authors=item.get("authors", "").split("; ")[:5],
                                abstract=item.get("abstract", ""),
                                journal=f"{server} (preprint)",
                                doi=item.get("doi", ""),
                                pub_date=item.get("date", ""),
                                url=f"https://www.{server}.org/content/{item.get('doi', '')}",
                                topics=[server, "preprint"]
                            )
                            papers.append(paper)

                    if len(papers) >= max_results:
                        break

        except Exception as e:
            print(f"{server} search error: {e}")

        return papers[:max_results]

    async def search_medrxiv(
        self,
        query: str,
        max_results: int = 20,
        days_back: int = 30
    ) -> List[Paper]:
        """Search medRxiv for medical preprints"""
        return await self.search_biorxiv(query, max_results, days_back, server="medrxiv")

    # ============ ClinicalTrials.gov Integration ============
    async def search_clinical_trials(
        self,
        query: str,
        max_results: int = 20,
        status: str = "RECRUITING"  # RECRUITING, COMPLETED, ACTIVE_NOT_RECRUITING
    ) -> List[ClinicalTrial]:
        """
        Search ClinicalTrials.gov for relevant trials

        Useful for finding cutting-edge longevity interventions in human trials
        """
        import aiohttp

        url = f"{self.clinicaltrials_base}/studies"
        params = {
            "query.term": query,
            "filter.overallStatus": status,
            "pageSize": max_results,
            "format": "json"
        }

        trials = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()

            for study in data.get("studies", []):
                protocol = study.get("protocolSection", {})
                id_module = protocol.get("identificationModule", {})
                status_module = protocol.get("statusModule", {})
                desc_module = protocol.get("descriptionModule", {})
                conditions_module = protocol.get("conditionsModule", {})
                interventions_module = protocol.get("armsInterventionsModule", {})

                nct_id = id_module.get("nctId", "")

                trial = ClinicalTrial(
                    nct_id=nct_id,
                    title=id_module.get("briefTitle", ""),
                    status=status_module.get("overallStatus", ""),
                    phase=", ".join(protocol.get("designModule", {}).get("phases", [])),
                    conditions=conditions_module.get("conditions", []),
                    interventions=[
                        i.get("name", "") for i in
                        interventions_module.get("interventions", [])
                    ],
                    summary=desc_module.get("briefSummary", ""),
                    start_date=status_module.get("startDateStruct", {}).get("date", ""),
                    url=f"https://clinicaltrials.gov/study/{nct_id}"
                )
                trials.append(trial)

        except Exception as e:
            print(f"ClinicalTrials.gov search error: {e}")

        return trials

    def clinical_trial_to_paper(self, trial: ClinicalTrial) -> Paper:
        """Convert ClinicalTrial to Paper format for unified processing"""
        return Paper(
            title=f"[Clinical Trial] {trial.title}",
            authors=[],
            abstract=trial.summary,
            journal=f"ClinicalTrials.gov ({trial.phase})",
            doi=trial.nct_id,
            pub_date=trial.start_date,
            url=trial.url,
            topics=["clinical_trial"] + trial.conditions[:3]
        )

    # ============ Unified Multi-Source Search ============
    async def search_all_sources(
        self,
        query: str,
        max_per_source: int = 10,
        days_back: int = 14,
        include_trials: bool = True
    ) -> Dict[str, List]:
        """
        Search all sources in parallel

        Returns:
            {
                "pubmed": [Paper, ...],
                "biorxiv": [Paper, ...],
                "medrxiv": [Paper, ...],
                "clinical_trials": [ClinicalTrial, ...]
            }
        """
        tasks = [
            self.search_pubmed(query, max_per_source, days_back),
            self.search_biorxiv(query, max_per_source, days_back * 2),  # wider window for preprints
            self.search_medrxiv(query, max_per_source, days_back * 2),
        ]

        if include_trials:
            # Use simpler query for clinical trials (first significant word)
            trial_query = query.split()[0] if query else "longevity"
            tasks.append(self.search_clinical_trials(trial_query, max_per_source))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "pubmed": results[0] if not isinstance(results[0], Exception) else [],
            "biorxiv": results[1] if not isinstance(results[1], Exception) else [],
            "medrxiv": results[2] if not isinstance(results[2], Exception) else [],
            "clinical_trials": results[3] if len(results) > 3 and not isinstance(results[3], Exception) else []
        }

    async def get_weekly_papers(self, include_preprints: bool = True, include_trials: bool = True) -> List[Paper]:
        """
        Get this week's relevant papers from all sources

        Args:
            include_preprints: Include bioRxiv/medRxiv preprints
            include_trials: Include clinical trials (converted to Paper format)
        """
        all_papers = []
        print("📚 Searching multiple sources...")

        # Search each source for top keywords
        for keyword in self.LONGEVITY_KEYWORDS[:5]:
            print(f"   🔍 Keyword: {keyword}")

            # PubMed (always)
            pubmed_papers = await self.search_pubmed(keyword, max_results=10, days_back=7)
            for p in pubmed_papers:
                if not p.topics or "pubmed" not in p.topics:
                    p.topics = ["pubmed"]
            all_papers.extend(pubmed_papers)

            if include_preprints:
                # bioRxiv
                biorxiv_papers = await self.search_biorxiv(keyword, max_results=5, days_back=30)
                all_papers.extend(biorxiv_papers)

                # medRxiv (30 days, broader window for medical preprints)
                medrxiv_papers = await self.search_medrxiv(keyword, max_results=5, days_back=30)
                all_papers.extend(medrxiv_papers)

        # Clinical trials use broader keywords for better results
        if include_trials:
            for keyword in self.CLINICAL_TRIAL_KEYWORDS[:6]:
                print(f"   🏥 Clinical trial keyword: {keyword}")
                trials = await self.search_clinical_trials(keyword, max_results=5)
                for trial in trials:
                    all_papers.append(self.clinical_trial_to_paper(trial))

        # Deduplicate by DOI
        seen_dois = set()
        unique_papers = []
        for paper in all_papers:
            key = paper.doi or paper.title
            if key and key not in seen_dois:
                seen_dois.add(key)
                unique_papers.append(paper)

        # Score and rank
        for paper in unique_papers:
            paper.relevance_score = self._calculate_relevance(paper)

        print(f"   ✅ Found {len(unique_papers)} unique papers")

        # Ensure source diversity: reserve slots for each source
        sorted_papers = sorted(unique_papers, key=lambda p: p.relevance_score, reverse=True)

        # Group by source
        by_source = {"pubmed": [], "biorxiv": [], "medrxiv": [], "clinical_trial": []}
        for paper in sorted_papers:
            src = "pubmed"
            for t in (paper.topics or []):
                if t in by_source:
                    src = t
                    break
            by_source[src].append(paper)

        # Guarantee minimum representation: 2 per non-empty source, fill rest by score
        selected = []
        used = set()
        for source in ["clinical_trial", "medrxiv", "biorxiv", "pubmed"]:
            for paper in by_source[source][:3]:  # up to 3 per source guaranteed
                key = paper.doi or paper.title
                if key not in used:
                    selected.append(paper)
                    used.add(key)

        # Fill remaining slots with highest-scored papers
        for paper in sorted_papers:
            if len(selected) >= 15:
                break
            key = paper.doi or paper.title
            if key not in used:
                selected.append(paper)
                used.add(key)

        return selected[:15]

    def _calculate_relevance(self, paper: Paper) -> float:
        """Calculate relevance score for a paper"""
        score = 0.0

        # Source bonus
        if paper.topics:
            if "clinical_trial" in paper.topics:
                score += 2.0  # Clinical trials are high value
            if "preprint" in paper.topics:
                score += 0.5  # Preprints are cutting edge

        # Journal impact
        if paper.journal:
            for journal in self.RELEVANT_JOURNALS:
                if journal.lower() in paper.journal.lower():
                    score += 3.0
                    break

        # Keyword matches in title
        title_lower = paper.title.lower()
        for keyword in self.LONGEVITY_KEYWORDS:
            if keyword.lower() in title_lower:
                score += 1.0

        # Abstract quality
        if paper.abstract and len(paper.abstract) > 500:
            score += 1.0

        return score


class DocumentProcessor:
    """
    문서 처리기 (Docling 기반)
    Process PDFs and documents using Docling
    """

    def __init__(self):
        self.docling_available = self._check_docling()

    def _check_docling(self) -> bool:
        """Check if docling is available"""
        try:
            from docling.document_converter import DocumentConverter
            return True
        except ImportError:
            return False

    async def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Process a PDF file and extract structured content"""
        if not self.docling_available:
            return {"error": "Docling not installed. Run: pip install docling"}

        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        result = converter.convert(pdf_path)
        doc = result.document

        return {
            "markdown": doc.export_to_markdown(),
            "text": doc.export_to_text(),
            "tables": [table.export_to_dataframe().to_dict() for table in doc.tables],
            "figures": [{"caption": fig.caption} for fig in doc.pictures],
            "metadata": {
                "title": doc.title,
                "pages": len(doc.pages) if hasattr(doc, 'pages') else 0
            }
        }


class ContentGenerator:
    """
    AI 콘텐츠 생성기
    Generates content using Gemini or GPT-4

    한국어로 따뜻하고 전문적인 콘텐츠 생성
    """

    SYSTEM_PROMPT_KOREAN = """당신은 브라운바이오텍(Brown Biotech)의 장수과학 리서치팀 관점으로 글을 작성하는 AI 어시스턴트입니다.

역할:
- 최신 의학 연구를 대중이 이해하기 쉽게 설명
- 과학적 정확성을 유지하면서도 따뜻하고 공감적인 톤 유지
- 실용적인 건강 인사이트 제공

글쓰기 스타일:
- 전문 용어는 쉬운 설명과 함께 사용
- 독자와 대화하듯 친근하게 (존댓말 사용)
- 핵심 메시지를 명확하게
- 희망적이고 긍정적인 톤 유지

주의사항:
- 의료적 조언은 "~할 수 있습니다", "~라고 합니다" 형식으로
- 출처를 명확히 밝히기
- 과장하거나 확정적인 표현 자제"""

    CONTENT_TEMPLATES = {
        "newsletter": """
## 뉴스레터 형식

제목: [흥미를 끄는 질문 형식의 제목]

인사말:
안녕하세요, 브라운바이오텍입니다.
이번 주에 주목할 만한 연구가 발표되었습니다.

핵심 내용 (3-4 문단):
- 연구 배경과 중요성
- 주요 발견 내용
- 우리 건강에 미치는 의미
- 실천할 수 있는 점

마무리:
건강한 한 주 보내시기 바랍니다.

총 길이: 400-600자
""",
        "blog": """
## 블로그 형식

제목: [SEO 최적화된 제목]
부제: [내용을 요약하는 한 줄]

도입부:
- 독자의 관심을 끄는 질문이나 상황 제시
- 이 연구가 왜 중요한지

본문 (5-7 문단):
1. 연구 배경
2. 방법론 (간략히)
3. 주요 결과
4. 전문가 해석
5. 한계점 (균형 잡힌 시각)
6. 실생활 적용

결론:
- 핵심 메시지 요약
- 독자 행동 유도 (CTA)

총 길이: 800-1200자
""",
        "youtube_script": """
## 유튜브 스크립트 형식

[오프닝 - 10초]
"여러분, 오늘 발표된 충격적인 연구 결과가 있습니다..."

[핵심 질문 - 20초]
"[연구 주제]가 정말 [효과]에 도움이 될까요?"

[연구 소개 - 1분]
- 어디서, 누가, 어떻게 연구했는지
- 왜 이 연구가 중요한지

[결과 설명 - 2분]
- 핵심 발견 1, 2, 3
- 그래프/표 설명 시점 표시 [자막: ...]

[의미 해석 - 1분]
- 우리에게 어떤 의미인지
- 주의할 점

[실천 팁 - 1분]
- 오늘부터 할 수 있는 것

[클로징 - 30초]
- 구독/좋아요 요청
- 다음 영상 예고

총 길이: 5-7분 분량
"""
    }

    def __init__(self, provider: str = "gemini"):
        """
        Initialize content generator

        Args:
            provider: "gemini", "openai", or "kimi"
        """
        self.provider = provider

    def _provider_has_key(self, provider: str) -> bool:
        if provider == "kimi":
            return bool(KIMI_API_KEY)
        if provider == "gemini":
            return bool(GEMINI_API_KEY)
        if provider == "openai":
            return bool(OPENAI_API_KEY)
        return False

    def _fallback_provider(self) -> Optional[str]:
        """
        Choose a reasonable fallback provider when the primary provider errors.
        Preference: kimi -> gemini -> openai (cost first), but only if keys exist.
        """
        for p in ("kimi", "gemini", "openai"):
            if p != self.provider and self._provider_has_key(p):
                return p
        return None

    async def generate_content(
        self,
        paper: Paper,
        content_type: str = "newsletter",
        language: str = "korean"
    ) -> ContentDraft:
        """Generate content from a research paper"""

        template = self.CONTENT_TEMPLATES.get(content_type, self.CONTENT_TEMPLATES["newsletter"])

        prompt = f"""다음 연구 논문을 바탕으로 {content_type} 콘텐츠를 작성해주세요.

## 논문 정보
제목: {paper.title}
저자: {', '.join(paper.authors)}
저널: {paper.journal}
발행일: {paper.pub_date}

## 초록
{paper.abstract}

## 작성 형식
{template}

## 추가 요청사항
1. 한국어로 작성
2. 전문 용어는 영어 원문을 괄호로 병기
3. 핵심 인사이트 3가지 별도 정리
4. 실용적 적용 방법 2-3가지 제안
5. 인용 출처 명시

JSON 형식으로 응답해주세요:
{{
    "korean_title": "제목",
    "korean_summary": "2-3문장 요약",
    "korean_body": "본문 전체",
    "key_insights": ["인사이트1", "인사이트2", "인사이트3"],
    "practical_applications": ["적용1", "적용2"],
    "confidence_score": 0.0-1.0
}}"""

        async def call_with_provider(provider: str) -> str:
            if provider == "gemini":
                return await self._call_gemini(prompt)
            if provider == "kimi":
                return await self._call_kimi(prompt)
            return await self._call_openai(prompt)

        response: str
        try:
            response = await call_with_provider(self.provider)
        except Exception:
            fb = self._fallback_provider()
            if not fb:
                raise
            response = await call_with_provider(fb)

        try:
            content_data = parse_json_response(response)
        except json.JSONDecodeError:
            # Treat malformed output as a hard failure so we can try another paper/provider.
            raise ValueError("AI response was not valid JSON")

        # Determine source from paper topics
        source = "pubmed"  # default
        if paper.topics:
            if "clinical_trial" in paper.topics:
                source = "clinical_trial"
            elif "medrxiv" in paper.topics:
                source = "medrxiv"
            elif "biorxiv" in paper.topics:
                source = "biorxiv"

        return ContentDraft(
            paper=paper,
            content_type=content_type,
            korean_title=content_data.get("korean_title", ""),
            korean_summary=content_data.get("korean_summary", ""),
            korean_body=content_data.get("korean_body", ""),
            english_title=paper.title,
            english_summary=paper.abstract,  # Full abstract, not truncated
            key_insights=content_data.get("key_insights", []),
            practical_applications=content_data.get("practical_applications", []),
            citations=[{"doi": paper.doi, "title": paper.title, "journal": paper.journal}],
            fact_check_notes=[],
            confidence_score=content_data.get("confidence_score", 0.5),
            created_at=datetime.now().isoformat(),
            status="draft",
            source=source,
        )

    async def _call_gemini(self, prompt: str, max_retries: int = 3) -> str:
        """Call Gemini API with retry on rate limit (new google.genai SDK)"""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)

        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[self.SYSTEM_PROMPT_KOREAN + "\n\n" + prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        max_output_tokens=8192,
                        safety_settings=[
                            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                        ],
                    ),
                )
                if not getattr(response, "text", None):
                    raise RuntimeError("Gemini returned empty response")
                return response.text
            except Exception as e:
                error_str = str(e)
                if "429" in error_str and attempt < max_retries - 1:
                    wait = (attempt + 1) * 15
                    print(f"   ⏳ Rate limit, {wait}초 대기 후 재시도 ({attempt + 1}/{max_retries})...")
                    await asyncio.sleep(wait)
                    continue
                raise RuntimeError(f"Gemini API error: {e}") from e

    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API"""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT_KOREAN},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2048
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("OpenAI returned empty response")
        return content

    async def _call_kimi(self, prompt: str) -> str:
        """
        Call Kimi (Moonshot AI) API - 저렴한 대안

        Pricing (2026):
        - Input: $0.45-0.60 / 1M tokens
        - Output: $2.50 / 1M tokens
        - 75% discount with caching

        vs OpenAI GPT-4o:
        - Input: $2.50 / 1M tokens
        - Output: $10.00 / 1M tokens
        """
        from openai import AsyncOpenAI

        # Kimi uses OpenAI-compatible API
        client = AsyncOpenAI(
            api_key=KIMI_API_KEY,
            base_url="https://api.moonshot.ai/v1",
            timeout=120.0  # Kimi can be slower, allow 2 min
        )

        response = await client.chat.completions.create(
            model="moonshot-v1-8k",  # Use 8k for faster response
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT_KOREAN},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2048
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("Kimi returned empty response")
        return content

    async def revise_content(
        self,
        paper: Paper,
        draft: ContentDraft,
        issues: List[str],
        content_type: str = "newsletter",
    ) -> ContentDraft:
        """
        Try to auto-fix a draft based on fact-check issues.
        This is intentionally conservative: prefer removing/qualifying claims over inventing details.
        """
        issues_text = "\n".join(f"- {i}" for i in (issues or [])[:8])
        prompt = f"""다음 콘텐츠를 원본 초록 범위 내에서 수정해주세요.

중요:
- 초록/제목에 없는 숫자, 저자, 연도, 결과를 새로 만들지 마세요.
- 확실하지 않으면 '초록에서 확인되지 않습니다'라고 명시하세요.
- 용어는 원문 의미를 유지하세요(예: knockout vs inhibition 등).
- 출력은 반드시 JSON만(코드블록/설명 없이) 반환하세요.

## 원본 논문
제목: {paper.title}
저자: {', '.join(paper.authors)}
저널: {paper.journal}
발행일: {paper.pub_date}

초록:
{paper.abstract}

## 기존 콘텐츠(JSON 일부)
korean_title: {draft.korean_title}
korean_summary: {draft.korean_summary}
korean_body:
{draft.korean_body}

## 팩트체크 이슈
{issues_text}

JSON 형식으로 응답:
{{
  "korean_title": "...",
  "korean_summary": "...",
  "korean_body": "...",
  "key_insights": ["...", "...", "..."],
  "practical_applications": ["...", "..."],
  "confidence_score": 0.0-1.0
}}"""

        original_provider = self.provider
        try:
            response = await (self._call_gemini(prompt) if self.provider == "gemini"
                              else self._call_kimi(prompt) if self.provider == "kimi"
                              else self._call_openai(prompt))
        except Exception:
            fb = self._fallback_provider()
            if not fb:
                raise
            self.provider = fb
            response = await (self._call_gemini(prompt) if self.provider == "gemini"
                              else self._call_kimi(prompt) if self.provider == "kimi"
                              else self._call_openai(prompt))
        finally:
            self.provider = original_provider

        content_data = parse_json_response(response)
        draft.korean_title = content_data.get("korean_title", draft.korean_title)
        draft.korean_summary = content_data.get("korean_summary", draft.korean_summary)
        draft.korean_body = content_data.get("korean_body", draft.korean_body)
        draft.key_insights = content_data.get("key_insights", draft.key_insights)
        draft.practical_applications = content_data.get("practical_applications", draft.practical_applications)
        draft.confidence_score = content_data.get("confidence_score", draft.confidence_score)
        return draft


class FactChecker:
    """
    팩트 체커
    Validates content accuracy using GPT-4 or Kimi (cheaper)
    """

    def __init__(self, provider: str = "gemini"):
        """
        Initialize fact checker

        Args:
            provider: "gemini", "openai", or "kimi"
        """
        self.provider = provider

    FACT_CHECK_PROMPT = """당신은 의학 논문 팩트체커입니다.

다음 AI 생성 콘텐츠가 원본 논문과 일치하는지 검증해주세요.

## 원본 논문
제목: {title}
초록: {abstract}

## AI 생성 콘텐츠
{content}

## 검증 항목
1. 숫자/통계 정확성
2. 인과관계 왜곡 여부
3. 과장된 표현 여부
4. 누락된 중요 정보
5. 잠재적 오해 가능성

JSON 형식으로 응답:
{{
    "accuracy_score": 0.0-1.0,
    "issues": ["문제점1", "문제점2"],
    "suggestions": ["수정제안1", "수정제안2"],
    "safe_to_publish": true/false
}}"""

    async def check(self, draft: ContentDraft) -> Dict[str, Any]:
        """Fact-check a content draft"""
        prompt = self.FACT_CHECK_PROMPT.format(
            title=draft.paper.title,
            abstract=draft.paper.abstract,
            content=draft.korean_body
        )

        if self.provider == "kimi":
            return await self._check_with_kimi(prompt)
        elif self.provider == "gemini":
            return await self._check_with_gemini(prompt)
        else:
            return await self._check_with_openai(prompt)

    async def _check_with_gemini(self, prompt: str) -> Dict[str, Any]:
        """Fact-check using Gemini (new google.genai SDK)"""
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=GEMINI_API_KEY)

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=4096,
                    safety_settings=[
                        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                    ],
                ),
            )
            return parse_json_response(response.text)
        except json.JSONDecodeError:
            return {
                "accuracy_score": 0.7,
                "issues": ["JSON 파싱 실패 - 수동 검토 필요"],
                "suggestions": [],
                "safe_to_publish": False
            }
        except Exception as e:
            return {
                "accuracy_score": 0.0,
                "issues": [f"Fact check failed (Gemini): {e}"],
                "suggestions": [],
                "safe_to_publish": False
            }

    async def _check_with_openai(self, prompt: str) -> Dict[str, Any]:
        """Fact-check using OpenAI GPT-4"""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=OPENAI_API_KEY)

            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1024
            )

            return parse_json_response(response.choices[0].message.content)
        except Exception as e:
            return {
                "accuracy_score": 0.0,
                "issues": [f"Fact check failed: {e}"],
                "suggestions": [],
                "safe_to_publish": False
            }

    async def _check_with_kimi(self, prompt: str) -> Dict[str, Any]:
        """Fact-check using Kimi (cheaper alternative)"""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=KIMI_API_KEY,
                base_url="https://api.moonshot.ai/v1",
                timeout=120.0
            )

            response = await client.chat.completions.create(
                model="moonshot-v1-8k",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1024
            )

            return parse_json_response(response.choices[0].message.content)
        except Exception as e:
            return {
                "accuracy_score": 0.0,
                "issues": [f"Fact check failed (Kimi): {e}"],
                "suggestions": [],
                "safe_to_publish": False
            }


class ContentPipeline:
    """
    전체 콘텐츠 파이프라인
    Orchestrates the entire content generation workflow

    Provider options:
    - "gemini": Google Gemini (default, moderate cost)
    - "openai": OpenAI GPT-4 (highest quality, highest cost)
    - "kimi": Moonshot Kimi (good quality, lowest cost - recommended for budget)
    """

    def __init__(self, ai_provider: str = "gemini", fact_check_provider: str = None):
        """
        Initialize content pipeline

        Args:
            ai_provider: Provider for content generation ("gemini", "openai", "kimi")
            fact_check_provider: Provider for fact checking (defaults to ai_provider)
        """
        self.discovery = PaperDiscovery()
        self.doc_processor = DocumentProcessor()
        self.generator = ContentGenerator(provider=ai_provider)
        # Use same provider for fact-check by default
        fc_provider = fact_check_provider or ai_provider
        self.fact_checker = FactChecker(provider=fc_provider)

    async def run_weekly_pipeline(
        self,
        include_preprints: bool = True,
        include_trials: bool = True
    ) -> List[ContentDraft]:
        """
        주간 콘텐츠 파이프라인 실행 (멀티소스)

        데이터 소스:
        - PubMed: 피어리뷰 논문
        - bioRxiv/medRxiv: 프리프린트 (최신 연구)
        - ClinicalTrials.gov: 진행 중인 임상시험

        파이프라인:
        1. 멀티소스 논문 수집
        2. 상위 5개 선정
        3. 각 논문별 뉴스레터 콘텐츠 생성
        4. 팩트체크
        5. 검토 대기 상태로 저장
        """
        print("🔍 멀티소스 논문 수집 중...")
        print("   📚 Sources: PubMed", end="")
        if include_preprints:
            print(" + bioRxiv + medRxiv", end="")
        if include_trials:
            print(" + ClinicalTrials.gov", end="")
        print()

        papers = await self.discovery.get_weekly_papers(
            include_preprints=include_preprints,
            include_trials=include_trials
        )

        # Show source breakdown
        source_counts = {"pubmed": 0, "biorxiv": 0, "medrxiv": 0, "clinical_trial": 0}
        for paper in papers:
            for topic in (paper.topics or []):
                if topic in source_counts:
                    source_counts[topic] += 1
                    break  # count each paper once

        print(f"\n📊 수집 결과:")
        for source, count in source_counts.items():
            icon = {"pubmed": "📄", "biorxiv": "🧬", "medrxiv": "🏥", "clinical_trial": "💊"}.get(source, "•")
            print(f"   {icon} {source}: {count}개")
        print(f"   총 {len(papers)}개 논문 발견")

        # Target number of publishable drafts. If a draft can't be auto-fixed, try the next paper.
        target_ready = int(os.getenv("TARGET_READY_DRAFTS", "5"))
        max_papers = int(os.getenv("MAX_PAPERS_TO_PROCESS", "15"))
        max_revisions = int(os.getenv("MAX_AUTO_REVISIONS", "2"))

        drafts: List[ContentDraft] = []
        ready_count = 0
        processed = 0

        for paper in papers:
            if processed >= max_papers or ready_count >= target_ready:
                break
            processed += 1

            print(f"\n📝 콘텐츠 생성 중 ({ready_count + 1}/{target_ready}): {paper.title[:50]}...")

            try:
                draft = await self.generator.generate_content(
                    paper,
                    content_type="newsletter",
                    language="korean"
                )
            except Exception as e:
                print(f"   ⚠️ 생성 실패(건너뜀): {e}")
                continue

            # Fact check + auto-revise loop
            for attempt in range(max_revisions + 1):
                print(f"   ✓ 팩트체크 중...")
                fact_result = await self.fact_checker.check(draft)
                draft.fact_check_notes = fact_result.get("issues", [])

                if fact_result.get("safe_to_publish", False):
                    draft.status = "ready_for_review"
                    print(f"   ✅ 검토 준비 완료 (정확도: {fact_result.get('accuracy_score', 0):.0%})")
                    break

                # Auto-revise if we still have attempts left
                if attempt < max_revisions and draft.fact_check_notes:
                    print(f"   🔁 자동 수정 시도 ({attempt + 1}/{max_revisions})...")
                    try:
                        draft = await self.generator.revise_content(
                            paper=paper,
                            draft=draft,
                            issues=draft.fact_check_notes,
                            content_type="newsletter",
                        )
                        continue
                    except Exception as e:
                        print(f"   ⚠️ 자동 수정 실패: {e}")

                draft.status = "needs_revision"
                if draft.fact_check_notes:
                    print(f"   ⚠️ 수정 필요: {', '.join(draft.fact_check_notes[:2])}")
                else:
                    print(f"   ⚠️ 수정 필요: 팩트체크 실패")
                break

            drafts.append(draft)
            if draft.status == "ready_for_review":
                ready_count += 1

            # Rate limit 방지: 논문 사이 10초 대기
            if ready_count < target_ready:
                await asyncio.sleep(10)

        return drafts

    async def generate_single_content(
        self,
        paper: Paper,
        content_type: str = "newsletter"
    ) -> ContentDraft:
        """단일 논문 콘텐츠 생성"""
        draft = await self.generator.generate_content(paper, content_type)
        fact_result = await self.fact_checker.check(draft)
        draft.fact_check_notes = fact_result.get("issues", [])
        draft.status = "ready_for_review" if fact_result.get("safe_to_publish") else "needs_revision"
        return draft

    def save_drafts(self, drafts: List[ContentDraft], output_dir: str = "content_drafts"):
        """Save drafts to JSON files"""
        os.makedirs(output_dir, exist_ok=True)

        for draft in drafts:
            filename = f"{draft.created_at[:10]}_{draft.content_type}_{draft.paper.doi.replace('/', '_')[:20]}.json"
            filepath = os.path.join(output_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(asdict(draft), f, ensure_ascii=False, indent=2)

        print(f"\n💾 {len(drafts)}개 콘텐츠 저장 완료: {output_dir}/")


# Example usage
async def main():
    """Example: Run weekly content pipeline with multi-source discovery"""
    print("=" * 60)
    print("🧬 장수 지식 플랫폼 - 자동 콘텐츠 파이프라인")
    print("=" * 60)

    # Source configuration
    include_preprints = os.getenv("INCLUDE_PREPRINTS", "true").lower() == "true"
    include_trials = os.getenv("INCLUDE_TRIALS", "true").lower() == "true"

    print("\n📡 데이터 소스 설정:")
    print(f"   • PubMed: ✅ (항상 활성)")
    print(f"   • bioRxiv/medRxiv: {'✅' if include_preprints else '❌'}")
    print(f"   • ClinicalTrials.gov: {'✅' if include_trials else '❌'}")

    # Provider 선택 (비용 순: kimi < gemini < openai)
    ai_provider = os.getenv("AI_PROVIDER", "kimi")
    if not os.getenv("KIMI_API_KEY") and ai_provider == "kimi":
        ai_provider = "gemini"  # Fallback to gemini
    if not os.getenv("GEMINI_API_KEY") and ai_provider == "gemini":
        ai_provider = "openai"  # Fallback to openai

    # Fact-check provider should be stable and allowed to be different from generation.
    fact_check_provider = os.getenv("FACT_CHECK_PROVIDER", "").strip().lower() or ""
    if fact_check_provider not in ("kimi", "gemini", "openai"):
        fact_check_provider = ""
    if not fact_check_provider:
        # Prefer Kimi for cost, then OpenAI, then fall back to generation provider.
        if os.getenv("KIMI_API_KEY"):
            fact_check_provider = "kimi"
        elif os.getenv("OPENAI_API_KEY"):
            fact_check_provider = "openai"
        else:
            fact_check_provider = ai_provider

    print(f"\n🤖 AI Provider: {ai_provider} (fact-check: {fact_check_provider})")
    pipeline = ContentPipeline(ai_provider=ai_provider, fact_check_provider=fact_check_provider)

    # Run weekly pipeline with multi-source
    drafts = await pipeline.run_weekly_pipeline(
        include_preprints=include_preprints,
        include_trials=include_trials
    )

    # Save drafts
    pipeline.save_drafts(drafts)

    # Generate Instagram card news images
    try:
        from card_news_generator import CardNewsGenerator
        print("\n🎨 Instagram 카드뉴스 생성 중...")
        card_gen = CardNewsGenerator()
        for draft in drafts:
            paths = card_gen.generate_for_draft(draft)
            print(f"   📸 {len(paths)} slides: {draft.korean_title[:40]}...")
        print("✅ 카드뉴스 생성 완료")
    except Exception as e:
        print(f"⚠️ 카드뉴스 생성 실패 (계속 진행): {e}")

    # Instagram auto-posting (opt-in via env var)
    instagram_enabled = os.getenv("INSTAGRAM_AUTO_POST", "false").lower() == "true"
    if instagram_enabled:
        try:
            from instagram_poster import InstagramPoster
            print("\n📱 Instagram 자동 포스팅 중...")
            poster = InstagramPoster(
                ig_user_id=os.getenv("INSTAGRAM_USER_ID"),
                access_token=os.getenv("INSTAGRAM_ACCESS_TOKEN"),
                github_repo=os.getenv("GITHUB_REPOSITORY", "chang-myungoh/longevity-platform"),
                pages_base_url=os.getenv("PAGES_BASE_URL", "https://chang-myungoh.github.io/longevity-platform"),
            )

            # Build list of (draft_data, card_news_dir) pairs
            drafts_with_dirs = []
            card_news_base = os.path.join(os.path.dirname(__file__), "card_news")
            for draft in drafts:
                from dataclasses import asdict as _asdict
                draft_data = _asdict(draft)
                # Reconstruct card_news dir name (matches CardNewsGenerator logic)
                date_str = draft.created_at[:10] if draft.created_at else datetime.now().strftime("%Y-%m-%d")
                doi = draft.paper.doi or ""
                slug = doi.replace("/", "-").replace(".", "-").lower()[:40] if doi else "untitled"
                card_dir = os.path.join(card_news_base, f"{date_str}_{slug}")
                if os.path.isdir(card_dir):
                    drafts_with_dirs.append((draft_data, card_dir))
                else:
                    print(f"   ⚠️ Card news not found: {card_dir}")

            await poster.post_batch(drafts_with_dirs)
        except Exception as e:
            print(f"⚠️ Instagram 포스팅 실패 (계속 진행): {e}")

    # Summary with source info
    print("\n" + "=" * 60)
    print("📊 결과 요약")
    print("=" * 60)
    for draft in drafts:
        status_icon = "✅" if draft.status == "ready_for_review" else "⚠️"
        source_tag = ""
        if draft.paper.topics:
            if "clinical_trial" in draft.paper.topics:
                source_tag = "[임상시험] "
            elif "preprint" in draft.paper.topics:
                source_tag = "[프리프린트] "

        print(f"{status_icon} {source_tag}{draft.korean_title}")
        print(f"   신뢰도: {draft.confidence_score:.0%} | 상태: {draft.status}")
        print(f"   출처: {draft.paper.journal}")

    return drafts


async def demo_multi_source():
    """Demo: Test multi-source paper discovery without content generation"""
    print("=" * 60)
    print("🔬 멀티소스 논문 검색 데모")
    print("=" * 60)

    discovery = PaperDiscovery()

    # Search specific topic across all sources
    query = "NAD+ longevity"
    print(f"\n🔍 검색어: {query}")

    results = await discovery.search_all_sources(
        query=query,
        max_per_source=5,
        days_back=30,
        include_trials=True
    )

    print(f"\n📊 검색 결과:")
    for source, items in results.items():
        print(f"\n--- {source.upper()} ({len(items)}개) ---")
        for item in items[:3]:  # Show top 3 per source
            if hasattr(item, 'title'):
                print(f"  • {item.title[:70]}...")
            elif hasattr(item, 'nct_id'):
                print(f"  • [{item.nct_id}] {item.title[:60]}...")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        asyncio.run(demo_multi_source())
    else:
        asyncio.run(main())
