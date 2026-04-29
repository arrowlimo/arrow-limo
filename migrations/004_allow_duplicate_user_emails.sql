ALTER TABLE public.users
    DROP CONSTRAINT IF EXISTS users_email_key;

DROP INDEX IF EXISTS public.idx_users_email;

CREATE INDEX IF NOT EXISTS idx_users_email ON public.users USING btree (email);