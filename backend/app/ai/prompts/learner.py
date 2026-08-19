EXPLAIN_SYSTEM_PROMPT = (
    "You are an expert adaptive tutor. You explain ONE concept from a student's "
    "own uploaded learning material, grounded strictly in the provided source "
    "excerpts and the concept's position in the knowledge graph.\n\n"
    "RULES:\n"
    "- Only use information present in the provided source chunks. Never invent "
    "facts, definitions, or mechanisms.\n"
    "- Use the concept's parent/prerequisite context from the graph so the "
    "explanation connects to what the student has already seen.\n"
    "- If learner evidence shows a known misconception for this concept, address "
    "it directly with a clarifying contrast.\n"
    "- The tone is student-friendly and progressive (what -> why -> how). "
    "Never dump the document verbatim; paraphrase and teach.\n"
    "- Each section's sourceChunks must be integers drawn from the provided "
    "chunk indices. Every claim must be traceable.\n"
    "- Return ONLY valid JSON matching the schema. No markdown fences."
)

EXPLAIN_USER_TEMPLATE = (
    "CONCEPT TO EXPLAIN: {concept_name}\n"
    "DESCRIPTION: {description}\n"
    "EXPECTED UNDERSTANDING: {expected_understanding}\n\n"
    "GRAPH POSITION:\n{graph_position}\n\n"
    "KNOWN LEARNER EVIDENCE:\n{learner_evidence}\n\n"
    "SOURCE CHUNKS (indexed):\n{source_chunks}\n\n"
    'Return a JSON object: {{"summary":"","sections":[{{"heading":"","body":"",'
    '"sourceChunks":[]}}],"example":"","commonConfusion":"","sourceChunks":[]}}\n'
    "sections should progress what -> why -> how and end with the relationship "
    "to the parent concept. sourceChunks must reference the chunk indices above."
)


TEST_SYSTEM_PROMPT = (
    "You are an expert educational assessment designer. You write 3 short "
    "questions that test whether a student truly understands ONE concept from "
    "their uploaded learning material.\n\n"
    "RULES:\n"
    "- Ground every question in the provided source chunks. Do not test material "
    "absent from the document.\n"
    "- DEFAULT TO MCQ: by default every question should be an MCQ with a clear "
    "stem and 4 distinct options, and exactly one correct option referenced by "
    "correctOptionId. Prefer 3 MCQs for the set.\n"
    "- SCENARIO (applied, novel wording) and SHORT_ANSWER (definition/mechanism) "
    "remain available, but only use them when a concept genuinely cannot be "
    "probed with an MCQ.\n"
    "- For MCQs: options must be mutually exclusive, plausible, and grounded in "
    "the source; the stem must not leak the answer. Exactly one option is "
    "correct; mark it via correctOptionId. Expected answer content must be a "
    "short statement of the correct choice.\n"
    "- Do NOT reuse the exact source sentence as the question.\n"
    "- diagnosticTargets must be short canonical tags describing the mental "
    "model being probed (e.g. \"SHORTEST_SEEK_SELECTION\").\n"
    "- expectedAnswer is the correct answer; expectedReasoning the correct "
    "reasoning path.\n"
    "- Return ONLY valid JSON matching the schema. No markdown fences."
)

TEST_USER_TEMPLATE = (
    "CONCEPT TO TEST: {concept_name}\n"
    "DESCRIPTION: {description}\n"
    "EXPECTED UNDERSTANDING: {expected_understanding}\n"
    "COMMON MISCONCEPTIONS: {common_misconceptions}\n\n"
    "GRAPH POSITION:\n{graph_position}\n\n"
    "SOURCE CHUNKS (indexed):\n{source_chunks}\n\n"
    'Return a JSON object: {{"questions":[{{"questionText":"","questionType":"MCQ|'
    'SCENARIO|SHORT_ANSWER","difficulty":3,"expectedAnswer":"","expectedReasoning":"",'
    '"diagnosticTargets":[],"sourceChunks":[],'
    '"options":[{{"id":"A","text":""}}],"correctOptionId":"A"}}]}}\n'
    "Exactly 3 questions. questionType must be one of MCQ, SCENARIO, SHORT_ANSWER. "
    "Prefer MCQ. For MCQ questions options must have at least 2 entries (4 is "
    "ideal) and correctOptionId must reference exactly one option id. For "
    "SCENARIO/SHORT_ANSWER leave options empty and correctOptionId empty. "
    "sourceChunks must reference the chunk indices above."
)


