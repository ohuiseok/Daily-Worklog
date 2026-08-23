# Daily Worklog

브라우저와 PC에서 한 일을 모아서 Notion 데이터베이스에 작업일지로 저장하는 프로젝트입니다.

이 저장소는 두 프로젝트로 나뉩니다.

## 어떤 README를 보면 되나요?

브라우저에서 작성한 내용을 Notion으로 보내고 싶다면:

- [브라우저용 README](browser-worklog-to-notion/README.md)

Windows Desktop 폴더의 파일 변경, Git 기록, 문서 작업 흔적을 Notion으로 보내고 싶다면:

- [PC용 README](desktop-worklog-to-notion/README.md)

설정 중 에러가 나면:

- [문제해결.md](문제해결.md)

## 폴더 구조

```text
.
├─ browser-worklog-to-notion   # Chrome/Edge 확장 프로그램
├─ desktop-worklog-to-notion   # Windows PC 작업 수집 Python 도구
├─ notion-schema               # Notion DB 속성 참고 스키마
└─ 문제해결.md                  # 자주 나는 문제와 해결법
```

## 공통으로 필요한 것

두 프로젝트 모두 Notion에 작업일지를 만들기 때문에 아래 준비가 필요합니다.

```text
Notion 데이터베이스
Notion 개인 액세스 토큰
데이터베이스 콘텐츠 사용 권한
```

처음이라면 [브라우저용 README](browser-worklog-to-notion/README.md)부터 따라 하는 것을 추천합니다. Notion 데이터베이스와 토큰 설정 과정을 가장 자세히 설명합니다.

## 보안 주의

`ntn_...` 토큰은 비밀번호와 같습니다.

GitHub, README, 코드, 스크린샷에 올리면 안 됩니다.
