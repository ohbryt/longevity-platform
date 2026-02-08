#!/usr/bin/env python3
"""
Quick Start - 빠른 시작 가이드
Test the content pipeline with a sample paper
"""

import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Check API keys
def check_setup():
    print("🔧 환경 설정 확인...\n")

    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    kimi_key = os.getenv("KIMI_API_KEY")

    issues = []
    available_providers = []

    if gemini_key:
        print("✅ GEMINI_API_KEY 설정됨")
        available_providers.append("gemini")
    else:
        print("⚠️ GEMINI_API_KEY 미설정")

    if openai_key:
        print("✅ OPENAI_API_KEY 설정됨 (비용 높음)")
        available_providers.append("openai")
    else:
        print("⚠️ OPENAI_API_KEY 미설정")

    if kimi_key:
        print("✅ KIMI_API_KEY 설정됨 (저렴한 대안 - 추천!)")
        available_providers.append("kimi")
    else:
        print("⚠️ KIMI_API_KEY 미설정 - https://platform.moonshot.cn/ 에서 발급")

    if not available_providers:
        issues.append("❌ 최소 1개의 API 키가 필요합니다.")

    print(f"\n📊 비용 비교:")
    print("   | Provider | Input/1M | Output/1M | 특징")
    print("   |----------|----------|-----------|------")
    print("   | Kimi     | $0.45    | $2.50     | 저렴, 한국어 양호 (추천)")
    print("   | Gemini   | $1.25    | $5.00     | 중간 비용, 긴 컨텍스트")
    print("   | OpenAI   | $2.50    | $10.00    | 고비용, 최고 품질")

    return len(available_providers) > 0, available_providers


async def test_paper_discovery():
    """Test multi-source paper discovery"""
    print("\n📚 멀티소스 논문 검색 테스트...")

    from content_pipeline import PaperDiscovery

    discovery = PaperDiscovery()

    # Test all sources
    print("\n   🔍 Searching: PubMed + bioRxiv + medRxiv + ClinicalTrials.gov")
    results = await discovery.search_all_sources(
        query="NAD+ longevity",
        max_per_source=3,
        days_back=30,
        include_trials=True
    )

    total = sum(len(v) for v in results.values())
    print(f"\n   📊 검색 결과:")
    print(f"      • PubMed: {len(results['pubmed'])}개")
    print(f"      • bioRxiv: {len(results['biorxiv'])}개")
    print(f"      • medRxiv: {len(results['medrxiv'])}개")
    print(f"      • ClinicalTrials: {len(results['clinical_trials'])}개")
    print(f"      총: {total}개\n")

    # Get best paper for content test
    if results['pubmed']:
        paper = results['pubmed'][0]
        print(f"   ✅ 테스트용 논문 선택:")
        print(f"      제목: {paper.title[:60]}...")
        print(f"      저널: {paper.journal}")
        return paper
    elif results['biorxiv']:
        paper = results['biorxiv'][0]
        print(f"   ✅ 테스트용 프리프린트 선택:")
        print(f"      제목: {paper.title[:60]}...")
        return paper
    else:
        print("   ⚠️ 논문을 찾지 못했습니다.")
        return None


async def test_content_generation(paper, provider="gemini"):
    """Test content generation with specified provider"""
    print(f"\n✍️ 콘텐츠 생성 테스트 (provider: {provider})...")

    from content_pipeline import ContentGenerator

    generator = ContentGenerator(provider=provider)
    draft = await generator.generate_content(paper, content_type="newsletter")

    if draft and draft.korean_body:
        print(f"   ✅ 콘텐츠 생성 완료\n")
        print("=" * 60)
        print(f"📰 {draft.korean_title}")
        print("=" * 60)
        print(f"\n{draft.korean_body[:500]}...\n")
        print("=" * 60)
        print(f"\n💡 핵심 인사이트:")
        for insight in draft.key_insights:
            print(f"   • {insight}")
        print(f"\n🎯 실용적 적용:")
        for app in draft.practical_applications:
            print(f"   • {app}")
        print(f"\n신뢰도 점수: {draft.confidence_score:.0%}")
        return draft
    else:
        print("   ❌ 콘텐츠 생성 실패")
        return None


async def test_fact_check(draft, provider="openai"):
    """Test fact checking with specified provider"""
    kimi_key = os.getenv("KIMI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    # Determine which provider to use for fact-checking
    if provider == "kimi" and kimi_key:
        fc_provider = "kimi"
    elif openai_key:
        fc_provider = "openai"
    elif kimi_key:
        fc_provider = "kimi"
    else:
        print("\n⏭️ 팩트체크 테스트 건너뜀 (API 키 없음)")
        return

    print(f"\n🔍 팩트체크 테스트 (provider: {fc_provider})...")

    from content_pipeline import FactChecker

    checker = FactChecker(provider=fc_provider)
    result = await checker.check(draft)

    print(f"   정확도 점수: {result.get('accuracy_score', 0):.0%}")
    print(f"   발행 가능: {'✅ 예' if result.get('safe_to_publish') else '❌ 아니오'}")

    if result.get('issues'):
        print(f"   주의 사항:")
        for issue in result['issues']:
            print(f"      • {issue}")


async def main():
    print("=" * 60)
    print("🧬 장수 지식 플랫폼 - 빠른 시작 테스트")
    print("=" * 60)
    print(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Check setup
    has_provider, available_providers = check_setup()
    if not has_provider:
        print("\n⚠️ 환경 설정을 완료한 후 다시 실행하세요.")
        return

    # Select best provider (prefer kimi for cost efficiency)
    if "kimi" in available_providers:
        provider = "kimi"
        print(f"\n💰 Kimi 사용 (저렴한 대안)")
    elif "gemini" in available_providers:
        provider = "gemini"
        print(f"\n🤖 Gemini 사용")
    else:
        provider = "openai"
        print(f"\n🧠 OpenAI 사용")

    # Test paper discovery
    paper = await test_paper_discovery()
    if not paper:
        return

    # Test content generation
    draft = await test_content_generation(paper, provider=provider)
    if not draft:
        return

    # Test fact check
    await test_fact_check(draft, provider=provider)

    print("\n" + "=" * 60)
    print("✅ 모든 테스트 완료!")
    print("=" * 60)
    print("""
다음 단계:
1. content_pipeline.py의 run_weekly_pipeline() 실행
2. Make.com 또는 n8n으로 주간 자동화 설정
3. 생성된 콘텐츠를 검토 후 발행

도움이 필요하시면 README.md를 참고하세요.
""")


if __name__ == "__main__":
    asyncio.run(main())