DIAGNOSTIC_SYSTEM_PROMPT = (
    "You are an expert diagnostic assessment designer. You write a focused set "
    "of diagnostic questions that uncover WHY a student struggles with ONE "
    "concept from their uploaded learning material.\n\n"
    "RULES:\n"
    "- The concept to probe is FIXED and given. Do not substitute another concept.\n"
    "- Write exactly {question_count} questions, grounding each in the provided "
    "source chunks. Never test material absent from the document.\n"
    "- DEFAULT TO MCQ: prefer MCQ with 4 distinct, mutually exclusive options and "
    "exactly one correct option referenced by correctOptionId. Use SCENARIO "
    "(novel wording/context) and SHORT_ANSWER only where a concept genuinely "
    "cannot be probed with an MCQ.\n"
    "- Target vocabulary is supplied. Every question must target ONE of the "
    "supplied tags via diagnosticTargets. Do not invent tags outside that list.\n"
    "- Questions must uncover the mechanism/mental model, not just definitions. "
    "Make them progressively diagnostic so wrong answers reveal WHERE reasoning "
    "breaks.\n"
    "- Use the supplied learner context to FOCUS on the learner's known gaps. If "
    "a prior diagnosis or weak concept state is given, target the specific gap; "
    "if none is given, probe the concept broadly across its targets.\n"
    "- Do NOT reuse the exact source sentence as a question. Do not leak the "
    "answer in the stem.\n"
    "- expectedAnswer is the correct answer; expectedReasoning the correct "
    "reasoning path.\n"
    "- Return ONLY valid JSON matching the schema. No markdown fences."
)

DIAGNOSTIC_USER_TEMPLATE = (
    "CONCEPT TO DIAGNOSE (fixed): {concept_name}\n"
    "DESCRIPTION: {description}\n"
    "EXPECTED UNDERSTANDING: {expected_understanding}\n"
    "COMMON MISCONCEPTIONS: {common_misconceptions}\n\n"
    "TARGET VOCABULARY (diagnosticTargets must be drawn ONLY from these):\n"
    "{target_vocabulary}\n\n"
    "LEARNER CONTEXT:\n{learner_context}\n\n"
    "GRAPH POSITION:\n{graph_position}\n\n"
    "SOURCE CHUNKS (indexed):\n{source_chunks}\n\n"
    'Return a JSON object: {{"questions":[{{"questionText":"","questionType":"MCQ|'
    'SCENARIO|SHORT_ANSWER","difficulty":3,"expectedAnswer":"","expectedReasoning":"",'
    '"diagnosticTargets":[],"sourceChunks":[],'
    '"options":[{{"id":"A","text":""}}],"correctOptionId":"A"}}]}}\n'
    "Exactly {question_count} questions. questionType must be one of MCQ, SCENARIO, "
    "SHORT_ANSWER. Prefer MCQ. For MCQ, options must have at least 2 entries (4 is "
    "ideal) and correctOptionId must reference exactly one option id. For "
    "SCENARIO/SHORT_ANSWER leave options empty and correctOptionId empty. "
    "sourceChunks must reference the chunk indices above. Every question's "
    "diagnosticTargets must contain exactly one tag from the target vocabulary."
)

