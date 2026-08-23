# AI 없이 만드는 자동 작업일지 Notion 업로드 구현 계획

## 목표

두 개의 독립 프로젝트를 만든다.

1. Python Desktop Worklog
   - Desktop에 있는 파일, Git 커밋, 문서/엑셀/CSV 변경 흔적을 정리해서 Notion API로 보낸다.

2. Browser Worklog Extension
   - 브라우저에서 한 작업을 확장 프로그램으로 수집하고 정리해서 Notion API로 보낸다.

두 프로젝트는 GitHub에 각각 공개해서 원하는 사용자가 선택적으로 사용할 수 있게 한다.

이 문서의 앞부분은 `Python Desktop Worklog` 구현 계획을 중심으로 작성한다. 브라우저 확장 프로그램은 별도 섹션에서 독립 프로젝트로 정리한다.

Python Desktop Worklog는 매일 지정한 시간에 로컬 작업 폴더를 검사해서 오늘 수정한 파일, Git 커밋 내역, Git 변경 상태, 텍스트/엑셀/CSV 파일의 기본 정보를 수집하고 Notion API로 일일 작업일지를 생성한다.

AI 요약은 사용하지 않는다. 대신 규칙 기반으로 파일 메타데이터, 변경 감지, 통계를 정리한다.

Notion에는 파일 자체나 원문 내용을 올리지 않는다. 로컬에서 분석한 결과를 바탕으로 `한 일`을 추정할 수 있는 요약 정보만 업로드한다.

## 프로젝트 분리 원칙

두 프로젝트는 서로 의존하지 않는다.

### Python Desktop Worklog

담당:

- Desktop 파일 변경 감지
- Git 저장소 분석
- txt/md/csv/xlsx 구조 분석
- 스냅샷 비교
- Windows 작업 스케줄러 등록
- Notion Database에 작업일지 생성

수집하지 않는 것:

- 브라우저 입력 내용
- 웹페이지 내부 본문
- 브라우저 확장 이벤트

### Browser Worklog Extension

담당:

- 브라우저 탭 활동 감지
- 페이지 제목/도메인/URL 패턴 분석
- 사용자가 입력한 작업 흔적 분석
- 웹앱별 작업 힌트 추출
- Notion Database에 브라우저 작업일지 생성

수집하지 않는 것:

- Desktop 파일 변경
- Git 상태
- 로컬 Excel/문서 파일 내용

### Notion 통합 방식

두 프로젝트는 같은 Notion Database를 사용할 수도 있고, 별도 Database를 사용할 수도 있다.

권장:

- 처음에는 별도 Database로 개발한다.
- 안정화 후 같은 Daily Worklog Database에 합치는 옵션을 제공한다.

공통 필드:

| 속성명 | 타입 | 설명 |
| --- | --- | --- |
| Name | Title | 작업일지 제목 |
| Date | Date | 작업 날짜 |
| Source | Select | Desktop, Browser |
| Project | Text | 프로젝트/작업 영역 |
| Status | Select | Success, Partial, Failed |

## 핵심 기능

### 1. 오늘 작업 파일 수집

지정한 루트 폴더 아래에서 오늘 수정된 파일을 찾는다.

수집 기준:

- 마지막 수정 시간이 오늘인 파일
- 제외 폴더에 포함되지 않은 파일
- 제외 확장자에 포함되지 않은 파일
- 파일 크기가 설정한 최대 크기 이하인 파일

기본 제외 대상:

- `.git`
- `node_modules`
- `.venv`
- `venv`
- `dist`
- `build`
- `.next`
- `.cache`
- `__pycache__`
- `.idea`
- `.vscode`

기본 제외 확장자:

- 이미지: `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.ico`
- 바이너리/압축: `.zip`, `.7z`, `.rar`, `.exe`, `.dll`
- 로그/임시: `.log`, `.tmp`
- 대용량 잠금 파일: 필요 시 `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`

### 2. Git 정보 수집

Git 저장소인 폴더에서는 다음 정보를 수집한다.

- 현재 브랜치
- 오늘 생성된 커밋 목록
- 커밋 해시
- 커밋 메시지
- 커밋 시간
- 커밋별 변경 파일 수
- 오늘 변경된 파일 목록
- 아직 커밋하지 않은 변경사항
- `git diff --stat`

권장 명령:

```bash
git rev-parse --is-inside-work-tree
git branch --show-current
git log --since="00:00" --pretty=format:"%h|%ad|%s" --date=iso
git status --short
git diff --stat
git diff --cached --stat
```

주의:

- `git diff` 원문 전체는 저장하지 않는다.
- 비밀키나 개인정보가 Notion으로 올라갈 수 있으므로 기본은 `--stat` 중심으로 기록한다.
- 필요할 경우 특정 확장자 파일만 diff 일부를 별도 추출한다.

### 3. 파일 타입별 분석

#### 공통 메타데이터

모든 파일에 대해 다음 값을 수집한다.

- 파일 경로
- 파일명
- 확장자
- 파일 크기
- 마지막 수정 시간
- SHA-256 해시

#### 텍스트 파일

대상:

- `.txt`
- `.md`
- `.json`
- `.yaml`
- `.yml`
- `.js`
- `.ts`
- `.tsx`
- `.jsx`
- `.py`
- `.html`
- `.css`

수집 정보:

- 라인 수
- 글자 수
- 제목 후보
- 주요 키워드 후보
- 첫 20줄 로컬 미리보기
- 너무 긴 줄은 잘라서 저장

제한:

- 파일 전체나 미리보기 원문은 Notion에 업로드하지 않는다.
- 미리보기는 로컬 분석과 디버깅 용도로만 사용한다.
- 기본 최대 읽기 크기는 200KB로 제한한다.

#### CSV 파일

수집 정보:

- 컬럼명
- 행 수
- 열 수
- 첫 5행 로컬 미리보기
- 컬럼명 기반 작업 키워드 후보

주의:

- 인코딩은 `utf-8-sig` 우선, 실패하면 `cp949`를 시도한다.
- 개인정보가 있을 수 있으므로 전체 데이터와 행 미리보기 원문은 업로드하지 않는다.

#### Excel 파일

대상:

- `.xlsx`
- `.xlsm`

수집 정보:

- 시트 이름 목록
- 시트별 행 수
- 시트별 열 수
- 시트별 헤더 추정
- 시트별 첫 5행 로컬 미리보기
- 시트명과 헤더 기반 작업 키워드 후보

구현 라이브러리:

- Python: `openpyxl`
- Node.js: `xlsx`

권장:

- 수식 계산 결과는 Excel 앱 없이 정확하지 않을 수 있으므로 값 그대로 읽는다.
- 대형 파일은 시트명과 크기 정보만 기록한다.
- Notion에는 Excel 파일 자체나 셀 데이터 원문을 업로드하지 않는다.

### 4. 스냅샷 저장

AI 없이 변경점을 파악하려면 이전 실행 결과가 필요하다. 매일 실행 후 로컬에 스냅샷을 저장한다.

예시 경로:

```text
.worklog/state/latest_snapshot.json
.worklog/state/2026-08-23.json
```

스냅샷 예시:

```json
{
  "generated_at": "2026-08-23T23:00:00+09:00",
  "root": "%USERPROFILE%/Desktop",
  "files": [
    {
      "path": "docs/report.md",
      "mtime": "2026-08-23T18:20:00+09:00",
      "size": 4021,
      "sha256": "abc123",
      "type": "markdown",
      "line_count": 120
    }
  ]
}
```

비교 방식:

