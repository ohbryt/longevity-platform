#!/usr/bin/env python3
"""Regenerate failed content drafts (요약 생성 실패)"""
import os
import json
import asyncio
from dotenv import load_dotenv

load_dotenv()

from content_pipeline import ContentGenerator, FactChecker, Paper, parse_json_response

async def main():
    drafts_dir = os.path.join(os.path.dirname(__file__), "content_drafts")

    # Find failed files
    failed_files = []
    for fname in sorted(os.listdir(drafts_dir)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(drafts_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("korean_summary") == "요약 생성 실패":
            failed_files.append((fname, fpath, data))

    if not failed_files:
        print("✅ 실패한 파일이 없습니다.")
        return

    print(f"🔄 재생성 대상: {len(failed_files)}개 파일\n")

    # Use gemini for both content and fact-check
    generator = ContentGenerator(provider="gemini")
    fact_checker = FactChecker(provider="gemini")

    for i, (fname, fpath, data) in enumerate(failed_files, 1):
        paper_data = data["paper"]
        paper = Paper(
            title=paper_data["title"],
            authors=paper_data.get("authors", []),
            abstract=paper_data.get("abstract", ""),
            journal=paper_data.get("journal", ""),
            doi=paper_data.get("doi", ""),
            pub_date=paper_data.get("pub_date", ""),
            url=paper_data.get("url", ""),
            topics=paper_data.get("topics", []),
            relevance_score=paper_data.get("relevance_score", 0.0),
        )

        print(f"📝 [{i}/{len(failed_files)}] {paper.title[:60]}...")

        # Generate content
        draft = await generator.generate_content(paper, content_type="newsletter")

        if draft.korean_summary == "요약 생성 실패":
            print(f"   ❌ 여전히 실패: {draft.korean_body[:80]}")
        else:
            print(f"   ✓ 콘텐츠 생성 완료")

            # Fact check
            print(f"   ✓ 팩트체크 중...")
            fact_result = await fact_checker.check(draft)
            draft.fact_check_notes = fact_result.get("issues", [])

            if fact_result.get("safe_to_publish", False):
                draft.status = "ready_for_review"
                print(f"   ✅ 완료 (정확도: {fact_result.get('accuracy_score', 0):.0%})")
            else:
                draft.status = "needs_revision"
                print(f"   ⚠️ 수정 필요")

            # Update the JSON file
            data["korean_title"] = draft.korean_title
            data["korean_summary"] = draft.korean_summary
            data["korean_body"] = draft.korean_body
            data["key_insights"] = draft.key_insights
            data["practical_applications"] = draft.practical_applications
            data["confidence_score"] = draft.confidence_score
            data["fact_check_notes"] = draft.fact_check_notes
            data["status"] = draft.status

            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"   💾 저장 완료: {fname}")

        # Rate limit delay
        if i < len(failed_files):
            print(f"   ⏳ 10초 대기...")
            await asyncio.sleep(10)

    print(f"\n✅ 재생성 완료!")

if __name__ == "__main__":
    asyncio.run(main())
