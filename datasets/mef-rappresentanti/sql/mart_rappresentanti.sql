-- mart_rappresentanti — Compensi + governance per societa' partecipata e anno
--
-- 1 riga = 1 (cf, anno): aggregazione compensi, gender gap, governance.
-- PK: (cf, anno)

WITH normalized AS (
    SELECT
        TRIM(REPLACE(REPLACE(societa_cf, '[', ''), ']', '')) AS cf,
        anno,
        amministrazione,
        amm_cf,
        amm_regione,
        rapp_id,
        rapp_genere,
        incarico_tipo,
        incarico_gratuito,
        incarico_importo_eur,
        incarico_riversato_eur
    FROM clean_input
),
totali AS (
    SELECT
        cf,
        anno,
        MAX(amm_regione) AS regione_sede,
        COUNT(*) AS n_incarichi,
        COUNT(DISTINCT rapp_id) AS n_rappresentanti,
        COUNT(DISTINCT amm_cf) AS n_amministrazioni,
        COUNT(*) FILTER (WHERE incarico_gratuito = 'INCARICO GRATUITO') AS n_gratuiti,
        ROUND(100.0 * COUNT(*) FILTER (WHERE incarico_gratuito = 'INCARICO GRATUITO')
              / NULLIF(COUNT(*), 0), 1) AS pct_gratuiti,
        COUNT(*) FILTER (WHERE rapp_genere = 'M') AS n_uomini,
        COUNT(*) FILTER (WHERE rapp_genere = 'F') AS n_donne
    FROM normalized
    GROUP BY cf, anno
),
compensi AS (
    SELECT
        cf,
        anno,
        SUM(incarico_importo_eur) AS spesa_totale_eur,
        ROUND(AVG(incarico_importo_eur), 0) AS spesa_media_eur,
        MAX(incarico_importo_eur) AS spesa_max_eur,
        SUM(incarico_importo_eur) FILTER (WHERE rapp_genere = 'M') AS spesa_uomini,
        SUM(incarico_importo_eur) FILTER (WHERE rapp_genere = 'F') AS spesa_donne
    FROM normalized
    WHERE incarico_importo_eur IS NOT NULL AND incarico_importo_eur > 0
    GROUP BY cf, anno
)
SELECT
    t.*,
    c.spesa_totale_eur,
    c.spesa_media_eur,
    c.spesa_max_eur,
    c.spesa_uomini,
    c.spesa_donne,
    CASE WHEN c.spesa_uomini > 0 AND c.spesa_donne > 0
         THEN ROUND(c.spesa_donne / c.spesa_uomini, 2)
         ELSE NULL END AS ratio_f_m,
    CASE WHEN t.n_rappresentanti > 0 AND c.spesa_totale_eur > 0
         THEN ROUND(c.spesa_totale_eur / t.n_rappresentanti, 0)
         ELSE NULL END AS spesa_per_rappresentante,
    CASE WHEN c.spesa_totale_eur > 0
         THEN ROUND(c.spesa_max_eur / c.spesa_totale_eur, 3)
         ELSE NULL END AS concentrazione_spesa,
    CASE WHEN t.n_amministrazioni > 0
         THEN ROUND(t.n_incarichi::DOUBLE / t.n_amministrazioni, 1)
         ELSE NULL END AS incarichi_per_amm
FROM totali t
LEFT JOIN compensi c ON t.cf = c.cf AND t.anno = c.anno
ORDER BY t.cf, t.anno
