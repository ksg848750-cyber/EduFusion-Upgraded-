# EduFusion — Document 7: API Specification & Flow Architecture
*Technical Design Phase. Updated API Specifications.*

---

## Centralized Diagnostic Investigation Endpoints

### 1. `POST /api/v1/diagnostics/{sessionId}/analyze`
Analyzes student responses submitted during a diagnostic session.

- **Request**: `{ "sessionId": "sess_001" }`
- **Response Case A (Conclusive Evidence $\ge 0.75$)**:
  ```json
  {
    "status": "DIAGNOSED",
    "diagnosisId": "diag_001",
    "rootCause": "MISSING_PREREQUISITE",
    "confidence": 0.89
  }
  ```
- **Response Case B (Ambiguous Signal $< 0.75$ — Probe Required)**:
  ```json
  {
    "status": "PROBE_REQUIRED",
    "sessionId": "sess_001",
    "investigationReason": "Initial answers indicate a problem, but evidence is split between Missing Prerequisite and Misconception.",
    "probeQuestion": {
      "probeQuestionId": "q_probe_001",
      "questionText": "Consider a single instruction executing alone in the pipeline. Does the EX stage communicate its output to the register file before WB finishes?",
      "questionType": "PROBE",
      "difficulty": "EASY"
    }
  }
  ```

---

### 2. `POST /api/v1/diagnostics/{sessionId}/probe-answer`
Submits the student's answer and stated reasoning for a targeted diagnostic probe.

- **Request**:
  ```json
  {
    "probeQuestionId": "q_probe_001",
    "response": "No, stages never communicate before WB.",
    "reasoning": "Each stage is completely isolated until write back."
  }
  ```
- **Response**:
  ```json
  {
    "status": "DIAGNOSED",
    "diagnosisId": "diag_001",
    "rootCause": "MISCONCEPTION",
    "confidence": 0.88,
    "evidenceSummary": "Initial answer suggested timing error; probe confirmed stage isolation misconception.",
    "recommendedAction": "CORRECT_MISCONCEPTION"
  }
  ```

---

*Document 7 updated with Diagnostic Probe investigation endpoints.*
