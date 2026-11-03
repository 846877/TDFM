# TDFM

Assistant de forgemagie pour Dofus. TDFM **ne touche jamais au jeu** : il ne clique pas,
ne lit pas la mémoire du client et n'intercepte pas le réseau. Il lit une capture d'écran
de la fenêtre de forgemagie (ou ta saisie) et te conseille :

- la prochaine rune la plus intéressante, ou celle qui a le plus de chances de passer ;
- le bon moment pour tenter une exo (PA, PM, PO…) selon le puits.

## État

- [x] Moteur de calcul : poids des runes, puits, over, probabilités estimées, conseils, timing de l'exo
- [x] Journal des tentatives pour affiner les probabilités avec tes vrais résultats
- [x] Interface Windows (saisie de l'objet, conseils, exo, résultat SC/SN/EC)
- [x] Mode direct : lecture de l'écran (OCR Windows intégré), conseils mis à jour en temps réel
- [x] `.exe` construit automatiquement par GitHub Actions (onglet Actions → TDFM-windows)

## Probabilités

TDFM utilise la formule de difficulté présentée par Huz dans « J'ai PERCÉ le secret de la forgemagie DOFUS » (voir
`tdfm/engine/model.py`), puis la corrige avec ton journal de tentatives.

## Développement

```
pip install -e .[dev]
pytest
python run_tdfm.py
```
