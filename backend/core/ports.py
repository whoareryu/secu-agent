"""경계 인터페이스.

안쪽 계층이 인터페이스를 소유하고 바깥 계층이 구현한다. 그래야 의존성이
항상 안쪽을 향한다 — adapters/ 는 core 를 알지만 core 는 psycopg 도,
sentence-transformers 도, LangChain 도 모른다.

여기 선언된 Protocol 은 전부 최소 두 구현을 갖는다: 실제 어댑터와 테스트
스텁. 한 번만 쓰는 추상화가 아니다.

@runtime_checkable 은 테스트가 스텁의 포트 만족을 확인하기 위해서다.
isinstance 는 메서드 존재만 보고 시그니처는 보지 않는다 — 시그니처는
실제 호출로 검증한다.
"""

from collections.abc import Sequence
from typing import Literal, Protocol, runtime_checkable

from core.types import Chunk, Clause, Document, PolicyHit, Principal

Vector = list[float]


@runtime_checkable
class Embedder(Protocol):
    def encode(self, texts: Sequence[str], kind: Literal["query", "passage"]) -> list[Vector]:
        """e5 계열은 query/passage 접두어를 요구한다 — 그 사실을 포트가 드러낸다.

        접두어를 빼면 검색 품질이 조용히 나빠진다. 시그니처로 강제한다.
        """
        ...


@runtime_checkable
class DocumentStore(Protocol):
    def upsert_document(self, doc: Document) -> int:
        """문서를 저장하고 id 를 돌려준다. 같은 source_path 는 갱신한다."""
        ...

    def insert_clauses(self, document_id: int, clauses: Sequence[Clause]) -> dict[str, int]:
        """조항을 저장하고 code -> id 를 돌려준다."""
        ...

    def insert_chunks(
        self,
        document_id: int,
        clause_ids: dict[str, int],
        chunks: Sequence[Chunk],
        vectors: Sequence[Vector],
    ) -> int:
        """청크와 벡터를 저장하고 저장한 개수를 돌려준다."""
        ...

    def delete_chunks(self, document_id: int) -> int:
        """문서의 청크를 전부 지우고 지운 개수를 돌려준다.

        재적재를 멱등하게 만드는 유일한 수단이다. UNIQUE (document_id,
        clause_id, ordinal) 제약으로는 안 된다 — clause_id 가 NULL 인
        청크(조항 밖 텍스트)는 SQL 에서 NULL 끼리 서로 다르다고 보므로
        제약이 아예 걸리지 않는다.
        """
        ...

    def count_all_chunks(self) -> int:
        """권한과 무관하게 코퍼스 전체 청크 수를 센다. 요청을 처리하는 경로에서
        호출하면 안 된다 — 존재 여부를 우회하는 채널이 된다. 적재 직후
        운영자에게 확인시키는 용도로만 쓴다(pipeline/cli.py 의 ingest)."""
        ...


@runtime_checkable
class ChunkSearch(Protocol):
    def by_vector(self, vec: Vector, principal: Principal, k: int) -> list[int]:
        """코사인 유사도 상위 k 개 chunk id.

        principal 이 필수 인자인 것이 중요하다 — 권한 없는 검색을 호출하는
        방법이 없다(spec 5.3). W1 에서는 필터가 아직 통과만 시키지만,
        시그니처는 처음부터 갖춘다. 나중에 끼워 넣으면 빠뜨린 경로가 생긴다.
        """
        ...

    def by_keyword(self, query: str, principal: Principal, k: int) -> list[int]: ...

    def load_hits(self, ids: Sequence[int], principal: Principal) -> list[PolicyHit]:
        """chunk id → PolicyHit. 권한 밖 id 는 조용히 빠진다.

        principal 이 필수인 이유: 이 메서드는 본문을 돌려준다. 권한 검사를
        검색 쪽에만 두면 id 를 아는 호출자가 이 경로로 본문을 가져간다.
        """
        ...
