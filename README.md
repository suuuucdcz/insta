# 📸 Instagram Follower Tracker & Multi-Account Analytics

Application locale et privée pour suivre l'évolution des abonnés et abonnements de comptes Instagram, avec détection automatique des **nouveaux abonnés**, des **désabonnements (unfollowers)**, et une **analyse croisée entre 2 comptes**.

---

## 🌟 Fonctionnalités

- **🔒 Connexion Manuelle 100% Sécurisée** : Connexion directe dans une vraie fenêtre Chrome avec votre mot de passe et 2FA si activé. La session est conservée localement sur votre ordinateur.
- **🟢 Nouveaux Abonnés** : Visualisation instantanée de qui a commencé à suivre le compte cible.
- **🔴 Désabonnements** : Détection exacte des personnes qui se sont désabonnées entre deux scans.
- **🔄 Non-Réciprocités** :
  - Comptes qu'elle suit mais qui ne la suivent pas en retour.
  - Abonnés qu'elle ne suit pas en retour (Fans).
  - Amis mutuels (suivi réciproque).
- **🔀 Croisement des 2 Comptes** :
  - Abonnés en commun entre son compte 1 et son compte 2.
  - Abonnés exclusifs au compte 1 vs compte 2.
  - Taux de recouvrement et graphiques de répartition.
- **📈 Graphiques & Historique** : Courbes d'évolution du nombre d'abonnés dans le temps.
- **📥 Export CSV / Excel** : Téléchargement en 1 clic de toutes les listes et journaux d'événements.

---

## 🚀 Démarrage Rapide

### Option 1 : Double-cliquer sur `launch.bat`
Double-cliquez simplement sur le fichier `launch.bat` à la racine du projet.

### Option 2 : Ligne de commande
```bash
python -m streamlit run app.py
```
Le tableau de bord s'ouvrira automatiquement dans votre navigateur à l'adresse : `http://localhost:8501`.

---

## 📖 Guide d'Utilisation

1. **Connexion à votre compte Instagram** :
   - Dans la barre latérale à gauche, cliquez sur **🌐 Se connecter via Navigateur**.
   - Une fenêtre Chrome s'ouvre : connectez-vous avec vos identifiants Instagram habituels.
   - Dès que vous êtes connecté, la fenêtre se ferme et votre statut passe à **🟢 Connecté**.
2. **Ajouter les 2 comptes cibles** :
   - Dans la section **🎯 Comptes Cibles**, entrez le pseudo du premier compte (ex: `compte1`) et cliquez sur **Ajouter**.
   - Répétez l'opération pour le deuxième compte (ex: `compte2`).
3. **Lancer un Scan** :
   - Choisissez "Tous les comptes" ou un compte spécifique.
   - Cliquez sur **⚡ Démarrer le Scan**.
   - L'application récupère la liste complète des abonnés et abonnements.
4. **Consulter les Résultats** :
   - Naviguez entre les onglets : *Vue d'ensemble*, *Nouveaux Abonnés*, *Désabonnements*, *Non-Réciprocités*, *Croisement des 2 Comptes*, etc.
   - Lors de vos prochains scans (par exemple le lendemain ou quelques jours plus tard), l'application calculera automatiquement toutes les différences et vous montrera exactement qui s'est abonné ou désabonné.