- 새 파일: 이전 스냅샷에 없고 현재 스냅샷에 있음
- 수정 파일: 경로는 같지만 해시가 다름
- 삭제 파일: 이전 스냅샷에는 있고 현재 스냅샷에는 없음
- 이름 변경: 기본 버전에서는 감지하지 않음

### 5. Notion 데이터베이스 설계

Notion에는 날짜별 작업일지 페이지를 만든다.

권장 Database 속성:

| 속성명 | 타입 | 설명 |
| --- | --- | --- |
| Name | Title | 작업일지 제목 |
| Date | Date | 작업 날짜 |
| Project | Text | 프로젝트 이름 |
| Root Path | Text | 수집한 로컬 루트 |
| Commit Count | Number | 오늘 커밋 수 |
| Modified Files | Number | 오늘 수정 파일 수 |
| New Files | Number | 새 파일 수 |
| Status | Select | Success, Partial, Failed |

페이지 본문 구성:

```text
# 오늘 작업 요약

## 한 일
- 규칙 기반으로 생성한 작업 요약
- 많이 수정된 파일 타입
- 많이 변경된 폴더
- Git 커밋 기반 작업 항목
- 문서/엑셀/코드 작업 여부

## Git
- 브랜치
- 오늘 커밋 목록
- 커밋되지 않은 변경사항
- diff stat

## 오늘 수정된 파일
- 파일명
- 경로
- 수정 시간
- 크기
- 파일 타입

## 문서 작업 요약
- 수정된 텍스트/마크다운 파일 수
- 제목 후보
- 키워드 후보
- 라인 수 변화

## CSV/Excel 요약
- 시트명
- 행/열 수
- 헤더
- 행/열 수 변화
- 데이터 파일 작업 여부

## 스냅샷 비교
- 새 파일
- 수정 파일
- 삭제 파일

## 실행 로그
- 실행 시간
- 제외된 파일 수
- 오류 파일 목록
```

Notion 본문에는 파일 원문, 파일 첨부, 텍스트 미리보기, CSV 행 데이터, Excel 셀 데이터 원문을 넣지 않는다. 필요한 경우 로컬 로그에만 제한적으로 남긴다.

### 6. 설정 파일

`.worklog/config.json` 파일로 설정을 관리한다.

Git에 올리는 기본 설정은 특정 사용자의 절대 경로를 포함하지 않는다. Windows 사용자 공통 경로는 `%USERPROFILE%/Desktop` 같은 환경 변수 기반 경로로 작성한다.

예시:

```json
{
  "project_name": "자동 작업일지",
  "root_paths": [
    "%USERPROFILE%/Desktop"
  ],
  "notion": {
    "database_id": "NOTION_DATABASE_ID"
  },
  "scan": {
    "max_file_size_kb": 2048,
    "text_preview_lines": 20,
    "table_preview_rows": 5,
    "exclude_dirs": [
      ".git",
      "node_modules",
      ".venv",
      "venv",
      "dist",
      "build",
      ".next",
      ".cache",
      "__pycache__"
    ],
    "exclude_extensions": [
      ".png",
      ".jpg",
      ".jpeg",
      ".gif",
      ".webp",
      ".ico",
      ".zip",
      ".7z",
      ".rar",
      ".exe",
      ".dll",
      ".log",
      ".tmp"
    ]
  }
}
```

환경 변수:

```text
NOTION_TOKEN=secret_xxx
```

토큰은 코드나 Notion 본문에 저장하지 않는다.

#### 경로 설정 규칙

이 프로젝트는 GitHub에 올려 여러 Windows 사용자가 쓸 수 있게 만들 예정이므로 개인 PC의 절대 경로를 설정 파일에 고정하지 않는다.

권장 경로 표현:

```text
%USERPROFILE%/Desktop
~/Desktop
${USERPROFILE}/Desktop
```

지원할 경로 해석 규칙:

- `%USERPROFILE%`은 현재 Windows 사용자의 홈 폴더로 변환한다.
- `${USERPROFILE}`도 현재 Windows 사용자의 홈 폴더로 변환한다.
- `~`는 현재 사용자 홈 폴더로 변환한다.
- 상대 경로는 프로젝트 루트 기준으로 해석한다.
- 경로 구분자는 `/`와 `\`를 모두 허용한다.

구현 예시:

```python
from pathlib import Path
import os


def expand_config_path(path_value: str) -> Path:
    expanded = os.path.expandvars(path_value)
    expanded = os.path.expanduser(expanded)
    return Path(expanded).resolve()
```

Git에 포함할 파일:

```text
.worklog/config.example.json
```

Git에 포함하지 않을 파일:

```text
.worklog/config.json
.env
```

초기 실행 시 `config.json`이 없으면 `config.example.json`을 복사해서 생성하거나, CLI 명령으로 초기 설정을 만든다.

## 권장 기술 스택

### Python 버전

장점:

- 파일 시스템 검사 구현이 단순함
- Excel 처리에 `openpyxl` 사용 가능
- Windows 작업 스케줄러와 연결하기 쉬움

권장 패키지:

```text
requests
python-dotenv
openpyxl
```

### Node.js 버전

장점:

- Notion SDK 사용이 편함
- JSON 처리와 CLI 구성에 익숙하면 개발 속도가 빠름

권장 패키지:

```text
@notionhq/client
dotenv
xlsx
fast-glob
```

이 프로젝트는 로컬 파일과 Excel 분석이 중요하므로 Python으로 시작하는 것을 권장한다.

## 구현 단계

### 1단계: 로컬 수집기

목표:

- 오늘 수정된 파일 목록을 콘솔에 출력한다.
- 제외 폴더와 제외 확장자를 적용한다.
- 파일 크기 제한을 적용한다.

산출물:

- `worklog.py`
- `.worklog/config.json`

완료 기준:

- 실행하면 오늘 수정된 파일 목록이 표시된다.
- 대형 파일과 제외 폴더가 스캔되지 않는다.

### 2단계: Git 수집기

목표:

- Git 저장소 여부를 판단한다.
- 오늘 커밋 목록과 현재 변경 상태를 수집한다.

산출물:

- `collect_git_info()` 함수

완료 기준:

- Git 저장소에서는 커밋/브랜치/status가 출력된다.
- Git 저장소가 아닌 폴더에서는 오류 없이 건너뛴다.

### 3단계: 파일 타입별 분석기

목표:

- 텍스트, CSV, Excel 파일의 기본 정보를 추출한다.

산출물:

- `analyze_text_file()`
- `analyze_csv_file()`
- `analyze_excel_file()`

완료 기준:

- 파일 타입별 미리보기와 통계가 생성된다.
- 읽기 실패 파일은 전체 실행을 중단하지 않고 오류 목록에 기록된다.

### 4단계: 스냅샷 비교

목표:

- 이전 실행 결과와 현재 결과를 비교한다.

산출물:

- `.worklog/state/latest_snapshot.json`
- 날짜별 스냅샷 JSON
- `compare_snapshots()` 함수

완료 기준:

- 새 파일, 수정 파일, 삭제 파일이 구분된다.
- 첫 실행 시에는 모든 파일을 현재 상태로 저장한다.

### 5단계: Notion 업로드

목표:

- Notion Database에 오늘 작업일지 페이지를 생성한다.

산출물:

- `notion_client.py`
- `create_daily_page()` 함수

완료 기준:

- Notion에 날짜별 페이지가 생성된다.
- 본문에 Git 정보, 수정 파일 목록, 파일 분석 결과가 들어간다.

### 6단계: 자동 실행

목표:

- 매일 지정 시간에 자동 실행되도록 설정한다.

Windows 작업 스케줄러 예시:

```powershell
$Action = New-ScheduledTaskAction -Execute "python" -Argument "C:\path\to\worklog.py"
$Trigger = New-ScheduledTaskTrigger -Daily -At 23:00
Register-ScheduledTask -TaskName "DailyWorklogToNotion" -Action $Action -Trigger $Trigger -Description "Upload daily worklog to Notion"
```

완료 기준:

- 지정 시간에 자동 실행된다.
- 실패 시 로그 파일에 오류가 남는다.

## 폴더 구조

권장 구조:

```text
.
├── worklog.py
├── notion_client.py
├── requirements.txt
├── .env
├── .worklog
│   ├── config.json
│   ├── logs
│   │   └── 2026-08-23.log
│   └── state
│       ├── latest_snapshot.json
│       └── 2026-08-23.json
└── AI없이_자동_작업일지_구현계획.md
```

## 현실적인 한계

- AI가 없으므로 작업 의도나 의미를 자연스럽게 요약하지는 못한다.
- Excel 내부의 실제 셀 변경 위치는 이전 파일 복사본이 없으면 정확히 비교하기 어렵다.
- 문서 파일의 의미 있는 요약보다는 파일 구조, 미리보기, 변경 여부 중심으로 기록된다.
- Notion API block 개수 제한과 요청 제한을 고려해서 긴 내용은 잘라야 한다.
- 비밀번호, 토큰, 개인정보가 포함된 파일은 제외 규칙으로 걸러야 한다.

## 보안 정책

- `.env` 파일은 Git에 커밋하지 않는다.
- Notion 토큰은 환경 변수에서만 읽는다.
- `git diff` 원문 전체는 기본 업로드하지 않는다.
- 대형 파일과 민감한 확장자는 제외한다.
- 업로드 전 제외 키워드를 검사한다.

민감 키워드 예시:

```text
password
passwd
secret
token
api_key
apikey
private_key
client_secret
```

## 첫 버전 최소 구현 범위

첫 버전에서는 아래까지만 구현한다.

- 오늘 수정 파일 목록 수집
- Git 브랜치, 오늘 커밋, status, diff stat 수집
- txt/md/csv/xlsx 기본 분석
- 스냅샷 저장
- Notion 페이지 생성
- 실행 로그 저장

제외할 것:

- AI 요약
- PDF/DOCX 분석
- 셀 단위 Excel 변경 비교
- GUI
- 여러 Notion Database 분기

## 예상 개발 순서

1. `config.json` 로딩
2. 오늘 날짜 계산
3. 파일 스캔
4. 파일 타입별 분석
5. Git 정보 수집
6. 스냅샷 저장과 비교
7. Notion 페이지 본문 생성
8. Notion API 업로드
9. 로그 저장
10. Windows 작업 스케줄러 등록

## 성공 기준

매일 밤 자동 실행 후 Notion에 다음과 같은 페이지가 생기면 성공이다.

```text
2026-08-23 자동 작업일지

