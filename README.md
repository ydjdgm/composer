# composer

AI-native music production environment where generation remains editable.

현재 단계: **Phase 1 구현 완료 — 사용자 런타임 확인 대기**.

SvelteKit 화면과 FastAPI API, PostgreSQL 영속 큐, 별도 worker를 연결했습니다. 프로젝트 생성, 복수 참조 오디오 업로드·검증, 가중치 저장, 모의 생성, 작업 취소·상태 조회, SongPackage revision 보존을 제공합니다. 실제 음악 분석·작곡·오디오·가창 생성은 하지 않습니다. fake 결과는 고정된 구조 예시이며 사용자 prompt/목표 길이를 실제 생성한 결과가 아닙니다.

개발 기준은 루트의 `PLAN.md`입니다. 사용자가 설정한 `.gitignore`는 README를 제외한 모든 `.md`를 추적에서 제외합니다. 해당 규칙을 유지했으므로 새 checkout에서는 PLAN과 docs를 별도로 제공해야 합니다.

## 로컬 실행

Python 3.12+, Node 22.12+, PostgreSQL 16+, FFmpeg/ffprobe가 필요합니다. [설정·실행 명령과 수동 확인 절차](docs/DEVELOPMENT.md)를 따르세요. API와 worker는 같은 DB 및 asset 경로를 사용해야 합니다.

의존성 설치·migration·서버·테스트·빌드는 실행하지 않았습니다. 직접 의존성 버전은 고정했으나 전체 전이 의존성 lockfile과 실행 호환성은 아직 확인되지 않았습니다. localhost 단일 사용자 개발용이며 외부 공개용 인증은 포함하지 않습니다.

## 문서

- [아키텍처 및 기술 결정](docs/ARCHITECTURE.md)
- [SongPackage와 도메인 모델](docs/SONG_PACKAGE.md)
- [AI 제공자 계약](docs/AI_PROVIDERS.md)
- [API 제안](docs/API.md)
- [개발 환경 및 작업 규칙](docs/DEVELOPMENT.md)
- [단계별 로드맵과 기술 위험](docs/ROADMAP.md)
