# PC 작업일지 Notion 업로드

Windows 11 PC에서 오늘 작업한 파일 변경과 Git 기록을 모아서 Notion에 작업일지를 올리는 도구입니다.

파일 첨부는 Notion에 올리지 않습니다. 대신 아래 작업 기록을 올립니다.

```text
텍스트/코드/Markdown/JSON 파일의 일부 내용
Word 문서(.docx)의 일부 내용
CSV/Excel의 컬럼과 샘플 행
파일 이름과 변경 개수
Git 커밋 메시지, 변경 파일, diff 일부
커밋하지 않은 Git 변경 파일과 diff 일부
```

PC 시작 후 백그라운드처럼 천천히 실행되는 사용 방식을 기준으로 기본 수집량과 Notion 기록량을 넉넉하게 잡았습니다.

```text
최대 스캔 파일: 20000개
최대 스캔 시간: 180초
최대 분석 파일: 10000개
텍스트 미리보기: 파일당 40줄
CSV/Excel 미리보기: 파일당 10행
Git 커밋 diff 수집: 커밋당 최대 400줄
Git 미커밋 diff 수집: 저장소당 최대 600줄
Notion 파일 상세 표시: 변경 파일 최대 80개
Notion 커밋 표시: 저장소당 최대 20개
Notion 커밋 diff 표시: 커밋당 최대 140줄
Notion 미커밋 diff 표시: 저장소당 최대 440줄
```

## 준비물 위치

GitHub에서 이 프로젝트를 받으면 아래 폴더를 엽니다.

```text
desktop-worklog-to-notion\dist
```

그 폴더 안에 아래 파일 2개가 있어야 합니다.

```text
desktop-worklog-to-notion\dist\desktop-worklog-to-notion.exe
desktop-worklog-to-notion\dist\uninstall.exe
```

처음 사용할 때는 `desktop-worklog-to-notion.exe`만 실행하면 됩니다.

지우고 싶을 때는 `uninstall.exe`를 실행하면 됩니다.

## 1. Notion 데이터베이스 만들기

먼저 작업일지를 저장할 Notion 데이터베이스를 만듭니다.

1. Notion을 엽니다.
2. 왼쪽 메뉴에서 원하는 페이지를 하나 엽니다.
3. 빈 곳에 `/database`를 입력합니다.
4. `표 - 전체 페이지` 또는 `Table - Full page`를 선택합니다.
5. 제목을 예를 들어 `Daily Worklog`로 바꿉니다.

처음에는 속성이 별로 없어도 괜찮습니다. 이 도구가 필요한 속성을 자동으로 추가합니다.

## 2. Notion API 토큰 만들기

이제 프로그램이 Notion에 글을 쓸 수 있도록 토큰을 만듭니다.

1. 브라우저에서 Notion 개발자 포털을 엽니다.
2. 내 워크스페이스로 로그인합니다.
3. 새 연결을 만듭니다.
4. 이름은 예를 들어 `Daily Worklog API`로 입력합니다.
5. 권한은 아래처럼 켭니다.

```text
콘텐츠 읽기
콘텐츠 업데이트
콘텐츠 삽입
```

6. 저장합니다.
7. 토큰을 복사합니다.

토큰은 보통 `ntn_`으로 시작합니다.

절대 GitHub, README, 코드, 스크린샷에 올리지 마세요.

## 3. Notion 데이터베이스에 권한 주기

토큰만 만들면 끝이 아닙니다. 방금 만든 데이터베이스에 연결 권한을 줘야 합니다.

1. Notion에서 `Daily Worklog` 데이터베이스를 엽니다.
2. 오른쪽 위 `...` 메뉴를 누릅니다.
3. `연결` 또는 `Connections` 메뉴를 찾습니다.
4. 방금 만든 `Daily Worklog API` 연결을 추가합니다.
5. 권한이 추가됐는지 확인합니다.

권한을 주지 않으면 프로그램이 이런 오류를 낼 수 있습니다.

```text
Could not find database
Share the database with this integration
```

이 오류가 나오면 거의 항상 데이터베이스 권한을 안 준 것입니다.

## 4. 데이터베이스 ID 복사하기

프로그램에 Notion 데이터베이스 ID를 넣어야 합니다.

1. Notion에서 `Daily Worklog` 데이터베이스를 엽니다.
2. 오른쪽 위 `...` 메뉴를 누릅니다.
3. `데이터 소스 ID 복사` 또는 비슷한 메뉴가 있으면 누릅니다.
4. 없다면 브라우저 주소에서 긴 ID를 복사합니다.

이 도구는 database ID와 data source ID를 둘 다 처리할 수 있습니다.

잘 모르겠으면 Notion에서 복사할 수 있는 ID를 그대로 넣어보면 됩니다.

## 5. 처음 실행하기

`desktop-worklog-to-notion.exe`를 더블클릭합니다.

처음 실행하면 검은 창이 열리고 아래처럼 물어봅니다.

```text
Notion token:
Notion database/data source ID:
Project name [Desktop Worklog]:
Folder to collect [%USERPROFILE%/Desktop]:
```

아래처럼 입력합니다.

```text
Notion token: ntn_...
Notion database/data source ID: Notion에서 복사한 ID
Project name [Desktop Worklog]: 그냥 Enter
Folder to collect [%USERPROFILE%/Desktop]: 그냥 Enter
```

`Project name`과 `Folder to collect`는 잘 모르겠으면 Enter만 누르세요.

기본 수집 폴더는 Desktop입니다.

## 6. 처음 실행하면 생기는 것

처음 실행하면 프로그램이 자기 자신을 안전한 위치로 복사합니다.

```text
%LOCALAPPDATA%\DesktopWorklogToNotion\app\desktop-worklog-to-notion.exe
```

설정은 아래 위치에 저장됩니다.

```text
%APPDATA%\DesktopWorklogToNotion\settings.json
```

PC를 켰을 때 자동 실행되도록 시작프로그램 바로가리도 만듭니다.

```text
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Desktop Worklog to Notion.lnk
```

그래서 처음 다운로드한 `desktop-worklog-to-notion.exe` 파일을 나중에 지워도 자동 실행은 계속 동작합니다.

## 7. 매일 어떻게 동작하나요?

PC에 로그인하면 설치된 exe가 자동으로 실행됩니다.

자동 실행 시 하는 일은 이렇습니다.

1. 마지막으로 성공한 시점을 확인합니다.
2. 그 이후에 바뀐 Desktop 파일을 확인합니다.
3. 내가 작성한 Git 커밋만 확인합니다.
4. Notion에 오늘 작업일지를 올립니다.
5. 성공하면 다음 기준 시점을 저장하고 종료합니다.

첫 실행에서는 기준점만 만들 수 있습니다. 이때는 Notion에 올리지 않고, 다음 실행부터 변경분을 올립니다.

## 8. 바로 수동 실행하기

자동 실행을 기다리지 않고 바로 실행하고 싶으면 `desktop-worklog-to-notion.exe`를 다시 더블클릭합니다.

설정이 이미 있으면 자동으로 업로드를 시도합니다.

## 9. 제거하기

더 이상 쓰고 싶지 않으면 `uninstall.exe`를 더블클릭합니다.

`uninstall.exe`는 아래 항목을 삭제합니다.

```text
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Desktop Worklog to Notion.lnk
%LOCALAPPDATA%\DesktopWorklogToNotion
%APPDATA%\DesktopWorklogToNotion\settings.json
```

즉, 자동 실행 바로가기, 설치된 exe, 저장된 설정을 지웁니다.

문제가 나면 루트의 [문제해결.md](../문제해결.md)를 확인하세요.
