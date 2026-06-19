from pathlib import Path

from apps.api.core.container import get_container
from apps.api.domain.models import Classification, Document


def main() -> None:
    container = get_container()
    sample_dir = Path("data/sample_docs")

    for path in sorted(sample_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        title = content.splitlines()[0].removeprefix("# ").strip()
        document = Document(
            tenant_id="default",
            title=title,
            content=content,
            source_type="manual",
            source_uri=str(path),
            classification=Classification.INTERNAL,
            metadata={"domain": "enterprise-ax", "language": "ko"},
        )
        saved, chunk_count = container.ingest_document.execute(
            document=document,
            actor_id="seed-script",
        )
        print(f"ingested: {saved.title} ({chunk_count} chunks)")


if __name__ == "__main__":
    main()