- 오늘 커밋 3개
- 수정 파일 12개
- 새 파일 2개
- 미커밋 변경 파일 4개
- Excel 파일 1개 수정
- Markdown 문서 2개 수정
- 오류 없이 업로드 완료
```

## 이후 개선 아이디어

- 프로젝트별 Notion 페이지 분리
- 주간 작업일지 자동 생성
- 특정 폴더만 감시하는 watch 모드
- 파일 변경 이벤트 기반 실시간 스냅샷
- PDF/DOCX 텍스트 추출
- Excel 이전 사본 저장 후 셀 단위 비교
- 원할 때만 OpenAI API로 자연어 요약 추가

## Notion 캘린더 뷰 연동

작업일지는 Notion Database의 `Date` 속성을 기준으로 Calendar view에서 볼 수 있게 만든다.

중요한 점:

- `Date` 속성은 필수로 만든다.
- 자동 업로드 시 매일 생성되는 페이지에 오늘 날짜를 `Date` 속성으로 넣는다.
- Notion Database 안에서 Table view와 Calendar view를 함께 만든다.
- 캘린더 카드 제목은 날짜와 프로젝트명이 바로 보이게 구성한다.

권장 뷰:

| View 이름 | View 타입 | 용도 |
| --- | --- | --- |
| All Logs | Table | 전체 작업일지 목록 확인 |
| Calendar | Calendar | 날짜별 작업 기록 확인 |
| By Status | Board | 성공/실패/부분 성공 상태 확인 |
| By Project | Table | 프로젝트별 필터링 |

캘린더 카드 제목 예시:

```text
2026-08-23 자동 작업일지
2026-08-23 notion-api-worklog
```

Notion API로 페이지를 만들 때 넣을 속성 예시:

```json
{
  "Name": {
    "title": [
      {
        "text": {
          "content": "2026-08-23 자동 작업일지"
        }
      }
    ]
  },
  "Date": {
    "date": {
      "start": "2026-08-23"
    }
  },
  "Project": {
    "rich_text": [
      {
        "text": {
          "content": "자동 작업일지"
        }
      }
    ]
  },
  "Commit Count": {
    "number": 3
  },
  "Modified Files": {
    "number": 12
  },
  "Status": {
    "select": {
      "name": "Success"
    }
  }
}
```

구현 시 주의:

- `Date` 값은 로컬 시간대 기준 오늘 날짜를 사용한다.
- 이 프로젝트의 기본 시간대는 `Asia/Seoul`로 둔다.
- 하루에 여러 번 실행될 수 있으므로 같은 날짜의 페이지가 이미 있으면 새로 만들지 않고 업데이트하는 옵션을 둔다.
- 중복 방지를 위해 `Date + Project` 조합으로 기존 페이지를 검색한다.

중복 처리 방식:

```text
1. Notion Database에서 Date가 오늘이고 Project가 같은 페이지를 검색한다.
2. 있으면 해당 페이지 본문을 업데이트하거나 새 실행 로그를 아래에 추가한다.
3. 없으면 새 페이지를 만든다.

## 집계 기준과 첫 실행 정책

작업일지 집계 기준은 `어제 하루`가 아니라 `마지막 성공 업로드 시각 이후부터 현재까지`로 잡는다.

이 방식의 장점:

- 컴퓨터가 꺼져 있던 날의 작업을 다음 실행 때 보충할 수 있다.
- 주말, 휴가, 스케줄러 실패로 인한 누락을 줄일 수 있다.
- 하루에 여러 번 실행해도 마지막 성공 시각 이후만 다시 보면 된다.
- 날짜별 Notion 페이지와 함께 쓰면 캘린더 뷰에서도 자연스럽게 확인할 수 있다.

### 실행 상태 파일

실행 상태는 `.worklog/state/run_state.json`에 저장한다.

예시:

```json
{
  "last_success_at": "2026-08-21T22:30:00+09:00",
  "last_run_at": "2026-08-23T09:10:00+09:00",
  "timezone": "Asia/Seoul"
}
```

기본 수집 범위:

```text
from = last_success_at
to = now
```

모든 Notion 업로드가 성공했을 때만 `last_success_at`을 현재 시각으로 갱신한다. 중간에 실패하면 다음 실행에서 같은 기간을 다시 처리할 수 있어야 한다.

### 날짜별 그룹화

수집 범위가 여러 날짜에 걸칠 수 있으므로 결과는 작업 날짜 기준으로 나눈다.

예시:

```text
금요일 22:30 마지막 업로드 성공
토요일/일요일 컴퓨터 꺼짐
월요일 09:10 컴퓨터 켜짐

수집 범위:
2026-08-21 22:30 ~ 2026-08-24 09:10

Notion 생성/업데이트:
- 2026-08-21 자동 작업일지
- 2026-08-22 자동 작업일지
- 2026-08-23 자동 작업일지
- 2026-08-24 자동 작업일지
```

