CREATE OR REPLACE FUNCTION sampleext.item_count()
RETURNS bigint
LANGUAGE sql
AS $$
    SELECT count(*) FROM sampleext.items;
$$;