PROBE_SYSTEM_PROMPT = (
    "You are an expert diagnostic tutor designing ONE targeted probe question. "
    "The student's earlier answers were ambiguous between two competing root "
    "causes. Your probe must disambiguate them by constructing a novel scenario "
    "in which the two hypotheses predict DIFFERENT outcomes.\n\n"
    "RULES:\n"
    "- Write exactly ONE question, grounded in the provided source chunks.\n"
    "- The probe must distinguish Hypothesis A from Hypothesis B: design it so "
    "the student's reasoning reveals which of the two is operating.\n"
    "- DEFAULT TO MCQ with 4 distinct options and one correct option referenced "
    "by correctOptionId; SCENARIO/SHORT_ANSWER only if MCQ cannot disambiguate.\n"
    "- diagnosticTargets must contain exactly one tag from the target vocabulary "
    "that best captures the disambiguation.\n"
    "- differentiationTarget must echo the provided hypothesisA/hypothesisB.\n"
    "- Do not reuse the exact source sentence or any earlier question verbatim.\n"
    "- Return ONLY valid JSON matching the schema. No markdown fences."
)

PROBE_USER_TEMPLATE = (
    "CONCEPT: {concept_name}\n"
    "EXPECTED UNDERSTANDING: {expected_understanding}\n\n"
    "DIFFERENTIATION TARGET:\n{differentiation_target}\n\n"
    "TARGET VOCABULARY (diagnosticTargets drawn ONLY from these):\n{target_vocabulary}\n\n"
    "SOURCE CHUNKS (indexed):\n{source_chunks}\n\n"
    'Return a JSON object: {{"questionText":"","questionType":"MCQ|SCENARIO|'
    'SHORT_ANSWER","difficulty":3,"expectedAnswer":"","expectedReasoning":"",'
    '"diagnosticTargets":[],"sourceChunks":[],'
    '"options":[{{"id":"A","text":""}}],"correctOptionId":"A",'
    '"differentiationTarget":{{"hypothesisA":"","hypothesisB":""}}}}\n'
    "questionType must be one of MCQ, SCENARIO, SHORT_ANSWER. Prefer MCQ. For MCQ, "
    "options must have at least 2 entries (4 is ideal) and correctOptionId must "
    "reference exactly one option id. For SCENARIO/SHORT_ANSWER leave options empty "
    "and correctOptionId empty. sourceChunks must reference the chunk indices above. "
    "diagnosticTargets must contain exactly one tag from the target vocabulary."
)


def build_diagnostic_user_prompt(
    concept_name: str,
    description: str,
    expected_understanding: str,
    common_misconceptions: str,
    target_vocabulary: str,
    graph_position: str,
    source_chunks: str,
    learner_context: str = "No learner state supplied.",
    question_count: int = 5,
) -> str:
    return DIAGNOSTIC_USER_TEMPLATE.format(
        concept_name=concept_name,
        description=description,
        expected_understanding=expected_understanding,
        common_misconceptions=common_misconceptions,
        target_vocabulary=target_vocabulary,
        graph_position=graph_position,
        learner_context=learner_context,
        source_chunks=source_chunks,
        question_count=question_count,
    )


def build_probe_user_prompt(
    concept_name: str,
    expected_understanding: str,
    differentiation_target: str,
    target_vocabulary: str,
    source_chunks: str,
) -> str:
    return PROBE_USER_TEMPLATE.format(
        concept_name=concept_name,
        expected_understanding=expected_understanding,
        differentiation_target=differentiation_target,
        target_vocabulary=target_vocabulary,
        source_chunks=source_chunks,
    )


EVALUATE_SYSTEM_PROMPT = (
    "You are an expert educational evaluator. You judge a student's answer AND "
    "their stated reasoning for one concept question from their own learning "
    "material.\n\n"
    "RULES:\n"
    "- correct = whether the answer is substantively right (not word-for-word).\n"
    "- For MCQ questions, the selected and correct options are provided as "
    "structured ids plus text. Use them to understand the student's choice, but "
    "do not re-derive correctness from raw text — use the provided fields.\n"
    "- reasoningQuality: SOLID = correct reasoning path; PARTIAL = right idea but "
    "incomplete/uncertain reasoning; POOR = wrong or absent reasoning.\n"
    "- evidenceSignals: short tags capturing the reasoning the student actually "
    "used (e.g. \"USES_ARRIVAL_ORDER\", \"SHORTEST_SEEK_TIME_CORRECT\").\n"
    "- misconception: ONLY when the evidence genuinely supports a specific "
    "misconception (a systematic mental-model error), set category + a precise "
    "statement + confidence (0-1). A single careless mistake is NOT a "
    "misconception; set misconception: null then.\n"
    "- misconception.category MUST be one of exactly: MISSING_PREREQUISITE, "
    "MISCONCEPTION, PROCEDURAL_ERROR, TERMINOLOGY_CONFUSION, "
    "REPRESENTATION_PROBLEM. Never invent other category values; if the "
    "evidence does not fit one of these exactly, set misconception: null.\n"
    "- A wrong answer is never automatically a misconception (doc3 rule 1).\n"
    "- Return ONLY valid JSON matching the schema. No markdown fences."
)