각 페이지의 `Date` 속성은 실제 작업 날짜로 넣는다. 페이지 본문에는 실제 수집 기간도 함께 표시한다.

본문 예시:

```text
수집 기간: 2026-08-21 22:30 ~ 2026-08-24 09:10
이 페이지의 작업 날짜: 2026-08-23
```

### 첫 실행 정책

첫 실행에서는 `last_success_at`이 없기 때문에 별도 정책이 필요하다.

기본 정책은 `baseline_only`로 한다.

`baseline_only` 동작:

- 현재 파일 상태를 기준 스냅샷으로 저장한다.
- `last_success_at`을 현재 시각으로 저장한다.
- 기존 파일들을 오늘 작업으로 업로드하지 않는다.
- 선택적으로 Notion에 초기화 페이지를 남길 수 있다.

이유:

- 첫 실행부터 전체 폴더를 업로드하면 오래된 파일이 오늘 작업처럼 기록될 수 있다.
- 민감한 과거 파일이 의도치 않게 Notion으로 올라갈 수 있다.
- 이후 실행부터는 변경분만 안정적으로 수집할 수 있다.

첫 실행 예시:

```text
2026-08-23 10:00 첫 실행

처리:
- 현재 파일 상태 저장
- latest_snapshot.json 생성
- run_state.json 생성
- last_success_at = 2026-08-23T10:00:00+09:00
- 작업 변경분 업로드 없음

다음 실행:
2026-08-23 23:30

처리:
- 10:00 이후 변경된 파일과 커밋 수집
- 2026-08-23 작업일지 생성/업데이트
```

### 첫 실행 모드 옵션

설정 파일에서 첫 실행 동작을 선택할 수 있게 한다.

```json
{
  "scan": {
    "first_run_mode": "baseline_only",
    "first_run_lookback_days": 3
  }
}
```

지원 모드:

| 모드 | 설명 | 권장 여부 |
| --- | --- | --- |
| `baseline_only` | 현재 상태만 기준으로 저장하고 작업일지는 업로드하지 않음 | 기본값 |
| `today_only` | 오늘 00:00 이후 수정된 파일만 첫 작업일지로 업로드 | 선택 |
| `lookback_days` | 최근 N일 변경분을 첫 작업일지로 업로드 | 선택 |

초기화 페이지를 Notion에 남기는 경우 본문 예시:

```text
자동 작업일지 초기화 완료

- 기준 스냅샷 생성 완료
- 이후 실행부터 변경분 수집
- 수집 루트: %USERPROFILE%/Desktop
- 초기 파일 수: 128개
- 첫 실행 모드: baseline_only
```

### 자동 실행 트리거

Windows 작업 스케줄러에는 두 가지 트리거를 함께 둔다.

권장:

- 매일 밤 23:30 실행
- 사용자 로그인 시 보충 실행

로그인 시 실행은 컴퓨터가 꺼져 있어서 정기 실행을 놓친 경우를 보완하기 위한 것이다.

중복 실행 방지:

- 최근 30분 안에 성공 실행한 기록이 있으면 건너뛴다.
- 이미 실행 중이면 새 실행을 시작하지 않는다.
- 동일한 `Date + Project` 페이지가 있으면 새로 만들지 않고 업데이트한다.

### 최종 수집 정책

최종 정책은 다음과 같이 고정한다.

```text
집계 기준:
- last_success_at 이후부터 현재까지

첫 실행:
- 기본값 baseline_only
- 현재 상태를 기준 스냅샷으로 저장
- 기존 파일은 업로드하지 않음

Notion 저장:
- 작업 날짜별 페이지 생성/업데이트
- Date 속성은 실제 작업 날짜
- Date + Project 조합으로 중복 방지

자동 실행:
- 매일 밤 23:30
- 로그인 시 보충 실행

상태 갱신:
- 모든 업로드 성공 후에만 last_success_at 갱신
```

## Desktop 전체 스캔 운영 정책

수집 루트는 Desktop 전체로 설정한다.

```json
{
  "root_paths": [
    "%USERPROFILE%/Desktop"
  ]
}
```

## 완전 자동 브라우저/앱 작업 추적 정책

사용자가 직접 메모를 남기지 않아도 브라우저와 앱 작업 흔적을 자동으로 수집한다. 다만 웹페이지 내부 내용 전체를 읽는 방식은 개인정보와 안정성 문제가 크므로 기본 정책에서 제외한다.

핵심 방향:

- 사용자의 입력 없이 자동 수집한다.
- 파일 원문과 웹페이지 본문은 수집하지 않는다.
- 브라우저 작업은 `방문 기록 + 활성 창 제목/프로세스 체류 시간`을 결합해 추정한다.
- Notion에는 원문이 아니라 `한 일`을 추정할 수 있는 요약만 보낸다.

### 자동 수집 방식

하루 한 번 실행하는 스크립트만으로는 브라우저 체류 시간과 실제 작업 흐름을 알기 어렵다. 따라서 완전 자동화를 원하면 로그인 후 백그라운드에서 조용히 실행되는 로컬 수집기가 필요하다.

구성:

```text
Windows 로그인
-> worklog background collector 자동 시작
-> 활성 창 제목/프로세스명을 주기적으로 기록
-> 브라우저 History는 일일 업로드 시점에 읽음
-> Desktop/Git/파일 변경 정보와 합침
-> Notion에 날짜별 작업일지 업로드
```

백그라운드 수집기는 HTTP 서버가 아니다. 외부 요청을 받지 않고, 로컬에서 주기적으로 현재 활성 창 정보만 기록한다.

예시 로그:

```json
{"time":"2026-08-23T14:10:00+09:00","process":"chrome.exe","window_title":"Notion API Reference - Google Chrome"}
{"time":"2026-08-23T14:10:30+09:00","process":"Code.exe","window_title":"worklog.py - Visual Studio Code"}
{"time":"2026-08-23T14:11:00+09:00","process":"EXCEL.EXE","window_title":"매출정리.xlsx - Excel"}
```

### 수집 가능한 정보

자동으로 수집 가능한 정보:

- 활성 앱 이름
- 활성 창 제목
- 앱별 체류 시간
- 브라우저 도메인별 방문 횟수
- 브라우저 페이지 제목
- GitHub, Notion, Google Docs, Figma 등 주요 작업 도구 사용 흔적
- 파일 변경과 브라우저 활동의 시간대 연결

수집하지 않는 정보:

- 키보드 입력 내용
- 마우스 클릭 위치
- 브라우저 쿠키
- 로그인 세션
- 웹페이지 본문 전체
- 폼 입력값
- 비밀번호/토큰
- 화면 캡처

### 브라우저 History 보조 수집

Chrome/Edge의 History 파일을 읽어 브라우저 작업 힌트를 보강한다.

Windows 기본 위치:

```text
Chrome:
%LOCALAPPDATA%/Google/Chrome/User Data/Default/History

Edge:
%LOCALAPPDATA%/Microsoft/Edge/User Data/Default/History
```

브라우저가 실행 중이면 History DB가 잠길 수 있으므로 원본 파일을 직접 읽지 않고 임시 파일로 복사해서 읽는다.

기본 정책:

- 허용 도메인만 집계한다.
- 전체 URL은 업로드하지 않는다.
- 쿼리 파라미터는 제거한다.
- 페이지 제목은 민감할 수 있으므로 설정으로 끌 수 있게 한다.
- Notion에는 도메인별 방문 횟수와 작업 힌트만 보낸다.

설정 예시:

