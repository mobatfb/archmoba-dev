-- SORTEOWEB 1.2.1: pricing basis for new cash raffles. Run after 1.2.0.
ALTER TABLE raffles ADD COLUMN IF NOT EXISTS pricing_participations INT UNSIGNED NULL;
