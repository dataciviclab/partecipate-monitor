-- mart_adempimenti — Compliance TUSP per amministrazione e anno
--
-- 1 riga = 1 (cf, anno): metriche di compliance derivate dai dati MEF.
-- PK: (cf, anno)

WITH base AS (
    SELECT
        cf,
        anno,
        denominazione,
        settore_istituzionale,
        macrocategoria,
        categoria,
        regione_sede,
        provincia_sede,
        comune_sede,
        partecipazioni_dichiarate,
        incarichi_dichiarati,
        negativa_partecipazioni_societarie,
        negativa_partecipazioni_nonsocietarie,
        negativa_incarichi,
        adempiente
    FROM clean_input
)
SELECT
    *,
    -- Score compliance: 0-4, più è alto più l'ente è trasparente
    (CASE WHEN NOT negativa_partecipazioni_societarie THEN 1 ELSE 0 END +
     CASE WHEN NOT negativa_partecipazioni_nonsocietarie THEN 1 ELSE 0 END +
     CASE WHEN NOT negativa_incarichi THEN 1 ELSE 0 END +
     CASE WHEN adempiente THEN 1 ELSE 0 END) AS compliance_score,
    -- Flag: ente con 0 partecipazioni dichiarate (potenziale under-reporting)
    CASE WHEN partecipazioni_dichiarate = 0 THEN true ELSE false END AS zero_partecipazioni,
    -- Flag: ente con dichiarazione negativa su tutte le forme
    CASE WHEN negativa_partecipazioni_societarie
          AND negativa_partecipazioni_nonsocietarie
          AND negativa_incarichi
         THEN true ELSE false END AS dichiarazione_negativa_totale,
    -- Categoria compliance
    CASE
        WHEN adempiente AND compliance_score = 4 THEN 'trasparente'
        WHEN adempiente AND compliance_score >= 2 THEN 'parziale'
        WHEN adempiente THEN 'minima'
        WHEN NOT adempiente THEN 'inadempiente'
    END AS categoria_compliance
FROM base
ORDER BY cf, anno