```json
{
  "browser_history": {
    "enabled": true,
    "mode": "hint_only",
    "browsers": ["chrome", "edge"],
    "allowed_domains": [
      "github.com",
      "docs.github.com",
      "developers.notion.com",
      "notion.so",
      "docs.python.org",
      "stackoverflow.com",
      "pypi.org"
    ],
    "upload_full_urls": false,
    "upload_titles": false,
    "strip_query_params": true,
    "max_items_per_day": 30
  }
}
```

### 활성 창 추적

브라우저 History만으로는 작업 시간이 빈약하므로 Windows의 활성 창 정보를 함께 기록한다.

Python 후보 라이브러리:

```text
pywin32
psutil
```

수집 주기:

```text
기본 30초
```

수집 예시:

```text
14:00 ~ 14:18 chrome.exe - Notion API Reference
14:18 ~ 15:05 Code.exe - worklog.py
15:05 ~ 15:20 EXCEL.EXE - report.xlsx
```

Notion 요약 예시:

```text
앱/브라우저 작업 흔적

- Chrome에서 Notion API 문서 관련 창이 약 18분 활성 상태였다.
- VS Code에서 worklog.py 관련 작업이 약 47분 감지되었다.
- Excel에서 report.xlsx 창이 약 15분 활성 상태였다.
- GitHub와 Python 문서 방문 흔적이 있다.
```

### 작업 추정 규칙

파일 변경, Git 기록, 브라우저 History, 활성 창 로그를 합쳐 작업을 추정한다.

예시:

```text
조건:
- Code.exe 활성 시간이 길다.
- .py 파일이 수정되었다.
- Git 커밋이 있다.

요약:
- Python 코드 작업을 수행했다.
```

```text
조건:
- Chrome에서 developers.notion.com 제목이 반복적으로 감지되었다.
- notion_client.py가 수정되었다.
- Notion 관련 커밋 메시지가 있다.

요약:
- Notion API 연동 작업을 수행했다.
```

```text
조건:
- EXCEL.EXE 활성 시간이 있다.
- .xlsx 파일 해시가 변경되었다.

요약:
- Excel 파일 작업을 수행했다.
```

### 백그라운드 실행 방식

완전 자동 사용성을 위해 Windows 로그인 시 백그라운드 수집기를 시작한다.

권장 실행 방식:

- Windows 작업 스케줄러에 `At log on` 트리거 등록
- 콘솔 창 없이 실행
- `.worklog/activity/YYYY-MM-DD.jsonl`에 로컬 로그 저장
- 매일 23:30에 Notion 업로드 실행

주의:

- 하루 한 번 실행되는 단발 스크립트만으로는 활성 창 체류 시간을 알 수 없다.
- 완전 자동 브라우저/앱 작업 추적을 원하면 가벼운 백그라운드 수집기가 필요하다.
- 이 수집기는 네트워크 서버가 아니며, 외부로 데이터를 보내지 않는다.
- Notion 업로드 시점에만 정리된 요약을 전송한다.

### 개인정보와 신뢰

이 기능은 사용자의 작업 습관을 다루므로 기본값과 표시가 중요하다.

정책:

- 설치 시 브라우저/앱 활동 수집 여부를 명확히 안내한다.
- 기본 업로드는 요약만 허용한다.
- 원문, URL 전체, 키 입력, 화면 캡처는 수집하지 않는다.
- 사용자가 언제든 기능을 끌 수 있게 한다.
- 로컬 로그 보관 기간을 둔다.

설정 예시:

```json
{
  "activity_tracking": {
    "enabled": true,
    "sample_interval_seconds": 30,
    "track_active_window": true,
    "track_browser_history": true,
    "upload_window_titles": false,
    "upload_full_urls": false,
    "local_retention_days": 14
  }
}
```

### 현실적인 결론

브라우저와 앱 작업까지 모두 자동으로 기록하려면 다음 조합이 가장 현실적이다.

```text
Desktop 파일 변경
+ Git 기록
+ Chrome/Edge History 도메인 집계
+ Windows 활성 창 제목/프로세스 체류 시간
-> 규칙 기반 작업 요약
-> Notion 캘린더 작업일지
```

이 방식은 브라우저 확장 프로그램이나 로컬 HTTP 서버 없이도 구현 가능하다. 대신 하루 한 번 실행 스크립트가 아니라 로그인 후 계속 켜져 있는 가벼운 백그라운드 수집기가 필요하다.

## Browser Worklog Extension 별도 프로젝트 계획

브라우저 작업은 Python Desktop Worklog에 억지로 포함하지 않고 별도 확장 프로그램 프로젝트로 만든다.

프로젝트 목표:

- 브라우저 안에서 한 작업을 자동으로 기록한다.
- 사용자가 별도로 메모하지 않아도 작업 흔적을 정리한다.
- Notion API로 브라우저 작업일지를 생성한다.
- 파일/Git/Desktop 작업은 다루지 않는다.

### 저장소 분리

권장 GitHub 저장소:

```text
desktop-worklog-to-notion
browser-worklog-to-notion
```

각 저장소의 책임:

| 저장소 | 언어/플랫폼 | 담당 |
| --- | --- | --- |
| `desktop-worklog-to-notion` | Python | Desktop 파일/Git/문서 변경 작업일지 |
| `browser-worklog-to-notion` | Chrome/Edge Extension | 브라우저 탭/입력/웹앱 작업일지 |

### 확장 프로그램 MVP

브라우저 확장 프로그램 첫 버전은 Chrome Manifest V3 기준으로 만든다. Edge에서도 크로미움 기반이므로 대부분 같은 코드로 동작한다.

MVP 기능:

- 활성 탭 변경 감지
- 페이지 URL/도메인/제목 수집
- 도메인별 체류 시간 계산
- 특정 웹앱의 작업 페이지 감지
- 입력 가능한 영역에서 변경 이벤트 감지
- 원문 전체가 아니라 변경 발생 여부와 짧은 작업 힌트만 저장
- 하루 단위로 Notion에 브라우저 작업일지 생성

기본 대상 웹앱:

- Notion
- Confluence
- Jira
- GitHub
- Google Docs
- Google Sheets

### 입력 내용 처리 원칙

입력 내용을 그대로 수집하면 개인정보 위험이 크다. 따라서 기본 정책은 `raw input 저장 금지`로 한다.

기본값:

- 사용자가 입력한 원문을 저장하지 않는다.
- 비밀번호 입력 필드는 절대 감지하지 않는다.
- 이메일, 전화번호, 토큰처럼 보이는 값은 폐기한다.
- 입력 이벤트는 `편집 발생`, `입력량`, `작업 시간`, `페이지 제목` 정도로 요약한다.

선택 옵션:

```json
{
  "privacy": {
    "capture_raw_input": false,
    "capture_selection_text": false,
    "capture_page_body": false,
    "mask_urls": true,
    "strip_query_params": true
  }
}
```

입력 이벤트 요약 예시:

```json
{
  "time": "2026-08-23T15:20:00+09:00",
  "domain": "notion.so",
  "app": "Notion",
  "page_title": "자동 작업일지 구현 계획",
  "event_type": "editing_activity",
  "typing_bursts": 12,
  "active_seconds": 900,
  "raw_text_saved": false
}
```

Notion 출력 예시:

```text
브라우저 작업일지

- Notion에서 `자동 작업일지 구현 계획` 페이지를 약 15분 편집했다.
- Confluence에서 API 설계 문서로 보이는 페이지를 약 20분 편집했다.
- GitHub에서 issue/PR 관련 페이지를 확인했다.
- Google Docs에서 문서 편집 활동이 감지되었다.
```

### 사이트별 감지 방식

확장 프로그램은 사이트별로 과한 본문 수집을 하지 않고, URL 패턴과 DOM의 안전한 메타데이터를 이용한다.

Notion:

