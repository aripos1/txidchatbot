# 프로젝트 구조 개선 제안 분석

## 현재 구조

```
multi_chain_tx_lookup/
├── main.py                    # 메인 애플리케이션
├── chatbot/                   # 챗봇 모듈
├── src/                       # 서비스 모듈
├── templates/                 # 템플릿
├── static/                    # 정적 파일
├── scripts/                   # 스크립트
├── airflow/                   # Airflow 설정
├── docker-compose.yml         # 메인 애플리케이션 Docker
├── requirements.txt
└── ...
```

## 제안된 구조

```
multi_chain_tx_lookup/
├── app/                       # 애플리케이션 코드 (완전 독립)
│   ├── main.py
│   ├── chatbot/
│   ├── src/
│   ├── templates/
│   ├── static/
│   ├── scripts/               # 애플리케이션 스크립트
│   ├── docker-compose.yml     # 애플리케이션 Docker 설정
│   ├── requirements.txt       # 애플리케이션 의존성
│   └── ...
├── airflow/                   # Airflow 설정 (완전 독립)
│   ├── dags/
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── ...
└── ...
```

## 장단점 분석

### ✅ 장점

1. **구조적 명확성**
   - `app/`과 `airflow/`의 역할이 명확히 구분됨
   - 프로젝트 루트가 더 깔끔해짐
   - 각 컴포넌트의 경계가 명확해짐

2. **Docker 실행 관점**
   - `app/` 폴더만 마운트/빌드 가능
   - Airflow와 애플리케이션의 분리가 명확함
   - 각각 독립적으로 관리 가능

3. **확장성**
   - 향후 다른 서비스 추가 시 구조가 명확함
   - 예: `app/`, `airflow/`, `admin/`, `api/` 등

4. **관리 편의성**
   - 코드베이스 관점에서 역할 분리
   - 각 컴포넌트별 독립적 관리 가능

### ⚠️ 단점

1. **대규모 리팩토링 필요**
   - 모든 import 경로 수정
   - Docker 설정 파일 수정
   - 경로 참조 수정 (templates, static 등)

2. **Airflow 마운트 경로 변경**
   - 현재: `../:/opt/airflow/project` (프로젝트 루트 마운트)
   - 변경 후: `../app:/opt/airflow/project` (app 폴더만 마운트)
   - Airflow DAG가 `scripts/data/crawl_bithumb.py`를 사용하므로 경로는 그대로 (`app/scripts/` 아래)

## 리팩토링 영향 범위

### 1. 파일 이동
- `main.py` → `app/main.py`
- `chatbot/` → `app/chatbot/`
- `src/` → `app/src/`
- `templates/` → `app/templates/`
- `static/` → `app/static/`
- `scripts/` → `app/scripts/`
- `docker-compose.yml` → `app/docker-compose.yml`
- `requirements.txt` → `app/requirements.txt`
- `docker/` → `app/docker/` (선택적)

### 2. Import 경로 수정
- `from chatbot import ...` → `from app.chatbot import ...`
- `from src.services import ...` → `from app.src.services import ...`
- 상대 import는 그대로 유지 가능

### 3. Docker 설정 수정
- `app/docker/Dockerfile.prod`: `COPY . .` (app 폴더 내에서 빌드)
- `app/docker-compose.yml`: 경로 수정 (app 폴더 기준)
- 작업 디렉토리: `app/` 디렉토리 기준

### 4. FastAPI 설정 수정
- `Jinja2Templates(directory="templates")` → `Jinja2Templates(directory="app/templates")`
- `StaticFiles(directory="static")` → `StaticFiles(directory="app/static")`
- 또는 절대 경로 사용

### 5. Airflow 설정 수정
- 현재: `../:/opt/airflow/project` (프로젝트 루트 마운트)
- 변경 후: `../app:/opt/airflow/project` (app 폴더만 마운트)
- DAG에서 `from scripts.data.crawl_bithumb import main` 사용 (app/scripts/ 아래)
- `airflow/entrypoint.sh`: `requirements.txt` 경로를 `/opt/airflow/project/requirements.txt`로 변경

## 최종 권장 구조

**구조**:
```
multi_chain_tx_lookup/
├── app/                       # 애플리케이션 코드 (완전 독립)
│   ├── main.py
│   ├── chatbot/
│   ├── src/
│   ├── templates/
│   ├── static/
│   ├── scripts/               # 애플리케이션 스크립트
│   ├── docker/                # 애플리케이션 Docker 설정
│   ├── docker-compose.yml     # 애플리케이션 Docker Compose
│   ├── requirements.txt       # 애플리케이션 의존성
│   └── ...
├── airflow/                   # Airflow 설정 (완전 독립)
│   ├── dags/
│   ├── config/
│   ├── docker-compose.yml     # Airflow Docker Compose
│   ├── Dockerfile
│   └── ...
└── README.md                  # 프로젝트 루트 문서
```

**특징**:
- ✅ 완전 분리: `app/`와 `airflow/`가 완전히 독립적
- ✅ 명확한 경계: 각 컴포넌트가 자체 의존성과 설정 관리
- ✅ 독립 실행: 각각 별도의 Docker Compose로 실행
- ✅ 확장성: 향후 다른 서비스 추가 시 동일한 패턴 적용 가능

## 결론

**구조 개선은 좋은 아이디어입니다.** 하지만 **대규모 리팩토링**이 필요하므로:

1. **현재 단계**: 프로젝트가 안정화된 후 진행 권장
2. **점진적 접근**: 필요 시 단계적으로 진행
3. **테스트 중요**: 리팩토링 후 전체 기능 테스트 필수

**최종 권장사항**: 
- 구조 개선은 **장기적으로 좋은 선택** (완전 분리 구조)
- **즉시 필요하지 않다면** 현재 구조 유지도 가능
- **리팩토링을 진행한다면** 완전 분리 구조 권장:
  - `app/`: 애플리케이션 관련 모든 것
  - `airflow/`: Airflow 관련 모든 것
  - 각각 독립적으로 관리 및 실행
