"""
Configuration for Content Pipeline
환경 설정
"""

import os
from dataclasses import dataclass
from typing import List


@dataclass
class PipelineConfig:
    """Pipeline configuration"""

    # API Keys (set via environment variables)
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # AI Provider preference
    primary_ai: str = "gemini"  # "gemini" or "openai"
    fact_checker_ai: str = "openai"  # Always use GPT-4 for fact-checking

    # Content settings
    default_language: str = "korean"
    max_content_length: int = 1200  # characters for blog
    newsletter_length: int = 600  # characters for newsletter

    # Paper discovery
    papers_per_week: int = 5
    relevance_threshold: float = 2.0
    days_lookback: int = 7

    # Keywords for paper discovery
    longevity_keywords: List[str] = None

    # Relevant journals (higher priority)
    target_journals: List[str] = None

    # Output settings
    output_dir: str = "content_drafts"
    save_format: str = "json"  # "json" or "markdown"

    def __post_init__(self):
        if self.longevity_keywords is None:
            self.longevity_keywords = [
                # Core longevity topics
                "NAD+ metabolism aging",
                "senolytics senescent cells",
                "mitochondrial dysfunction aging",
                "autophagy longevity",
                "epigenetic clock biological age",
                "telomere attrition aging",
                # Interventions
                "rapamycin longevity",
                "metformin aging",
                "nicotinamide riboside NR",
                "nicotinamide mononucleotide NMN",
                "GLP-1 agonist metabolic",
                "fasting longevity",
                # Metabolic disease
                "metabolic syndrome intervention",
                "insulin resistance aging",
                "obesity inflammation aging",
            ]

        if self.target_journals is None:
            self.target_journals = [
                "Nature Aging",
                "Cell Metabolism",
                "Aging Cell",
                "GeroScience",
                "Lancet Healthy Longevity",
                "Nature Medicine",
                "Cell",
                "Nature",
                "Science",
                "JAMA",
                "New England Journal of Medicine",
            ]


@dataclass
class ProfessorProfile:
    """Professor's voice and style for content generation"""

    name: str = "브라운바이오텍"
    title: str = "장수과학 리서치팀"
    institution: str = "Brown Biotech Inc."

    # Writing style
    tone: str = "warm_professional"  # warm_professional, academic, casual
    perspective: str = "clinician_researcher"

    # Content preferences
    include_korean_context: bool = True
    include_practical_tips: bool = True
    cite_korean_studies: bool = True

    # Signature phrases (한국어)
    greeting: str = "안녕하세요, 브라운바이오텍입니다."
    closing: str = "건강한 한 주 보내시기 바랍니다."

    def get_system_prompt(self) -> str:
        """Generate system prompt for AI content generation"""
        return f"""당신은 {self.name} {self.title}의 관점으로 글을 작성하는 AI 어시스턴트입니다.

역할:
- 최신 의학 연구를 대중이 이해하기 쉽게 설명
- 과학적 정확성을 유지하면서도 따뜻하고 공감적인 톤 유지
- 실용적인 건강 인사이트 제공
- 한국인 독자에게 맞춤화된 정보 제공

글쓰기 스타일:
- 전문 용어는 쉬운 설명과 함께 사용 (영어 원문 병기)
- 독자와 대화하듯 친근하게 (존댓말 사용)
- 핵심 메시지를 명확하게
- 희망적이고 긍정적인 톤 유지

시작 인사: "{self.greeting}"
마무리 인사: "{self.closing}"

주의사항:
- 의료적 조언은 "~할 수 있습니다", "~라고 합니다" 형식으로
- 출처를 명확히 밝히기
- 과장하거나 확정적인 표현 자제
- 개인 의료 조언 금지 ("의사와 상담하세요" 권고)
"""


# Default configurations
DEFAULT_CONFIG = PipelineConfig()
PROFESSOR_PROFILE = ProfessorProfile()
