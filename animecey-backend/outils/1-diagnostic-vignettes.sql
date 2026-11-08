-- À exécuter dans la console SQL de Neon.
-- 1) Voir d'où viennent les adresses des vignettes :
SELECT substring(thumbnail_url from '^https?://[^/]+') AS hote, count(*)
FROM episodes
WHERE thumbnail_url IS NOT NULL
GROUP BY 1 ORDER BY 2 DESC;

-- 2) Si tu vois l'ancien hébergeur (ex. Koyeb), remplace-le par Railway.
--    Remplace ANCIEN_HOTE (sans le https://) puis exécute :
-- UPDATE episodes
-- SET thumbnail_url = replace(thumbnail_url, 'https://ANCIEN_HOTE', 'https://animecey-production.up.railway.app')
-- WHERE thumbnail_url LIKE 'https://ANCIEN_HOTE/%';