- 도메인: `notion.so`, `notion.site`
- 페이지 제목: `document.title`
- 편집 감지: `contenteditable` 영역의 입력 이벤트 발생 여부
- 저장 데이터: 페이지 제목, 활성 시간, 편집 이벤트 횟수

Confluence:

- 도메인: 회사별 Atlassian/Confluence 도메인
- 페이지 제목: `document.title`
- 편집 감지: 편집 모드 URL/버튼/입력 이벤트
- 저장 데이터: Space 또는 페이지 제목 추정, 활성 시간, 편집 이벤트 횟수

GitHub:

- 도메인: `github.com`
- URL 패턴: `/issues/`, `/pull/`, `/commit/`, `/actions/`
- 저장 데이터: repo 이름, 작업 타입, 활성 시간

Google Docs/Sheets:

- 도메인: `docs.google.com`
- URL 패턴: `/document/`, `/spreadsheets/`
- 저장 데이터: 문서 타입, 제목, 활성 시간, 편집 이벤트 여부

### 확장 프로그램 구조

권장 구조:

```text
browser-worklog-to-notion
├── manifest.json
├── src
│   ├── background.js
│   ├── contentScript.js
│   ├── notionClient.js
│   ├── activityStore.js
│   ├── summarizer.js
│   └── options.js
├── options.html
├── popup.html
├── popup.js
└── README.md
```

역할:

- `background.js`: 탭 활성화, 시간 계산, 일일 업로드 스케줄 관리
- `contentScript.js`: 페이지 제목, 편집 이벤트, 사이트별 힌트 수집
- `activityStore.js`: `chrome.storage.local`에 활동 로그 저장
- `summarizer.js`: 규칙 기반 브라우저 작업 요약 생성
- `notionClient.js`: Notion API 업로드
- `options.js`: Notion 토큰, Database ID, 개인정보 설정 관리

### 경량화 설계 원칙

브라우저 확장 프로그램은 가볍게 동작해야 한다. 탭을 많이 열어도 브라우저 사용성이 떨어지지 않도록 `이벤트 기반 수집`, `즉시 저장`, `업로드 직전 요약` 구조로 만든다.

핵심 원칙:

- 모든 사이트에 무조건 주입하지 않는다.
- 허용 도메인에서만 content script를 실행한다.
- DOM 전체를 계속 스캔하지 않는다.
- focus된 입력 영역만 감시한다.
- 키 입력을 한 글자씩 저장하지 않는다.
- `input`, `beforeinput`, `compositionend` 이벤트를 debounce해서 처리한다.
- 메모리에는 최근 snapshot 하나와 작은 상태값만 둔다.
- 작성 chunk는 즉시 `chrome.storage.local`에 저장한다.
- 요약 라이브러리는 평소에 로드하지 않고 업로드 직전에만 lazy load한다.
- 하루/페이지별 저장량 제한을 둔다.

피해야 할 구현:

- 매초 전체 페이지 텍스트 읽기
- 큰 문서 전체 snapshot 반복 저장
- 모든 탭에 NLP 라이브러리 로드
- 모든 키 입력 이벤트를 로그로 저장
- 페이지 본문 전체 저장
- `<all_urls>` 기본 권한 사용
- raw chunk를 장시간 메모리에 보관

권장 처리 흐름:

```text
사용자가 입력 영역 focus
-> 입력 이벤트 발생
-> 3~5초 debounce
-> 현재 입력 영역의 제한된 snapshot 읽기
-> 이전 snapshot과 비교
-> 새로 작성된 chunk만 추출
-> 민감정보 필터 적용
-> chrome.storage.local에 저장
-> 메모리 상태 최소화
```

요약 처리 흐름:

```text
브라우저 시작 또는 업로드 알람
-> last_success_at 이후 chunk 조회
-> 날짜/도메인/페이지 제목별 그룹화
-> 요약 라이브러리 lazy import
-> 키워드와 작업 문장 생성
-> Notion 업로드
-> 성공한 raw chunk 삭제 또는 보관 정책 적용
```

성능 제한 기본값:

```json
{
  "performance": {
    "debounce_ms": 5000,
    "max_snapshot_chars": 10000,
    "max_chunk_chars": 2000,
    "max_chunks_per_page_per_day": 50,
    "max_total_chars_per_day": 200000,
    "summarize_only_on_upload": true,
    "allowed_domains_only": true,
    "lazy_load_summarizer": true
  }
}
```

메모리에 유지할 수 있는 값:

- 현재 focus 입력 영역의 마지막 snapshot
- 최근 chunk hash 몇 개
- debounce timer
- 현재 탭의 페이지 제목/도메인
- 설정값 일부

메모리에 유지하지 않을 값:

- 하루치 전체 raw text
- 페이지 본문 전체
- 여러 탭의 전체 snapshot
- NLP 모델/요약 라이브러리 상시 인스턴스

### 경량 요약 엔진

npm 기반 확장 프로그램으로 만들되, 요약 엔진은 가볍게 유지한다.

권장 방식:

- 첫 버전은 규칙 기반 요약으로 시작한다.
- 키워드 추출 라이브러리는 작은 것을 사용한다.
- 한국어/영어 불용어 사전을 프로젝트 내부에 둔다.
- 문장 점수화와 중복 제거는 직접 구현한다.
- 무거운 NLP 라이브러리는 기본 번들에서 제외하거나 optional로 둔다.

후보:

```text
keyword-extractor
- 매우 가벼운 키워드 추출용

wink-nlp
- 기능은 좋지만 번들 크기를 확인한 뒤 선택

compromise
- 영어 중심. 선택 기능으로 검토
```

기본 요약 규칙:

- 페이지 제목에 포함된 단어에 가중치를 준다.
- 여러 chunk에서 반복된 단어에 가중치를 준다.
- 긴 chunk의 첫 문장과 마지막 문장을 후보로 둔다.
- 같은 문장이나 유사 문장은 제거한다.
- 도메인과 페이지 제목을 조합해 작업 문장을 만든다.

예시:

```text
입력 chunk:
- Local Detail Mode를 기본으로 브라우저 작성 내용을 로컬에 임시 저장한다.
- Notion에는 원문이 아니라 작업 요약만 업로드한다.
- 업로드 성공 후 raw chunk를 삭제한다.

요약:
- Local Detail Mode 기반 브라우저 작성 기록 방식을 정리했다.
- Notion 원문 업로드 금지와 raw chunk 삭제 정책을 설계했다.
```

### 확장 프로그램 상태 저장

Python 프로젝트와 같은 방식으로 `last_success_at`을 사용한다.

상태 저장 위치:

```text
chrome.storage.local
```

상태 예시:

```json
{
  "state": {
    "last_success_at": "2026-08-21T23:30:00+09:00",
    "last_run_at": "2026-08-23T09:10:00+09:00",
    "timezone": "Asia/Seoul"
  }
}
```

업로드 기준:

```text
from = last_success_at
to = now
```

브라우저 시작 시:

- `last_success_at` 이후 저장된 chunk가 있으면 업로드를 시도한다.
- 업로드할 내용이 없으면 아무 것도 하지 않는다.
- 업로드 성공 후에만 `last_success_at`을 갱신한다.

첫 실행:

- 설치 시각을 기준점으로 저장한다.
- 설치 이전 브라우저 작업은 수집하지 않는다.
- 첫 실행부터 과거 History를 훑어 업로드하지 않는다.

### 개발자용 도메인 프리셋

브라우저 확장 프로그램은 개발자가 실제로 작성 작업을 많이 하는 사이트를 기본 프리셋으로 제공한다. 모든 사이트에서 무조건 입력을 수집하지 않고, `developer_preset`에 포함된 도메인과 사용자가 직접 추가한 도메인에서만 동작한다.

