# EduFusion — Document 8: UX / Screen & Interaction Specification
*Technical Design Phase. Complete & Finalized Document.*

---

## Governing Principle

> EduFusion is a living learning environment, not a PDF viewer, AI chatbot, or static quiz site.
> The interface continuously communicates: *"I understand what you know, I identified where you struggle, I know why, and here is how we will fix it together."*
> All screen states map directly to backend API contracts (Document 7) and are designed using **Stitch MCP**.

---

## Complete Student Journey Flow

```
LANDING PAGE
     │
     ▼
SIGN UP / LOGIN (Supabase Auth)
     │
     ▼
ONBOARDING (Goals & Optional Interests)
     │
     ▼
STUDENT DASHBOARD ("What Should I Do Next?")
     │
     ▼
CREATE SUBJECT & UPLOAD MATERIAL (PDF Ingestion)
     │
     ▼
KNOWLEDGE OVERVIEW (Interactive Graph Map)
     │
     ▼
DIAGNOSTIC ASSESSMENT (Scenario Questions + Reasoning Input)
     │
     ▼
DIAGNOSTIC RESULTS ("Why We Think This" Evidence Bundle)
     │
     ▼
PERSONALIZED LEARNING PATH (Prerequisite Unlocking)
     │
     ▼
THE LEARNING EXPERIENCE (Explanation + Mandatory Visual Player)
     │
     ▼
REASSESSMENT (Novel Scenario Verification)
     │
     ▼
LEARNER MODEL UPDATED (Mastery & Misconceptions Updated)
     │
     └─────────────────────────► REPEAT LOOP
```

---

## Screen State Specifications

---

### Screen 1: Landing Page
- **Primary Goal**: Instantly demonstrate the adaptive learning loop to visitors without technical jargon.
- **Hero Message**: *"EduFusion — Learning that adapts to you."*
- **Supporting Narrative**: *"Upload your course notes. EduFusion extracts the concept graph, diagnoses why you struggle, and teaches you with concept-accurate visualizations."*
- **Interactive Storytelling Demo**:
  - Step 1: Student uploads CPU Pipelining PDF.
  - Step 2: EduFusion detects missing `Data Dependency` prerequisite.
  - Step 3: Generates targeted lesson + animated pipeline SVG.
  - Step 4: Reassessment verifies understanding gain (21% $\rightarrow$ 67%).

---

### Screen 2: Authentication
- **Powered By**: Supabase Auth.
- **Layout**: Clean, minimal form supporting email/password or social OAuth.
- **UI Focus**: Frictionless access directly into Onboarding or Dashboard.

---

### Screen 3: Onboarding
- **Inputs**:
  - Display Name (*"What should we call you?"*).
  - Primary Learning Goal (*"University"*, *"Competitive Exam"*, *"Self Learning"*).
  - Optional Interest Contexts (*"Cricket"*, *"Gaming"*, *"Anime"*, *"F1"*, *"Movies"*, *"Music"*).
- **Control**: Prominent **"Skip for now"** button. EduFusion operates with technical precision even without interest selections.

---

### Screen 4: Student Dashboard
- **UX Core**: **Action over statistics**. Answers: *"What should I do right now?"*

```
┌──────────────────────────────────────────────────────────────┐
│  Welcome back, Ganesh!                                       │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  YOUR RECOMMENDED NEXT STEP                             │  │
│  │  Subject: Computer Architecture                        │  │
│  │  Concept: Data Dependency                              │  │
│  │  Reason: Prerequisite repair needed before Forwarding. │  │
│  │                                                        │  │
│  │  [ Start Learning Lesson → ]                           │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ACTIVE SUBJECTS                                             │
│  - Computer Architecture  (Mastery: 54% • 37 Concepts)       │
└──────────────────────────────────────────────────────────────┘
```

---

### Screen 5 & 6: Subject Creation & Material Upload
- **Drag & Drop Target**: Accepts PDF files.
- **Real-Time Extraction Status**: Replaces generic spinners with informative stage indicators:
  - `[✓] Uploading PDF`
  - `[✓] Extracting text & page structures`
  - `[●] Building Knowledge Graph & concept relationships...`
  - `[ ] Preparing personalized diagnostic`

---

### Screen 7: Knowledge Overview (Interactive Graph Map)
- **Visual Node Map**: Displays extracted concepts and prerequisite edges.
- **Interactions**: Zoom, Pan, Click Node to inspect.
- **Concept Drawer**: Shows concept description, difficulty level, prerequisites, and source PDF references (*"Found on Pages 14–17"*).

---

### Screen 8: Diagnostic Assessment
- **Framing**: Supportive, non-judgmental introduction (*"This isn't a graded exam. Your answers help us tailor how we teach you."*).
- **Question Layout**:
  - Scenario-based diagnostic question.
  - Radio/text selection for `response`.
  - **Mandatory Reasoning Input Field**: *"Explain your reasoning / why you chose this answer."*
- **Constraint**: Never reveals internal diagnostic targets to avoid biasing the student.

---

### Screen 9: Diagnostic Results & "Why We Think This"