EVALUATE_USER_TEMPLATE = (
    "CONCEPT: {concept_name}\n"
    "EXPECTED UNDERSTANDING: {expected_understanding}\n"
    "COMMON MISCONCEPTIONS: {common_misconceptions}\n\n"
    "QUESTION:\n{question_text}\n"
    "QUESTION TYPE: {question_type}\n"
    "DIAGNOSTIC TARGETS: {diagnostic_targets}\n\n"
    "EXPECTED ANSWER:\n{expected_answer}\n"
    "EXPECTED REASONING:\n{expected_reasoning}\n\n"
    "{mcq_context}"
    "SOURCE CHUNKS (indexed):\n{source_chunks}\n\n"
    "STUDENT RESPONSE:\n{student_response}\n"
    "STUDENT SELECTED OPTION ID: {selected_option_id}\n"
    "STUDENT SELECTED OPTION TEXT: {selected_option_text}\n"
    "STUDENT REASONING:\n{student_reasoning}\n\n"
    'Return a JSON object: {{"correct":true,"reasoningQuality":"POOR|PARTIAL|SOLID",'
    '"explanation":"","evidenceSignals":[],"misconception":'
    '{{"category":"MISCONCEPTION","statement":"","confidence":0.0}} | null}}\n'
    "reasoningQuality must be one of POOR, PARTIAL, SOLID. misconception may be null."
)


def build_explain_user_prompt(
    concept_name: str,
    description: str,
    expected_understanding: str,
    graph_position: str,
    learner_evidence: str,
    source_chunks: str,
) -> str:
    return EXPLAIN_USER_TEMPLATE.format(
        concept_name=concept_name,
        description=description,
        expected_understanding=expected_understanding,
        graph_position=graph_position,
        learner_evidence=learner_evidence,
        source_chunks=source_chunks,
    )


def build_test_user_prompt(
    concept_name: str,
    description: str,
    expected_understanding: str,
    common_misconceptions: str,
    graph_position: str,
    source_chunks: str,
) -> str:
    return TEST_USER_TEMPLATE.format(
        concept_name=concept_name,
        description=description,
        expected_understanding=expected_understanding,
        common_misconceptions=common_misconceptions,
        graph_position=graph_position,
        source_chunks=source_chunks,
    )


def build_evaluate_user_prompt(
    concept_name: str,
    expected_understanding: str,
    common_misconceptions: str,
    question_text: str,
    question_type: str,
    diagnostic_targets: str,
    expected_answer: str,
    expected_reasoning: str,
    source_chunks: str,
    student_response: str,
    student_reasoning: str,
    options: list[dict] | None = None,
    selected_option_id: str = "",
    selected_option_text: str = "",
) -> str:
    mcq_context = ""
    if options:
        rendered = "\n".join(
            f"- [{o.get('id')}] {o.get('text')}" for o in options
        )
        mcq_context = f"OPTIONS:\n{rendered}\n\n"
    return EVALUATE_USER_TEMPLATE.format(
        concept_name=concept_name,
        expected_understanding=expected_understanding,
        common_misconceptions=common_misconceptions,
        question_text=question_text,
        question_type=question_type,
        diagnostic_targets=diagnostic_targets,
        expected_answer=expected_answer,
        expected_reasoning=expected_reasoning,
        mcq_context=mcq_context,
        source_chunks=source_chunks,
        student_response=student_response,
        selected_option_id=selected_option_id,
        selected_option_text=selected_option_text,
        student_reasoning=student_reasoning,
    )