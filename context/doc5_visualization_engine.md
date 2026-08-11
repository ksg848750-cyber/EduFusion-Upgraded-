# EduFusion — Document 5: Visualization Engine Architecture
*Technical Design Phase. Complete & Finalized Document.*

---

## Governing Principle

> **Every explanation in EduFusion MUST have a synchronized visualization.**
> Visualizations are core pedagogical instruments, not decorative AI images or optional video embeds.
> The LLM produces a validated, declarative specification (`visualizationSpec`); deterministic frontend components render and animate the exact technical concept. The LLM never writes or executes frontend code.

---

## Complete Visualization Architecture

```
                            LESSON GENERATION
                                    │
                                    ▼
                   LLM Generates Explanation & Spec
                                    │
                                    ▼
                         Pydantic Spec Validation
                                    │
            ┌───────────────────────┴───────────────────────┐
            ▼                                               ▼
     VALID SPECIFICATION                            INVALID SPECIFICATION
            │                                               │
            ▼                                               ▼
  Visualization Registry                           Retry / Schema Repair
            │                                               │
 ┌──────────┼──────────┬──────────┐                         ▼
 ↓          ↓          ↓          ↓                If still invalid:
Pipeline  Hazard   Forwarding  Generic             Fallback Generic
Renderer Renderer   Renderer   Renderer                Renderer
 │          │          │          │                         │
 └──────────┴────┬─────┴──────────┘                         │
                 ▼                                          │
       Frontend SVG / Framer Motion ◄───────────────────────┘
                 │
                 ▼
     Synchronized Animation UI
     (Play, Pause, Step, Speed)
```

---

## The Declarative Specification Contract (`visualizationSpec`)

The LLM outputs a structured JSON object validated against Pydantic schemas before storage in `lessons.visualizationSpec`.

### Master Specification Schema
```json
{
  "type": "PIPELINE",
  "version": "1.0",
  "data": {
    "stages": ["IF", "ID", "EX", "MEM", "WB"],
    "instructions": [
      { "id": "I1", "text": "ADD R1, R2, R3", "color": "#4CAF50" },
      { "id": "I2", "text": "SUB R4, R1, R5", "dependsOn": "I1", "color": "#F44336" }
    ]
  },
  "highlights": ["DATA_DEPENDENCY", "HAZARD_CONFLICT"],
  "animation": {
    "steps": [
      {
        "stepIndex": 1,
        "description": "Instruction I1 enters EX stage and computes R1.",
        "stageState": { "I1": "EX", "I2": "ID" },
        "activeConnections": []
      },
      {
        "stepIndex": 2,
        "description": "Instruction I2 needs R1 in ID, but R1 is in EX/MEM pipeline register.",
        "stageState": { "I1": "MEM", "I2": "STALL" },
        "activeConnections": [
          { "from": "I1_EX", "to": "I2_ID", "label": "Raw Data Hazard", "type": "HAZARD_ARROW" }
        ],
        "hazardHighlight": true
      },
      {
        "stepIndex": 3,
        "description": "Forwarding unit passes R1 directly from EX/MEM register to EX stage input.",
        "stageState": { "I1": "MEM", "I2": "EX" },
        "activeConnections": [
          { "from": "I1_MEM", "to": "I2_EX", "label": "Forwarding Path", "type": "FORWARDING_PATH" }
        ],
        "forwardingHighlight": true
      }
    ]
  }
}
```

---

## Visualization Registry & Renderers

The frontend maintains a **Visualization Registry** mapping `type` enums to React components.

```
VISUALIZATION REGISTRY
│
├── CPU PIPELINING (MVP Core)
│   ├── PIPELINE        ──► PipelineRenderer.tsx
│   ├── HAZARD          ──► HazardRenderer.tsx
│   ├── FORWARDING      ──► ForwardingRenderer.tsx
│   └── STALL           ──► StallRenderer.tsx
│
├── GENERIC FALLBACKS (Always Available)
│   ├── GENERIC_PROCESS ──► GenericProcessRenderer.tsx
│   └── CONCEPT_MAP     ──► ConceptMapRenderer.tsx
│
└── FUTURE EXTENSIBILITY (Post-MVP)
    ├── TREE            ──► TreeRenderer.tsx
    ├── GRAPH           ──► GraphRenderer.tsx
    ├── NORMALIZATION   ──► NormalizationRenderer.tsx
    └── MEMORY_PAGING   ──► MemoryPagingRenderer.tsx
```

