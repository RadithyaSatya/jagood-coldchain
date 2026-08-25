import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_DEFAULT_KNOWLEDGE_DIRECTORY = Path(__file__).resolve().parents[3] / "knowledge"
_STOP_WORDS = {
    "apa",
    "apakah",
    "bagaimana",
    "buat",
    "dan",
    "dari",
    "di",
    "dengan",
    "does",
    "how",
    "itu",
    "ke",
    "mengenai",
    "of",
    "pada",
    "saja",
    "saya",
    "tentang",
    "the",
    "untuk",
    "what",
    "yang",
}
_SYNONYMS = {
    "fungsi": {"fitur", "kegunaan", "kemampuan"},
    "fitur": {"fungsi", "kegunaan", "kemampuan"},
    "kirim": {"pengiriman", "distribusi", "transportasi"},
    "pengiriman": {"kirim", "distribusi", "transportasi"},
    "pantau": {"pemantauan", "monitoring", "memantau"},
    "monitoring": {"pantau", "pemantauan", "memantau"},
    "simulasi": {"skenario", "scenario", "simulator"},
    "skenario": {"simulasi", "scenario", "simulator"},
    "jalur": {"rute", "route"},
    "rute": {"jalur", "route"},
}


@dataclass(frozen=True)
class KnowledgeChunk:
    source: str
    heading: str
    content: str
    score: int = 0

    @property
    def citation(self) -> str:
        return f"{self.source}#{_slugify(self.heading)}"


def retrieve_knowledge(query: str, *, limit: int = 3) -> list[KnowledgeChunk]:
    query_tokens = _expanded_tokens(query)
    if not query_tokens:
        return []

    ranked: list[KnowledgeChunk] = []
    for chunk in _load_chunks(_knowledge_directory()):
        heading_tokens = _expanded_tokens(chunk.heading)
        content_tokens = _expanded_tokens(chunk.content)
        heading_overlap = len(query_tokens & heading_tokens)
        content_overlap = len(query_tokens & content_tokens)
        score = heading_overlap * 3 + content_overlap
        if score > 0:
            ranked.append(
                KnowledgeChunk(
                    source=chunk.source,
                    heading=chunk.heading,
                    content=chunk.content,
                    score=score,
                )
            )

    ranked.sort(key=lambda item: (-item.score, item.source, item.heading))
    return ranked[:limit]


def format_knowledge_context(chunks: list[KnowledgeChunk]) -> list[dict[str, str]]:
    return [
        {"source": chunk.citation, "content": chunk.content}
        for chunk in chunks
    ]


def _knowledge_directory() -> Path:
    configured_directory = os.getenv("AI_EXPLAIN_KNOWLEDGE_DIR")
    if configured_directory:
        return Path(configured_directory).resolve()
    return _DEFAULT_KNOWLEDGE_DIRECTORY


@lru_cache(maxsize=4)
def _load_chunks(directory: Path) -> list[KnowledgeChunk]:
    if not directory.is_dir():
        return []
    resources = sorted(directory.glob("*.md"))
    return _read_markdown_resources(resources)


def _read_markdown_resources(resources: list[object]) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    for resource in resources:
        name = resource.name
        content = resource.read_text(encoding="utf-8")
        chunks.extend(_parse_markdown(name, content))
    return chunks


def _parse_markdown(source: str, content: str) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    heading = source.removesuffix(".md").replace("-", " ").title()
    body: list[str] = []

    def append_chunk() -> None:
        text = "\n".join(body).strip()
        if text:
            chunks.append(KnowledgeChunk(source=source, heading=heading, content=text))

    for line in content.splitlines():
        if line.startswith("#"):
            append_chunk()
            heading = line.lstrip("#").strip()
            body = []
        else:
            body.append(line)
    append_chunk()
    return chunks


def _expanded_tokens(value: str) -> set[str]:
    tokens = {
        token
        for token in _TOKEN_PATTERN.findall(value.casefold())
        if token not in _STOP_WORDS
    }
    expanded = set(tokens)
    for token in tokens:
        expanded.update(_SYNONYMS.get(token, set()))
    return expanded


def _slugify(value: str) -> str:
    return "-".join(_TOKEN_PATTERN.findall(value.casefold()))
