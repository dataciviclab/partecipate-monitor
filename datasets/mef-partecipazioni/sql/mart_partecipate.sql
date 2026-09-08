-- mart_partecipate — Anagrafica partecipate pubbliche con metriche strutturali
--
-- 1 riga = 1 (cf, anno): solo colonne dense e utili per il dashboard.
-- Le metriche governance (nr_amministratori, nr_componenti_controllo)
-- sono in mart_rappresentanti.
-- PK: (cf, anno)

WITH aggregated AS (
    SELECT
        TRIM(REPLACE(REPLACE(partecipata_codice_fiscale, '[', ''), ']', '')) AS cf,
        anno,
        MAX(TRIM(partecipata_denominazione)) AS denominazione,
        MAX(partecipata_settore_attivita) AS settore_attivita,
        MAX(partecipata_forma_giuridica) AS forma_giuridica,
        MAX(partecipata_stato_giuridico) AS stato_giuridico,
        MAX(partecipata_regione_sede) AS regione_sede,
        MAX(partecipata_provincia_sede) AS provincia_sede,
        MAX(partecipata_comune_sede) AS comune_sede,
        MAX(partecipata_nazione) AS nazione,
        MAX(partecipata_anno_di_costituzione) AS anno_costituzione,
        MAX(partecipata_divisione_ateco) AS divisione_ateco,
        MAX(tipo_controllo) AS tipo_controllo,
        MAX(CASE WHEN emittente_azioni_quotate = 'SI' THEN 1 ELSE 0 END) AS quotata,
        MAX(CASE WHEN tipo_controllo IS NOT NULL AND tipo_controllo != '' AND tipo_controllo != 'nessuno'
            THEN 1 ELSE 0 END) AS controllo_pubblico,
        COUNT(DISTINCT amministrazione_codice_fiscale) AS n_amministrazioni,
        MAX(partecipata_numero_di_addetti) AS addetti,
        MAX(partecipata_valore_della_produzione_co_e_p) AS valore_produzione,
        MAX(partecipata_risultato_d_esercizio_co_e_p) AS risultato_esercizio,
        MAX(partecipata_patrimonio_netto_co_e_p) AS patrimonio_netto,
        MAX(partecipata_costo_del_personale_co_e_p) AS costo_personale,
        MAX(quota_partecipazione_diretta) AS quota_partecipazione
    FROM clean_input
    GROUP BY cf, anno
)
SELECT
    *,
    -- ROE: risultato / patrimonio (indica redditività del capitale)
    CASE WHEN patrimonio_netto > 0
         THEN ROUND(risultato_esercizio::DOUBLE / patrimonio_netto, 4)
         ELSE NULL END AS roe,
    -- Cost ratio: costo personale / valore produzione (efficienza)
    CASE WHEN valore_produzione > 0
         THEN ROUND(costo_personale::DOUBLE / valore_produzione, 4)
         ELSE NULL END AS cost_ratio,
    -- Età dell'ente
    CASE WHEN anno_costituzione > 0
         THEN anno - anno_costituzione
         ELSE NULL END AS eta,
    -- Taglia per addetti
    CASE
        WHEN addetti IS NULL OR addetti = 0 THEN 'sconosciuta'
        WHEN addetti < 10 THEN 'piccola'
        WHEN addetti < 50 THEN 'media'
        WHEN addetti < 250 THEN 'medio-grande'
        ELSE 'grande'
    END AS taglia
FROM aggregated
ORDER BY cf, anno
