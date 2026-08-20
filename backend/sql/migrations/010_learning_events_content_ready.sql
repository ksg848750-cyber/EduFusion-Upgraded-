-- Add LESSON_CONTENT_READY to the learning_events event_type check constraint.
-- The M5 lesson pipeline emits this event after lesson content is generated, but
-- the constraint from 004_learner_model.sql predates it.

alter table public.learning_events drop constraint if exists learning_events_event_type_check;

alter table public.learning_events add constraint learning_events_event_type_check check (
    event_type in (
        'MATERIAL_UPLOADED','MATERIAL_PROCESSED','DIAGNOSTIC_STARTED',
        'QUESTION_ANSWERED','DIAGNOSIS_CREATED','MISCONCEPTION_DETECTED',
        'MISCONCEPTION_RESOLVED','LESSON_STARTED','LESSON_CONTENT_READY',
        'LESSON_COMPLETED',
        'VISUALIZATION_VIEWED','REASSESSMENT_STARTED','REASSESSMENT_COMPLETED',
        'MASTERY_UPDATED','CONCEPT_UNDERSTAND_REQUESTED','TEST_SESSION_COMPLETED'
    )
);