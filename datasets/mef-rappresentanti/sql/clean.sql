-- clean.sql — mef_rappresentanti_partecipate
--
-- Input: CSV MEF con encoding ISO-8859-1, delimitatore ;
-- Schema uniforme per anni 2018-2023.

WITH raw_clean AS (
    SELECT
        cast_int({year})                                             AS anno,
        normalize_string("Amministrazione Denominazione")           AS amministrazione,
        normalize_string("Amministrazione Settore Istituzionale")  AS amm_settore,
        normalize_string("Amministrazione Macrocategoria")         AS amm_macrocategoria,
        normalize_string("Amministrazione Categoria")              AS amm_categoria,
        normalize_string("Amministrazione Codice Fiscale")         AS amm_cf,
        normalize_string("Amministrazione Regione Sede")           AS amm_regione,
        normalize_string("Amministrazione Provincia Sede")         AS amm_provincia,
        normalize_string("Amministrazione Comune Sede")            AS amm_comune,

        normalize_string("Società/ente in cui è nominato il rappresentante Denominazione") AS societa,
        normalize_string("Società/Ente Codice Fiscale")            AS societa_cf,
        cast_int(normalize_string("Società/Ente Anno di costituzione")) AS societa_anno_costituzione,
        normalize_string("Società/Ente Forma Giuridica")           AS societa_forma_giuridica,
        normalize_string("Società/Ente Stato Giuridico")           AS societa_stato,
        normalize_string("Società/Ente Settore Attività")          AS societa_settore,
        normalize_string("Società/Ente Divisione ATECO")           AS societa_ateco,
        normalize_string("Società/Ente Regione Sede")              AS societa_regione,
        normalize_string("Società/Ente Provincia Sede")            AS societa_provincia,
        normalize_string("Società/Ente Comune Sede")               AS societa_comune,

        cast_bigint(normalize_string("Rappresentante identificativo")) AS rapp_id,
        normalize_string("Rappresentante Cognome")                 AS rapp_cognome,
        normalize_string("Rappresentante Nome")                    AS rapp_nome,
        normalize_string("Rappresentante Genere")                  AS rapp_genere,

        normalize_string("Incarico Tipologia")                     AS incarico_tipo,
        normalize_string("Incarico Data inizio")                   AS incarico_data_inizio,
        normalize_string("Incarico Data fine")                     AS incarico_data_fine,
        normalize_string("Incarico gratuito o remunerato")         AS incarico_gratuito,
        normalize_italian_number("Incarico Importo trattamento economico") AS incarico_importo_eur,
        normalize_italian_number("Incarico Compenso riversato all'Amministrazione") AS incarico_riversato_eur

    FROM raw_input
    WHERE "Rappresentante identificativo" IS NOT NULL
)

SELECT
    anno, amministrazione, amm_settore, amm_macrocategoria, amm_categoria,
    amm_cf, amm_regione, amm_provincia, amm_comune,
    societa, societa_cf, societa_anno_costituzione,
    societa_forma_giuridica, societa_stato, societa_settore, societa_ateco,
    societa_regione, societa_provincia, societa_comune,
    rapp_id, rapp_cognome, rapp_nome, rapp_genere,
    incarico_tipo, incarico_data_inizio, incarico_data_fine,
    incarico_gratuito, incarico_importo_eur, incarico_riversato_eur
FROM raw_clean
WHERE
    rapp_id IS NOT NULL
    AND rapp_cognome IS NOT NULL
