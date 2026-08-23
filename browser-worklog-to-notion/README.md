# 브라우저 작업일지 Notion 업로드

Chrome/Edge에서 내가 입력한 브라우저 작업 내용을 로컬에서 가볍게 정리한 뒤 Notion 데이터베이스에 작업일지로 저장하는 확장 프로그램입니다.

목표는 간단합니다.

```text
브라우저에서 글 작성 → 확장 프로그램이 감지 → Upload now → Notion에 작업일지 생성
```

## 1. Notion 데이터베이스 만들기

1. Notion을 엽니다.
2. 왼쪽 메뉴에서 새 페이지를 만듭니다.
3. 페이지 이름을 정합니다.

예시:

```text
Daily Worklog
```

4. 새 페이지 안에서 표 데이터베이스를 만듭니다.

Notion에서 아래와 비슷한 메뉴를 고르면 됩니다.

```text
표
Table
Database - Table
표 - 전체 페이지
```

5. 처음에는 `이름` 속성만 있어도 괜찮습니다.

나머지 속성은 확장 프로그램 Options 페이지에서 자동으로 만듭니다.

## 2. Notion 토큰 만들기

1. Notion 왼쪽 사이드바에서 `설정`을 엽니다.
2. `연결` 메뉴를 엽니다.
3. `개발자 포털`을 엽니다.
4. `개인 액세스 토큰` 또는 `Personal access tokens` 화면을 엽니다.
5. 토큰을 새로 만드는 버튼을 누릅니다.

Notion UI에 따라 버튼 이름은 조금 다를 수 있습니다.

```text
새 토큰
토큰 만들기
Create token
```

6. 이름을 입력합니다.

예시:

```text
daily-worklog-connection
```

7. 이 프로젝트를 사용할 Notion 워크스페이스를 선택합니다.
8. 토큰을 생성합니다.
9. 토큰 값이 보이면 바로 복사해 둡니다.

토큰은 보통 이렇게 시작합니다.

```text
ntn_...
```

## 3. 토큰 기능 권한 켜기

방금 만든 토큰 설정에서 `기능` 또는 `Capabilities` 화면으로 갑니다.

아래 3개를 켭니다.

```text
콘텐츠 읽기
콘텐츠 업데이트
콘텐츠 삽입
```

## 4. 데이터베이스 접근 권한 주기

토큰에 기능 권한을 켜도, 실제 데이터베이스 접근 권한을 따로 줘야 합니다.

1. Notion 왼쪽 사이드바에서 `설정`을 엽니다.
2. `연결` 메뉴를 엽니다.
3. `개발자 포털`을 엽니다.
4. 방금 만든 토큰을 엽니다.
5. `콘텐츠 사용 권한` 또는 `Content access` 탭을 엽니다.
6. `페이지와 데이터베이스 추가` 또는 비슷한 추가 버튼을 누릅니다.
7. 1번에서 만든 데이터베이스를 선택합니다.

예시:

```text
Daily Worklog
```

8. 저장합니다.

성공하면 `콘텐츠 사용 권한` 탭에 선택한 데이터베이스가 보입니다.

## 5. 확장 프로그램 빌드하기

터미널에서 이 폴더로 이동합니다.

```powershell
cd "C:\path\to\daily-worklog\browser-worklog-to-notion"
```

처음 한 번만 설치합니다.

```powershell
npm install
```

확장 프로그램 파일을 만듭니다.

```powershell
npm run build
```

성공하면 아래 폴더가 생깁니다.

```text
browser-worklog-to-notion/dist
```

## 6. Chrome에 확장 프로그램 올리기

1. Chrome 주소창에 입력합니다.

```text
chrome://extensions
```

2. 오른쪽 위 `개발자 모드`를 켭니다.
3. `압축해제된 확장 프로그램을 로드`를 누릅니다.
4. 아래 폴더를 선택합니다.

```text
browser-worklog-to-notion/dist
```

5. 확장 프로그램 목록에 `Browser Worklog to Notion`이 보이면 성공입니다.

코드를 고치거나 새로 빌드한 뒤에는 `chrome://extensions`에서 확장 프로그램 새로고침 버튼을 눌러야 합니다.

## 7. Options 페이지 설정하기

1. `chrome://extensions`로 갑니다.
2. `Browser Worklog to Notion`을 찾습니다.
3. `세부정보`를 누릅니다.
4. `확장 프로그램 옵션` 또는 `options.html`을 엽니다.
5. `Notion 토큰` 칸에 `ntn_...` 토큰을 붙여넣습니다.
6. `토큰 저장`을 누릅니다.
7. `접근 가능한 DB 찾기`를 누릅니다.
8. `Daily Worklog` 카드의 복사 아이콘을 누르거나 카드를 클릭합니다.
9. `DB ID 저장`을 누릅니다.
10. `스키마 준비`를 누릅니다.

`스키마 준비 완료`가 보이면 설정이 끝난 것입니다.

## 8. 캡처 테스트하기

1. Notion, ChatGPT, GitHub 같은 허용 도메인을 엽니다.
2. 기존 탭이 열려 있었다면 새로고침합니다.
3. 글을 씁니다.

예시:

```text
오늘 회의 내용을 정리했다.
```

4. 2초 정도 기다립니다.
5. 확장 프로그램 아이콘을 누릅니다.
6. `Today chunks`가 `1` 이상이면 캡처 성공입니다.

## 9. Notion에 업로드하기

1. 확장 프로그램 아이콘을 누릅니다.
2. `Upload now`를 누릅니다.
3. Notion 데이터베이스를 확인합니다.

성공하면 이런 페이지가 생깁니다.

```text
2026-08-23 Browser Worklog
```

예상되는 값:

```text
Source          Browser
Status          Success
Project         Browser Worklog
Written Chunks  1
Main Domains    Notion
Summary         Notion에서 회의록 관련 문서를 정리했다.
```

문제가 나면 루트의 [문제해결.md](../문제해결.md)를 확인하세요.
