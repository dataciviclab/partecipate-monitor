SELECT
    CAST({year} AS INTEGER) AS anno,
    normalize_string("Amministrazione Settore Istituzionale") AS settore_istituzionale,
    normalize_string("Amministrazione Macrocategoria") AS macrocategoria,
    normalize_string("Amministrazione Categoria") AS categoria,
    normalize_string("Amministrazione Denominazione") AS denominazione,
    REPLACE(REPLACE(normalize_string("Amministrazione Codice Fiscale"), '[', ''), ']', '') AS cf,
    normalize_string("Amministrazione Regione Sede") AS regione_sede,
    normalize_string("Amministrazione Provincia Sede") AS provincia_sede,
    normalize_string("Amministrazione Comune Sede") AS comune_sede,
    TRY_CAST("Partecipazioni dichiarate" AS INTEGER) AS partecipazioni_dichiarate,
    TRY_CAST("Incarichi dichiarati" AS INTEGER) AS incarichi_dichiarati,
    CASE WHEN normalize_string("Dichiarazione negativa su partecipazioni in forme societarie") = 'SI' THEN true ELSE false END AS negativa_partecipazioni_societarie,
    CASE WHEN normalize_string("Dichiarazione negativa su partecipazioni in forme non societarie") = 'SI' THEN true ELSE false END AS negativa_partecipazioni_nonsocietarie,
    CASE WHEN normalize_string("Dichiarazione negativa su incarichi") = 'SI' THEN true ELSE false END AS negativa_incarichi,
    CASE WHEN UPPER(normalize_string("Adempimento Amministrazione")) = 'ADEMPIENTE' THEN true ELSE false END AS adempiente
FROM raw_input
