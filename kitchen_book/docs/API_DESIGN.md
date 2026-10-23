# 비접촉 레시피북 · API 및 규칙 설계

버전 1.3.0 / 작성일 2026-10-23 / Python FastAPI, 단일 PC·단일 사용자 기준.

프로젝트 주제는 **웹캠 식재료 인식 → 확인·수정 → AI 메뉴 추천 → AI 레시피 생성 → 손 제스처 조리 보조**이다. 참고 PDF의 로봇·격자 이동은 구현 대상이 아니다. API 설계, LLM 도구 선택, 코드 기반 조건 분기, 화면 동작, 제스처 시퀀스, 복합 입력의 학습 구조를 같은 번호로 적용했다.

## API A1~A5

| 번호 | HTTP / 경로 | 요청 | 응답 / 검증 |
|---|---|---|---|
| A1 | GET `/`, `/api/health` | 없음 | HTML / `{version,demo,models,csrf,detector,yolo_device,gpu_layers}` |
| A2 | POST `/api/gesture` | `{image: JPEG data URL}` | 200 `{gesture,score,hand_present,fingers,timestamp_ms,inference_ms}`. 잠금 중이면 `{gesture:"None",score:0,busy:true}` |
| A3 | POST `/api/ingredients` | `{image: JPEG data URL}` | 202 `{job_id}` → 작업 조회의 result: `{ingredients,uncertain,evidence,review_required,verification_status,...}` |
| A4 | POST `/api/menus` | `{ingredients:[확인한 재료],request?:문자열}` | 202 `{job_id}` → `{menus:[{id,name,reason,missing}]}` 정확히 3개 |
| A4 | POST `/api/recipe` | `{ingredients,request?,menu:{name,missing?}}` | 202 `{job_id}` → `{title,ingredients,steps:[{title,instruction,timer_seconds,timer_origin}],notes}` |
| A5 | POST `/api/llm-answer` | `{prompt,context,history?,gesture?}` | 202 `{job_id}` → `{tool,args,message,need_more_info,inference_mode,parsed_tool}` |
| 공통 | GET `/api/jobs/{job_id}` | 없음 | 200 `{status,kind,started,result?,error?,elapsed_seconds?,metrics?}`. 없는 ID는 404 |
| 보조 | GET `/docs`, `/openapi.json` | 없음 | FastAPI 경로 문서·기본 OpenAPI. 자세한 JSON body 계약은 본 문서 참고 |

A2는 서버에서 MediaPipe를 실행한다. PDF 예시의 브라우저 WASM 파일 배포를 그대로 옮기지 않았다. 기존 `/api/ingredients`, `/api/menus`, `/api/recipe`, `/api/gesture`, 작업 폴링 계약을 보존했다. `/api/yolo-detect`나 `/api/vlm-describe` 별도 경로는 만들지 않았다.

모든 POST: `Content-Type: application/json`, `X-Kitchen-Token: health.csrf`가 필요하다. `127.0.0.1` 또는 `localhost`로 접속한다. 요청 본문 최대 4,200,000 bytes, 이미지 디코딩 최대 3 MB / 8 MP. 이미지 데이터는 디스크에 저장하지 않지만 입력·결과 캐시는 메모리에 일시 보관한다. 로컬 파일·폴더에는 모델 경로만 설정한다.

오류: 잘못된 JSON·인자·이미지 400, 토큰/호스트 403, 경로/작업 없음 404, AI 작업 중 재요청 409, 큰 본문 413, A2 패키지/모델 없음 503, A2 추론 오류 500. A3~A5 접수 후 추론 실패는 **HTTP 200 작업 조회 + `status:error`**이다. UI/검증기는 반드시 이 값을 검사한다. inference 실패를 DEMO 데이터로 대체하지 않는다.

## A3 식재료 탐지

- `KITCHEN_DETECTOR=auto`: `models/best.pt`가 있으면 YOLO, 없으면 기존 Qwen2.5-VL. `yolo`는 없으면 오류, `vlm`은 기존 경로 고정.
- YOLO 모델은 최초 사용 시 지연 로딩. `names` 개수가 120인지 확인한다. 120개라는 사실만으로 올바른 데이터셋임이 증명되는 것은 아니므로 `export_class_names.py`로 실제 이름도 확인한다.
- `best.pt`의 클래스 ID/영문 이름이 기준. 선택적 `models/ingredient_labels_ko.json`은 정확한 이름 일치 시만 한국어 표시명으로 바꾼다. 매핑 없는 클래스도 영문 이름으로 처리하며 번호를 추측하지 않는다. 제공 매핑은 일부 일반 재료의 편의용이며 120개 번역 완료본은 아니다.
- 기본 검출 문턱 0.25, 자동 목록 편입 0.50, NMS IoU 0.50. 0.25~0.50 후보는 `uncertain`에 표시. 상위 점수를 정답 확률로 해석하지 않는다.
- YOLO result에는 `objects:[{class_id,label,name,confidence,box:[x1,y1,x2,y2]}]`, `backend:yolo`, `inference_ms` 포함. 좌표는 `image_info`의 분석 이미지 픽셀 기준이며 촬영 미리보기에는 모델 입력 사진과 같은 크기로 표시한다.
- 빈 탐지는 빈 목록으로 반환하고 직접 입력을 안내한다. 자동으로 다른 모델을 호출하거나 보이지 않는 재료를 보충하지 않는다. 사용자의 확인 체크 후 A4 진행.

## A5 요청 예시

```json
{
  "prompt": "이쪽으로 2페이지 넘겨",
  "context": {
    "page": 1,
    "total_pages": 6,
    "timer_seconds": 180,
    "step_seconds": 120,
    "step_title": "볶기",
    "step_instruction": "재료를 2분간 볶습니다."
  },
  "history": [],
  "gesture": {
    "name": "Thumb_Up",
    "mode": "book",
    "score": 0.95,
    "stable": true,
    "age_ms": 100
  }
}
```