---

## Technical Concept vs. Interest Context Separation

```
                       STUDENT LESSON
                              │
            ┌─────────────────┴─────────────────┐
            ▼                                   ▼
   INTEREST ANALOGY TEXT              TECHNICAL VISUAL SPEC
 (e.g. Cricket Batting Run)         (CPU Pipeline Hardware)
            │                                   │
            ▼                                   ▼
 "Batters must wait for call..."    SVG Hardware Diagram
 (Pedagogical Bridge)               (Accurate Technical Truth)
```

- **Text Explanation**: Uses the interest context (cricket, gaming, anime) as a narrative bridge.
- **Visual Renderer**: ALWAYS draws the **exact, technically accurate hardware/conceptual diagram**.
- **Rule**: We NEVER generate fake interest-themed diagrams (e.g., animated cricket bats) for technical concepts. The visual shows the real hardware/system mechanics.

---

## Diagnosis-Driven Visual Emphasis

The visualization dynamically adapts its `highlights` to match the Document 3 diagnosis:

| Diagnosis Focus | Visual Emphasis / Animation Behavior |
|---|---|
| `MISCONCEPTION`: Stages independent | Highlight the dependency arrow between Instruction A and B in red; pause animation at collision point. |
| `MISSING_PREREQUISITE`: Timing model | Slow down clock cycles; animate register write-back timing explicitly. |
| `PROCEDURAL_ERROR`: Forwarding path | Animate the EX/MEM $\rightarrow$ EX data bypass path in neon green with step-by-step counter. |
| `TERMINOLOGY_CONFUSION`: Hazard vs Dependency | Display split-screen showing Data Dependency (relationship) vs Data Hazard (pipeline collision). |

---

## Frontend Rendering Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Structure & Diagrams** | **SVG (Scalable Vector Graphics)** | Crisp 2D nodes, buses, registers, arrows, and pipeline grids. |
| **Animation & Motion** | **Framer Motion** | Smooth step-by-step transitions, highlight pulses, and path tracing. |
| **Component Layer** | **React / Next.js** | Manages UI state, player timeline, step stepping, and synchronization. |
| **3D Rendering** | **Three.js / React Three Fiber** | *Optional*: Reserved strictly for spatial concepts where 3D adds genuine pedagogical value. |

---

## Interactive Player & Stepping Controls

Visualizations are not unpausable GIFs. They include interactive controls:

```
┌──────────────────────────────────────────────────────────────┐
│                  PIPELINE VISUALIZATION                      │
│                                                              │
│   [IF] ──► [ID] ──► [EX] ──► [MEM] ──► [WB]                 │
│                      │                                       │
│                      └─────── Forwarding ──► [EX]            │
│                                                              │
│  [⏮ Previous Step]   [⏸ Pause / ▶ Play]   [⏭ Next Step]       │
│  Step 2 of 3: Forwarding unit passes R1 directly to EX      │
└──────────────────────────────────────────────────────────────┘
```

- **Player Controls**: Play, Pause, Step Forward, Step Backward, Speed Adjust ($0.5x, 1x, 2x$).
- **Explanation Sync**: As the student steps through the animation, the accompanying explanation sentence highlights automatically.

---

## Fail-Safe & Fallback Pipeline

```
LLM Generates Spec
        │
        ▼
Validation Check ──► FAIL ──► Retry / Repair (1 attempt)
        │                             │
        │ PASS                        ▼
        │                    Still Fails?
        │                             │
        ▼                             ▼
Specialized Renderer        Fallback Generic Renderer
(e.g., PipelineRenderer)    (e.g., GenericProcessRenderer)
        │                             │
        └──────────────┬──────────────┘
                       ▼
         Visual Render Guaranteed
```

- **Fallback Guarantee**: If the LLM generates an unrecognized `type` or malformed payload that fails Pydantic schema validation, the system automatically routes to `GenericProcessRenderer` or `ConceptMapRenderer`.
- **Result**: The non-negotiable rule ("Every explanation MUST have a visualization") is guaranteed to hold under all runtime conditions.

---

*Document 5 complete. Next: Document 6 — Reassessment & Learner Model Architecture.*
