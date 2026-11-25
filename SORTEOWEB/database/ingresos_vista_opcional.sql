-- Opcional: ejecutar despues del esquema, solo si el usuario tiene CREATE VIEW.
CREATE OR REPLACE SQL SECURITY INVOKER VIEW raffle_income AS
SELECT r.id AS raffle_id, r.title, r.status, r.total AS total_tickets,
       COUNT(p.id) AS registered_tickets,
       r.total - COUNT(p.id) AS available_tickets,
       COUNT(CASE WHEN p.payment = 'pagado' THEN 1 END) AS paid_tickets,
       COUNT(CASE WHEN p.payment = 'pendiente' THEN 1 END) AS pending_tickets,
       COUNT(CASE WHEN p.payment = 'pagado' THEN 1 END) * r.price_cents AS income_cents,
       COUNT(CASE WHEN p.payment = 'pendiente' THEN 1 END) * r.price_cents AS pending_income_cents,
       CAST(r.total AS UNSIGNED) * r.price_cents AS potential_income_cents
FROM raffles r LEFT JOIN participants p ON p.raffle_id = r.id
GROUP BY r.id, r.title, r.status, r.total, r.price_cents;
