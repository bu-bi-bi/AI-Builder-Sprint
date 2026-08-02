# Chrome Extension

부산 여행 예약 조건 분석용 Chrome Side Panel 확장 프로그램이다.

## 로컬 로드

1. Chrome에서 `chrome://extensions`를 연다.
2. 개발자 모드를 켠다.
3. "압축해제된 확장 프로그램을 로드합니다"를 선택한다.
4. 이 `extension/` 디렉터리를 선택한다.

## 현재 동작

- 브라우저 action 버튼을 누르면 Chrome Side Panel이 열린다.
- Side Panel의 "현재 페이지 가져오기" 버튼으로 현재 탭의 읽을 수 있는 텍스트를 추출한다.
- Airbnb 도메인에서는 `targetSiteAdapter`를 먼저 사용한다.
- 그 외 페이지에서는 `genericAdapter`가 읽을 수 있는 전체 페이지 텍스트를 추출한다.
- 어댑터는 중요 약관을 임의로 선별하지 않고, 원문 순서 보존과 민감정보 마스킹에 집중한다.
- 긴 원문은 Side Panel에서 50,000자까지만 미리보기로 보여주며, 복사와 분석에는 전체 원문을 사용한다.

## 다음 단계

- Side Panel에서 `/api/analyze-reservation` 호출을 연결한다.
- 분석 결과 카드 UI와 원문 확인 체크를 구현한다.
- 실제 Airbnb 예약/숙소/약관 페이지에서 추출 품질을 검증한다.
