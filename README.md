# HARMATTAN-LOCATE — Consent-Based Location Sharing

Plateforme de **partage volontaire de position** via lien.

> ⚠ La page publique affiche clairement le consentement.  
> Les titres/messages de type arnaque (« argent gratuit », etc.) sont **bloqués**.  
> Usage trompeur ou sans consentement = **interdit**.

## Lancer

```bash
cd ~/harmattan-locate
chmod +x locate.sh
./locate.sh
```

→ Dashboard : **http://127.0.0.1:8095/ops**  
→ Liens publics : `http://127.0.0.1:8095/s/<code>`

### Accès distant (participant hors LAN)

```bash
export HLOC_HOST=0.0.0.0
export HLOC_PUBLIC_BASE=https://ton-tunnel.example
./locate.sh
```

## Fonctionnalités

- Création de liens (expiration, max clics, mot de passe, thèmes)
- Page de consentement honnête + cases à cocher
- GPS navigateur **uniquement** si popup OS acceptée
- Géoloc IP approximative (ville/pays)
- Device / browser / timezone / écran
- Dashboard events + cartes OpenStreetMap
- Export CSV / JSON
- On/off + suppression des liens
- Token API opérateur

## Ce qui n’est PAS inclus

- Sites leurres (faux gains, faux comptes)
- Tracking invisible sans case de consentement
- Contournement de la permission GPS du navigateur