```
┌──────────────────────────────────────────────────────────────┐
│  DIAGNOSTIC OUTCOME                                          │
│  Concept: Forwarding                                         │
│  Status: Missing Prerequisite (Data Dependency)             │
│  Confidence: 89% (High)                                      │
│                                                              │
│  WHY WE THINK THIS (Evidence Bundle)                         │
│  • Q2 Answer: You stated "Instruction B can execute          │
│    immediately because pipeline stages work independently." │
│  • Q4 Answer: You stated "Forwarding is unnecessary."        │
│                                                              │
│  Diagnosis: You are treating pipeline stages as isolated.    │
│  We will repair Data Dependency before tackling Forwarding. │
│                                                              │
│  [ View Personalized Learning Path → ]                       │
└──────────────────────────────────────────────────────────────┘
```

---

### Screen 10: Personalized Learning Path
- **Visual Flow**: Node hierarchy unlocking sequentially.
- **Locked Node Tooltip**: Clicking a locked concept (e.g. `Forwarding`) displays: *"Locked until Data Dependency prerequisite is completed."*

---

### Screen 11: The Learning Experience Screen
The primary learning view combines explanation text and the interactive visualization player in one unified layout:

```
┌──────────────────────────────────────────────────────────────┐
│  Data Dependency                             Step 1 of 3     │
├──────────────────────────────┬───────────────────────────────┤
│                              │                               │
│  EXPLANATION PANEL (40%)     │  VISUALIZATION PLAYER (60%)   │
│                              │                               │
│  Before we look at           │  [IF] ──► [ID] ──► [EX]       │
│  forwarding, let's understand│                     │         │
│  why Instruction B must      │                     ▼         │
│  wait for Instruction A...   │                    R1         │
│                              │                               │
│  [Lens: Normal | Cricket ▾]  │  [⏮] [⏸ Play] [⏭] Speed: 1x  │
│                              │                               │
├──────────────────────────────┴───────────────────────────────┤
│  [ Still Confused? 💡 ]                           [ Continue ] │
└──────────────────────────────────────────────────────────────┘
```

- **Perspective Switcher**: Toggle between `Normal` and `Cricket` (or other interest lens) narrative text. Visual renderer remains technically exact.
- **"Still Confused?" Button**: Triggers user-driven adaptation modal (*"Simpler Explanation"*, *"Worked Example"*, *"Break into smaller steps"*).

---

### Screen 12: Reassessment & Supportive Results
- **Framing**: *"Let me verify if that clicked."*
- **Content**: Novel scenario testing the same underlying gap.
- **Feedback States**:
  - `PASSED`: *"Awesome! Your understanding of Data Dependency improved (21% → 67%). Unlocking Forwarding!"*
  - `FAILED`: *"Not quite yet. We noticed the dependency model is still tricky. Let's try a visual step-by-step example."*

---

### Screen 13: Learner Dashboard & Analytics
- **Visual Mastery Map**: Overlays current concept states (`UNKNOWN`, `WEAK`, `DEVELOPING`, `MASTERED`) directly onto the Knowledge Graph.
- **Learning Timeline**: Chronological log of diagnoses, interventions, and reassessment wins.
- **Strategy Insights**: Displays evidence-backed strategy effective rates (*"Visual step-by-step interventions have helped you succeed 80% of the time"*).

---

## Stitch MCP Integration & Design System Guidelines

Stitch MCP is used to iterate and generate the production UI components based on these rules:

### 1. Typography & Hierarchy
- **Headings**: Modern sans-serif (e.g., Inter, Outfit) with strong contrast.
- **Code & Diagrams**: Clean monospace for assembly instructions and register labels (`ADD R1, R2, R3`).

### 2. Status Color Token Language
- **Mastered / Success**: `#10B981` (Emerald Green)
- **Developing / In Progress**: `#3B82F6` (Royal Blue)
- **Weak / Needs Attention**: `#F59E0B` (Amber / Orange)
- **Misconception / Error**: `#EF4444` (Crimson Red)
- **App Background**: Deep dark mode or clean high-contrast light mode (`Intelligent + Calm`).

### 3. Component to API Mapping
| UI Component | Backend Endpoint (Doc 7) |
|---|---|
| Material Upload Dropzone | `POST /api/v1/materials` |
| Progress Poller | `GET /api/v1/materials/{id}` |
| Knowledge Graph Viewer | `GET /api/v1/subjects/{id}/concepts` |
| Diagnostic Question Card | `GET /api/v1/diagnostics/{sessionId}` |
| "Why We Think This" Drawer | `GET /api/v1/diagnoses/{id}` |
| Visualization Player | `POST /api/v1/lessons` (`visualizationSpec`) |
| Reassessment Card | `POST /api/v1/reassessments/{id}/answer` |
| Learner Mastery Overlay | `GET /api/v1/learner-model/{subjectId}` |

---

## Responsive & Mobile Layout Rules

- **Desktop Layout**: 60% Visualization Player / 40% Explanation Panel side-by-side.
- **Mobile Layout**: Vertical stack with Visualization Player pinned at top (35vh), Explanation Panel scrollable below, and sticky navigation bar at bottom (`[⏮] [⏸] [⏭] [Continue]`).

---

## Error Handling UX

System or AI provider failures NEVER show raw technical errors to the student.
- **AI Rate Limit / Failure**: Displays supportive alert (*"We couldn't generate this lesson step right now. Your progress is safe. [ Try Again ]"*).
- **Network Disconnect**: Offline banner with automatic retry polling.

---

*Document 8 complete. Next: Document 9 — Technology Architecture & Learning Guide.*