`page`는 0부터 시작하며 준비 페이지도 포함한다. prompt는 1~600자. total_pages 0~17, page 0~16, 초 0~86400. history는 최대 12개 항목, UI는 최근 10개 유지. history의 각 항목은 user `{role,content}` 또는 assistant `{role,tool,args,message}`. 명령 상태는 브라우저 소유이며 서버는 상태를 영구 보관하지 않는다. history는 인증된 대화 저장소가 아니라 단일 로컬 UI가 보내는 문맥이다.

결과 예:

```json
{"tool":"page","args":{"direction":"next","steps":2},"message":"다음 2페이지 이동 요청","need_more_info":false,"inference_mode":"qwen","parsed_tool":"page"}
```

도구는 실행 요청이다. 서버가 페이지·타이머를 직접 바꾸지 않는다. 브라우저가 적용한 후 실제 페이지와 타이머 상태, `applied`를 명령 로그에 표시한다. 페이지 경계는 0~마지막으로 제한한다. 서버 상태 문맥 이후 UI가 바뀌면 이전 응답을 적용하지 않는다.

## 도구와 R1~R5

| 규칙 | 보장 | 코드 / 검증 |
|---|---|---|
| R1 | `page`, `timer`, `describe`, `ask`만 허용. 잘못된 JSON/없는 도구는 describe로 종료 | `parse_tool_call`; `R1.parser`, 단위 테스트 |
| R2 | page 방향 next/previous, 이동 1~10. timer는 set/start/pause/reset/adjust. set 1~86400초, adjust -86400~86400초. 빠진 인자는 ask | `parse_tool_call`, `bounded`; `R2.clamp` |
| R3 | LLM이 추측한 방향/초를 실행 근거로 인정하지 않음. 현재 명령·되묻기 문맥·유효 손 근거만 사용. 레시피 없으면 실행 안 함 | `apply_rules`, `text_evidence`; `R3.evidence` |
| R4 | `need_more_info`는 tool이 ask일 때만 true | `call`; 모든 A5 검증 |
| R5 | 되묻기 직후 짧은 답을 이전 질문과 연결. 완료된 오래된 명령은 재사용하지 않음 | `apply_rules`; `R5.continuation`, 타이머 이어가기 단위·DOM 테스트 |

도구 의미:

- `page(direction,steps)`: 페이지 이동. 처음/끝에서 경계를 넘어가지 않는다.
- `timer(action,seconds?)`: 설정·시작·일시정지·초기화·증감. 시간 변경은 정지 상태로 만든다. start 시 시간이 없으면 ask. set 후 자동 시작하지 않는다.
- `describe()`: 현재 단계/사용법 설명. 상태 변화 없음.
- `ask()`: 부족하거나 모호한 정보 요청. 상태 변화 없음.

Qwen3-4B가 JSON Schema 제한으로 후보 도구를 선택한다. 이후 코드가 근거와 인자를 확정한다. `parsed_tool`은 모델 선택, `tool`은 규칙 적용 후 결과. `--demo`에서는 Qwen을 부르지 않고 `inference_mode=demo_rules`를 명시한다. 기술적 추론 실패는 작업 오류로 표시한다. 출력 형식 검증 실패는 describe로 종료한다.

R5 예: “2페이지 넘겨” → ask → “이전” → previous 2. “타이머 설정” → ask → “3분” → set 180. “타이머 시작”(미설정) → ask → “3분” → set 180으로 설정만 한다. 다시 “시작”을 입력한다.

R3 예: “버스 위치로 가”, “저쪽으로 해줘”에는 페이지 방향을 만들지 않는다. “다음 말고 이전 페이지”는 이전. “다음 말고 넘겨”는 ask. 명시적 취소/부정과 여러 동작이 섞인 명령은 실행하지 않고 설명/되묻기한다. 자연어 모든 표현을 완전히 이해하는 규칙은 아니다. 문서에 있는 짧은 명령 사용을 권장하며 미지원 표현은 명시적으로 다시 입력한다.

## F305 / F306

F305는 기존 책/타이머 모드를 보존하고 분 설정 시퀀스를 추가한다. 책 모드 🤟 유지 → 손가락 1~5개 700ms 유지 → 손을 400ms 내려 확정, 5초 초과는 취소. 1~5분 설정만 하고 타이머 모드로 전환한다. 👍로 시작한다. 기존 ✊는 현재 단계 시간 설정을 유지한다.

F306은 “손동작 함께 사용” 체크 상태에서만 손 근거를 A5로 전송한다. 이때 직접 제스처 명령은 중단해 같은 손으로 이중 실행하지 않는다. 현재 텍스트 > 바로 전 되묻기의 사용자 의도 > 현재 안정 손 포즈 순서. 점수 0.65 이상, 연속 유지 성공, 수신 후 1200ms 이하만 유효. 기본 동작은 엄지 위/아래이므로 화면 좌우 반전과 무관하다. 이 모드의 요청 전송은 명령 입력창/버튼으로 한다. F306 음성 전송은 미구현이며 기존 2단계 음성 요청 입력만 유지한다.

## 성능 관찰

작업 조회 `elapsed_seconds`는 모델 로딩·추론을 포함한 전체 작업 시간이다. `metrics`는 cache_hit, LLM/VLM 마지막 호출의 load_ms, generation_ms, usage를 담는다. VLM 재검증 모드의 여러 호출 총합은 elapsed_seconds로 본다. YOLO inference_ms는 모델 최초 로딩을 제외한다. 실측 전에는 성능 향상 배율이나 정확도를 주장하지 않는다.