기본 정책:

- 기본값은 `developer_preset`이다.
- 사용자는 도메인을 추가하거나 제거할 수 있다.
- 민감 사이트는 blocklist로 항상 제외한다.
- `<all_urls>` 권한은 기본으로 사용하지 않는다.

권장 설정:

```json
{
  "capture_scope": "developer_preset",
  "user_allowed_domains": [],
  "blocked_domains": [
    "accounts.google.com",
    "mail.google.com",
    "gmail.com",
    "outlook.live.com",
    "outlook.office.com",
    "paypal.com",
    "stripe.com"
  ]
}
```

#### 핵심 개발 도구

```text
github.com
gitlab.com
bitbucket.org
dev.azure.com
stackoverflow.com
stackexchange.com
```

#### 이슈/프로젝트 관리

```text
atlassian.net
jira.com
linear.app
shortcut.com
trello.com
asana.com
clickup.com
monday.com
```

#### 문서/위키/노트

```text
notion.so
notion.site
confluence.com
docs.google.com
drive.google.com
coda.io
slite.com
dropboxpaper.com
quip.com
```

#### 개발 문서

```text
developer.mozilla.org
docs.github.com
docs.gitlab.com
learn.microsoft.com
cloud.google.com
docs.aws.amazon.com
docs.docker.com
kubernetes.io
nodejs.org
docs.npmjs.com
python.org
docs.python.org
pypi.org
react.dev
nextjs.org
vuejs.org
angular.dev
typescriptlang.org
vitejs.dev
tailwindcss.com
```

#### API/개발 도구

```text
postman.com
hoppscotch.io
swagger.io
readme.com
stoplight.io
insomnia.rest
rapidapi.com
```

#### 디자인/협업

```text
figma.com
miro.com
whimsical.com
lucid.app
draw.io
diagrams.net
```

#### 배포/클라우드/인프라

```text
vercel.com
netlify.com
render.com
railway.app
fly.io
heroku.com
cloudflare.com
aws.amazon.com
console.aws.amazon.com
console.cloud.google.com
portal.azure.com
supabase.com
firebase.google.com
```

#### 모니터링/로그/에러

```text
sentry.io
datadoghq.com
grafana.com
newrelic.com
betterstack.com
statuspage.io
```

#### 패키지/레지스트리

```text
npmjs.com
pypi.org
crates.io
rubygems.org
packagist.org
mvnrepository.com
nuget.org
hub.docker.com
```

### AI 사이트 프리셋

요즘 개발자는 AI 도구에 질문을 작성하면서 문제 해결, 설계, 디버깅, 문서화를 많이 진행한다. 따라서 AI 사이트는 별도 프리셋으로 관리한다.

AI 사이트에서 수집하는 것:

- 사용자가 작성한 프롬프트
- 질문/요청 입력 chunk
- 페이지 제목
- 도메인
- 작성 시간
- 키워드/작업 힌트

AI 사이트에서 수집하지 않는 것:

- AI 답변 본문
- 전체 대화 내용
- 페이지 본문 전체
- 첨부 파일
- 로그인/토큰/세션 정보

AI 사이트는 민감한 코드, 에러 로그, 회사 정보가 입력될 수 있으므로 raw 보관 기간을 더 짧게 둔다.

권장 설정:

```json
{
  "domain_presets": {
    "ai_tools": [
      "chatgpt.com",
      "chat.openai.com",
      "claude.ai",
      "gemini.google.com",
      "aistudio.google.com",
      "perplexity.ai",
      "poe.com",
      "you.com",
      "phind.com",
      "copilot.microsoft.com",
      "grok.com",
      "x.ai",
      "platform.openai.com",
      "console.anthropic.com",
      "ai.google.dev",
      "console.groq.com",
      "groq.com",
      "openrouter.ai",
      "together.ai",
      "replicate.com",
      "huggingface.co",
      "mistral.ai",
      "console.mistral.ai",
      "cohere.com",
      "dashboard.cohere.com",
      "deepseek.com",
      "platform.deepseek.com",
      "cursor.com",
      "windsurf.com",
      "lovable.dev",
      "bolt.new",
      "replit.com",
      "v0.dev",
      "base44.com"
    ]
  },
  "ai_site_policy": {
    "capture_user_prompt_only": true,
    "capture_ai_response": false,
    "raw_retention_hours": 6,
    "upload_raw_text_to_notion": false
  }
}
```

AI 사이트 Notion 출력 예시:

```text
AI 도구에서 작성한 것

- ChatGPT에서 브라우저 작업 기록 확장 프로그램의 경량화 방식을 검토했다.
- Claude에서 Notion API 업로드 구조 관련 질문을 작성했다.
- Perplexity에서 Chrome extension Manifest V3 권한 관련 자료를 조사했다.
```

### Local Detail Mode 최종 정책

Browser Worklog Extension은 `Local Detail Mode`를 기본 모드로 생각한다.

의미:

- 사용자가 브라우저에서 작성한 텍스트를 로컬에 임시 저장한다.
- Notion에는 작성 원문을 업로드하지 않는다.
- 업로드 직전에 로컬에서 경량 요약을 만든다.
- 업로드 성공 후 raw chunk를 삭제하거나 짧은 보관 기간을 적용한다.

최종 설정 예시:

```json
{
  "capture": {
    "capture_mode": "local_detail",
    "capture_only_user_written_text": true,
    "ignore_password_fields": true,
    "ignore_sensitive_patterns": true,
    "min_chars": 20,
    "debounce_ms": 5000,
    "max_chunk_chars": 2000,
    "max_chunks_per_page_per_day": 50,
    "max_total_chars_per_day": 200000,
    "raw_retention_hours": 24,
    "delete_raw_after_upload": true,
    "upload_raw_text_to_notion": false
  }
}
```

구현 원칙:

- `keydown` 로그를 저장하지 않는다.
- 입력 영역의 snapshot을 debounce 후 비교한다.
- 새로 작성된 chunk만 저장한다.
- 같은 chunk는 hash로 중복 제거한다.
- 비밀번호, 결제, 로그인, 민감 패턴은 즉시 폐기한다.
- AI 답변, 웹페이지 본문, 타인이 쓴 글은 수집하지 않는다.

예상 Notion 출력:

```text
2026-08-23 Browser Worklog

브라우저에서 작성한 것

- Notion에서 자동 작업일지 구현 계획을 정리했다.
- 브라우저 확장 프로그램의 Local Detail Mode와 경량화 정책을 설계했다.
- AI 도구에서 Chrome extension 권한, Notion API 업로드 흐름, 개인정보 보호 정책을 검토했다.
- GitHub 공개용 프로젝트 분리 방향을 정리했다.

근거

- 작성 chunk: 24개
- 주요 사이트: chatgpt.com, notion.so, github.com
- 주요 키워드: Local Detail Mode, Notion API, browser extension, last_success_at, chrome.storage.local
```

### 권한 설계

Manifest 권한은 최소화한다.

예시:

```json
{
  "permissions": [
    "tabs",
    "storage",
    "alarms",
    "idle"
  ],
  "host_permissions": [
    "https://api.notion.com/*",
    "https://*.notion.so/*",
    "https://*.atlassian.net/*",
    "https://github.com/*",
    "https://docs.google.com/*"
  ]
}
```

주의:

- `<all_urls>`는 기본으로 사용하지 않는다.
- 사용자가 추적할 도메인을 직접 추가할 수 있게 한다.
- 민감 사이트는 기본 제외한다.

### Notion 업로드 방식

확장 프로그램이 직접 Notion API로 보낸다.

장점:

