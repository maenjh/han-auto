---

### 📋 AI (Codex / Claude) 전달용 종합 작업 계획서 프롬프트

```text
# Role
You are an expert Python developer specialized in Office Automation, specifically using the `win32com` library to control Hancom Office (HWP) documents. 

# Project Goal
개발 목표는 '범정부오피스 공문서 자동화 프로그램'을 구축하는 것입니다. 사용자가 마크다운(Markdown) 문법과 프롬프트로 텍스트를 작성하면, 파이썬 프로그램이 이를 구조화된 데이터로 파싱하여 지자체(충청남도, 경상남도, 제주특별자치도 교육청 등) 표준 공문서 양식인 한글(HWP) 파일의 **'누름틀(Field)'**에 텍스트를 자동 삽입하고 마크다운 서식을 HWP 스타일에 맞게 적용하는 시스템입니다.

# Core Architecture & Features
프로그램은 다음의 핵심 기능들을 포함해야 합니다.

1. **Markdown to HTML/Data Parser**
   - 사용자의 마크다운 텍스트를 분석하여 구조화된 데이터(예: 수신자, 제목, 본문, 끝표시 등)로 분리합니다.
   - HWP 서식 매칭의 안정성을 높이기 위해, 본문 마크다운은 Python의 `markdown` 라이브러리를 사용하여 HTML 태그 구조로 1차 변환하는 로직을 고려합니다.

2. **HWP Automation Module & Security Bypass (`win32com`)**
   - `win32com.client`를 사용하여 백그라운드에서 한글(HWP) 프로그램을 실행합니다.
   - **중요:** 자동화 중단 방지를 위해 한글 보안 팝업 우회 코드(`FilePathCheckDLL` 등 보안승인모듈 레지스트리 등록 및 `hwp.RegisterModule` 실행)를 반드시 포함해야 합니다.

3. **'누름틀(Field)' 기반 데이터 삽입 및 서식 맵핑 (Core Logic)**
   - 미리 만들어둔 지자체별 공문서 템플릿(HWP)을 불러옵니다.
   - `hwp.PutFieldText("누름틀_이름", "데이터")` 메서드를 활용하여 파싱된 텍스트를 템플릿 내의 알맞은 누름틀(예: '수신', '문서제목', '본문내용')에 정확히 삽입합니다.
   - 데이터 삽입 과정에서 마크다운의 서식을 HWP에 반영합니다. 템플릿 내 미리 정의된 스타일을 호출(`hwp.HAction.Run("Style...")`)하거나, HWP 인라인 매크로 명령어(예: 볼드체 처리를 위한 `CharShapeBold`)를 결합하여 공문서 표준 규격에 맞게 변환합니다.

# Task for AI
위의 작업 계획을 완벽하게 구현하기 위해 다음 4가지를 작성해 주세요.

1. **Project Setup:** 이 프로젝트의 디렉토리 구조와 필요한 외부 라이브러리 목록(`requirements.txt`).
2. **Base Configuration:** HWP 객체 생성 및 보안 팝업 우회 로직이 포함된 초기화 코드.
3. **Core Automation Class:** 
   - 지정된 템플릿 파일을 열고 `hwp.PutFieldText`를 이용해 누름틀에 데이터를 밀어 넣는 기능.
   - 마크다운 서식(헤더, 리스트, 볼드체)을 HWP 스타일이나 매크로 액션으로 맵핑하여 적용하는 상세 로직 및 예제.
4. **Error Handling:** 템플릿 파일이 없거나, HWP에 지정된 누름틀 이름이 존재하지 않거나, 한글 프로그램이 설치되지 않은 경우를 대비한 견고한 예외 처리 방안.
```

---

### 💡 활용 안내
*   위 프롬프트는 **보안 팝업 우회(FilePathCheckDLL)**, **마크다운의 HTML 1차 파싱 전략**, **누름틀(PutFieldText) 활용** 등 실무에서 HWP 자동화 시 발생할 수 있는 주요 문제 해결법을 AI가 미리 인지하도록 설계되었습니다.
*   AI가 코드를 생성해주면, `win32com`이 로컬 환경의 한글 프로그램과 통신하므로 실제 윈도우 환경에서 코드를 테스트하시면서 누름틀 이름(`문서제목`, `본문내용` 등)만 템플릿과 동일하게 맞춰주시면 원활하게 작동할 것입니다.