-- 003: Align relationship vocabulary with the extraction schema.
-- The schema now uses PREREQUISITE_OF (was PREREQUISITE) and adds INSTANCE_OF.

update public.concept_relationships
   set relationship_type = 'PREREQUISITE_OF'
 where relationship_type = 'PREREQUISITE';

alter table public.concept_relationships
  drop constraint concept_relationships_relationship_type_check;

alter table public.concept_relationships
  add constraint concept_relationships_relationship_type_check
  check (relationship_type in (
    'PART_OF','INSTANCE_OF','DEPENDS_ON','PREREQUISITE_OF','CONTRASTS_WITH','RELATED_TO'
  ));