- Python Desktop Worklog와 독립적으로 동작한다.
- 사용자가 브라우저 작업일지만 따로 쓸 수 있다.
- 로컬 서버가 필요 없다.

단점:

- Notion 토큰을 브라우저 확장 프로그램 저장소에 보관해야 한다.
- 토큰 보호와 권한 안내가 중요하다.

대안:

- 사용자가 직접 만든 Notion integration token을 넣는다.
- 토큰은 `chrome.storage.local`에 저장한다.
- 가능하면 최소 권한 Database만 공유하도록 안내한다.

### 작업일지 생성 주기

기본:

- 매일 23:30에 업로드
- 브라우저가 꺼져 있으면 다음 실행 시 미업로드 로그를 보충 업로드

상태 저장:

```json
{
  "last_success_at": "2026-08-23T23:30:00+09:00",
  "pending_days": ["2026-08-22", "2026-08-23"]
}
```

중복 방지:

- `Date + Source + Project` 조합으로 기존 Notion 페이지를 검색한다.
- 이미 있으면 업데이트한다.
- 없으면 새로 만든다.

### 두 프로젝트를 함께 쓰는 경우

사용자가 두 프로젝트를 모두 설치하면 Notion에는 두 종류의 기록이 생긴다.

예시:

```text
2026-08-23 Desktop Worklog
- Desktop 파일/Git/Excel/문서 변경

2026-08-23 Browser Worklog
- Notion, Confluence, GitHub, Google Docs 브라우저 작업
```

같은 Daily Worklog Database에 저장하는 경우:

- `Source = Desktop`
- `Source = Browser`

나중에 통합 뷰를 만들면 하루 작업을 한 캘린더에서 같이 볼 수 있다.

### 현실적인 제품 포지션

두 프로젝트를 분리하면 사용자는 원하는 수준만 선택할 수 있다.

- 파일/Git 중심 사용자는 Python 프로젝트만 설치한다.
- 웹앱 작업이 많은 사용자는 확장 프로그램만 설치한다.
- 둘 다 필요한 사용자는 두 프로젝트를 같은 Notion Database에 연결한다.

이 방식은 개발 범위를 분리하면서도 최종 사용자에게는 하나의 Notion 작업일지 경험으로 보이게 할 수 있다.

GitHub에 배포할 기본 설정에서는 `C:/Users/사용자명/Desktop` 같은 개인 절대 경로를 사용하지 않는다. 실행 시 현재 사용자의 환경 변수로 실제 Desktop 경로를 계산한다.

냉정한 전제:

- Desktop 전체 스캔은 기술적으로 가능하다.
- 다만 실제 작업 파일과 임시 파일, 스크린샷, 바로가기, 다운로드 파일이 섞일 수 있다.
- 따라서 모든 파일을 자세히 기록하는 방식이 아니라 작업 흔적을 분류해서 `한 일`만 기록하는 방식으로 설계한다.

Notion에 올리는 것:

- 날짜별 작업 요약
- Git 커밋 메시지와 통계
- 수정된 파일 수
- 새 파일 수
- 삭제된 파일 수
- 많이 수정된 폴더
- 많이 수정된 확장자
- 문서/코드/표 파일 작업 여부
- Excel 시트명, 행 수, 열 수 같은 구조 정보
- CSV 컬럼명과 행/열 수 같은 구조 정보
- 실행 로그와 오류 요약

Notion에 올리지 않는 것:

- 파일 첨부
- 파일 원문
- 텍스트 파일 본문
- 코드 diff 원문
- CSV 행 데이터 원문
- Excel 셀 데이터 원문
- 이미지 파일
- 압축 파일
- 설치 파일
- 바로가기 파일

Desktop 전체 스캔 기본 제외 설정:

```json
{
  "scan": {
    "max_file_size_kb": 1024,
    "exclude_dirs": [
      ".git",
      "node_modules",
      ".venv",
      "venv",
      "dist",
      "build",
      ".next",
      ".cache",
      "__pycache__",
      "$RECYCLE.BIN"
    ],
    "exclude_extensions": [
      ".lnk",
      ".png",
      ".jpg",
      ".jpeg",
      ".gif",
      ".webp",
      ".ico",
      ".zip",
      ".7z",
      ".rar",
      ".exe",
      ".msi",
      ".dll",
      ".tmp",
      ".log"
    ],
    "exclude_name_patterns": [
      "~$*",
      "스크린샷*",
      "Screenshot*"
    ]
  }
}
```

### 한 일 요약 생성 규칙

AI를 쓰지 않고 다음 규칙으로 `한 일`을 만든다.

예시 규칙:

- Git 커밋이 있으면 커밋 메시지를 작업 항목으로 사용한다.
- `.py`, `.js`, `.ts`, `.tsx`, `.html`, `.css` 변경이 많으면 코드 작업으로 분류한다.
- `.md`, `.txt` 변경이 많으면 문서 작업으로 분류한다.
- `.xlsx`, `.csv` 변경이 있으면 데이터/표 작업으로 분류한다.
- 특정 하위 폴더에서 변경이 집중되면 해당 폴더명을 작업 영역으로 표시한다.
- 새 파일이 많으면 신규 작성 작업으로 표시한다.
- 삭제 파일이 있으면 정리 작업으로 표시한다.
- 커밋되지 않은 Git 변경사항이 있으면 진행 중 작업으로 표시한다.

예시 출력:

```text
오늘 한 일

- Git 커밋 2개를 기록했다.
- Desktop 하위 notion-api-worklog 프로젝트에서 코드 파일 5개가 수정되었다.
- Markdown 문서 1개가 수정되었다.
- Excel 파일 1개에서 시트 구조 변경이 감지되었다.
- 커밋되지 않은 변경 파일 3개가 남아 있다.
```

이 요약은 파일 내용을 설명하는 것이 아니라 파일 변경 흔적과 Git 기록을 바탕으로 만든 작업 요약이다.

### 로컬 분석과 Notion 업로드 분리

로컬에서는 파일 내용을 일부 읽을 수 있다.

목적:

- 라인 수 계산
- 제목 후보 추정
- CSV 컬럼 추출
- Excel 시트 구조 확인
- 키워드 후보 추출

하지만 Notion에는 원문을 올리지 않는다.

업로드 전 최종 데이터는 다음 형태로 제한한다.

```json
{
  "date": "2026-08-23",
  "summary": [
    "Git 커밋 2개를 기록했다.",
    "코드 파일 5개와 Markdown 문서 1개가 수정되었다.",
    "Excel 파일 1개에서 구조 변경이 감지되었다."
  ],
  "counts": {
    "commits": 2,
    "modified_files": 8,
    "new_files": 1,
    "deleted_files": 0
  },
  "file_type_summary": {
    ".py": 3,
    ".md": 1,
    ".xlsx": 1
  },
  "top_folders": [
    "Desktop/notion-api-worklog"
  ]
}
```

### 개인정보 보호 기준

Desktop 전체를 대상으로 하므로 보수적으로 처리한다.

- 파일 내용 원문은 Notion에 올리지 않는다.
- 민감 키워드가 포함된 파일명은 상세 표시하지 않고 `민감 가능 파일`로 묶는다.
- 숨김 파일과 시스템 파일은 기본 제외한다.
- 파일 경로는 필요하면 Desktop 기준 상대 경로만 기록한다.
- 파일명까지 민감할 수 있으면 설정으로 파일명 마스킹을 켤 수 있게 한다.

파일명 마스킹 옵션 예시:

```json
{
  "privacy": {
    "mask_sensitive_file_names": true,
    "upload_relative_paths_only": true,
    "upload_raw_content": false,
    "upload_file_attachments": false
  }
}
```
