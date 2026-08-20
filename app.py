"""
Instagram Follower Tracker & Analytics
Interface ultra-simple, claire et directe avec accès mobile et scans programmés.
"""

import streamlit as st
import os
import sys
import pandas as pd
from datetime import datetime

# Add project root to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.database import (
    init_db,
    add_target,
    remove_target,
    get_targets,
    get_latest_snapshot,
    get_snapshots,
    get_snapshot_followers,
    get_snapshot_following,
    get_events
)
from backend.auth import (
    is_session_valid,
    login_with_browser,
    login_with_tokens,
    get_saved_session
)
from backend.scraper import scan_target
from backend.analytics import (
    compare_snapshots,
    to_rich_dataframe,
    download_avatar
)
from backend.scheduler import (
    start_scheduler,
    stop_scheduler,
    is_scheduler_active
)

# Page configuration
st.set_page_config(
    page_title="Suivi Instagram - Simple & Visuel",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database tables on startup
init_db()

# Custom Clean Styling
st.markdown("""
<style>
    .big-card {
        background-color: #1e1e24;
        border-radius: 12px;
        padding: 18px;
        border: 1px solid #333340;
        margin-bottom: 12px;
    }
    .alert-card {
        background-color: rgba(239, 68, 68, 0.15);
        border: 1px solid #ef4444;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 12px;
    }
    .success-card {
        background-color: rgba(16, 185, 129, 0.15);
        border: 1px solid #10b981;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 12px;
    }
    .info-card {
        background-color: rgba(59, 130, 246, 0.15);
        border: 1px solid #3b82f6;
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)


# --- BARRE LATÉRALE ---
with st.sidebar:
    st.title("📸 Suivi Instagram")
    st.caption("Gestion simple & sécurisée")
    
    st.markdown("---")
    
    # Statut Connexion
    saved_sess = get_saved_session()
    is_valid, user_or_err, profile_data = is_session_valid() if saved_sess else (False, "Non connecté", None)
    
    if is_valid:
        st.success(f"🟢 **Connecté** : `@{user_or_err}`")
        st.caption("Session active pour ~60 à 90 jours.")
    else:
        st.error(f"🔴 Déconnecté ({user_or_err})")
        if st.button("🌐 Ouvrir Brave pour se connecter", use_container_width=True):
            with st.spinner("Ouverture de Brave..."):
                login_with_browser(timeout_seconds=240)
                st.rerun()
                
    # Manual token login (ideal for cloud/phone without PC)
    with st.expander("🔑 Connexion directe par Jeton (Cloud / Mobile 24/7)"):
        st.caption("Collez votre `sessionid` Instagram pour utiliser l'app hébergée sur le Cloud sans avoir besoin d'ouvrir un navigateur.")
        input_sid = st.text_input("Jeton sessionid", type="password", help="Ex: 8205680658%3AIQkOxf4VhTPPKz...", key="input_sid")
        input_uid = st.text_input("Identifiant ds_user_id", value="8205680658", key="input_uid")
        input_csrf = st.text_input("csrftoken (optionnel)", type="password", key="input_csrf")
        if st.button("Valider les Jetons", use_container_width=True):
            if input_sid:
                ok_tok, msg_tok = login_with_tokens(input_sid, input_uid, input_csrf)
                if ok_tok:
                    st.success(msg_tok)
                    st.rerun()
                else:
                    st.error(msg_tok)
                
    st.markdown("---")
    
    # Comptes Cibles
    st.subheader("🎯 Vos 2 Comptes Cibles")
    targets = get_targets()
    target_names = [t["username"] for t in targets]
    
    if "salome_2m" not in target_names:
        add_target("salome_2m")
    if "salomee__pv" not in target_names:
        add_target("salomee__pv")
    targets = get_targets()
    target_names = [t["username"] for t in targets]
    
    for t in target_names:
        st.write(f"• **@{t}**")
        
    st.markdown("---")
    
    # Scans Automatiques Programmés
    st.subheader("⏰ Scan Automatique Programmé")
    scheduler_on = st.toggle("Activer le scan auto (Matin & Soir)", value=is_scheduler_active())
    if scheduler_on and not is_scheduler_active():
        start_scheduler(interval_hours=12.0)
        st.toast("Scan automatique activé toutes les 12h !", icon="⏰")
    elif not scheduler_on and is_scheduler_active():
        stop_scheduler()
        st.toast("Scan automatique désactivé.", icon="🛑")
        
    if is_scheduler_active():
        st.caption("🟢 Scan auto actif toutes les 12h.")
        
    st.markdown("---")
    
    # Bouton de Scan Manuel
    st.subheader("🚀 Scan Manuel Immédiat")
    st.caption("⚠️ Mode sécurisé anti-détection avec pauses humaines.")
    
    if st.button("⚡ Lancer un Scan Sécurisé", use_container_width=True):
        if not is_valid:
            st.error("Veuillez d'abord vous connecter avec votre session.")
        else:
            prog_bar = st.progress(0, text="Démarrage du scan sécurisé...")
            status_placeholder = st.empty()
            
            total_targets = len(target_names)
            for idx, t in enumerate(target_names):
                base_pct = idx / total_targets
                
                def on_progress(ptype, count, total):
                    sub_p = (count / total) if total > 0 else 0
                    current_p = min(0.99, base_pct + (sub_p / total_targets))
                    prog_bar.progress(current_p, text=f"Scan de @{t} ({idx+1}/{total_targets}) : {count}/{total} {ptype}...")
                
                status_placeholder.info(f"⏳ Récupération de @{t} en cours...")
                res = scan_target(t, progress_callback=on_progress)
                if res.get("success"):
                    status_placeholder.success(f"✅ @{t} terminé ({res.get('follower_count')} abonnés) !")
                else:
                    status_placeholder.warning(f"⚠️ @{t} : {res.get('message')}")
                    
            prog_bar.progress(1.0, text="✅ Scan terminé avec succès !")
            st.toast("Toutes les données ont été mises à jour !", icon="🎉")
            st.rerun()


# --- EN-TÊTE PRINCIPAL ---

st.title("📊 Tableau de Bord & Analyse d'Abonnements")

snap_main = get_latest_snapshot("salome_2m")
snap_priv = get_latest_snapshot("salomee__pv")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div class="big-card">
        <h4 style="margin:0; color:#3b82f6;">👤 Votre Compte</h4>
        <h2 style="margin:5px 0;">@mathis_dryy</h2>
        <p style="margin:0; color:#888;">Compte connecté & sécurisé</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    f_count_1 = snap_main["follower_count"] if snap_main else 373
    fl_count_1 = snap_main["following_count"] if snap_main else 403
    st.markdown(f"""
    <div class="big-card">
        <h4 style="margin:0; color:#10b981;">📱 Compte Public</h4>
        <h2 style="margin:5px 0;">@salome_2m</h2>
        <p style="margin:0;"><b>{f_count_1}</b> abonnés &nbsp;|&nbsp; <b>{fl_count_1}</b> abonnements</p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    f_count_2 = snap_priv["follower_count"] if snap_priv else 57
    fl_count_2 = snap_priv["following_count"] if snap_priv else 57
    st.markdown(f"""
    <div class="big-card">
        <h4 style="margin:0; color:#ec4899;">🔒 Compte Privé</h4>
        <h2 style="margin:5px 0;">@salomee__pv</h2>
        <p style="margin:0;"><b>{f_count_2}</b> abonnés &nbsp;|&nbsp; <b>{fl_count_2}</b> abonnements</p>
    </div>
    """, unsafe_allow_html=True)


# --- ONGLETS PRINCIPAUX ---

tab_chrono, tab_comparateur, tab_liens_secrets, tab_recherche = st.tabs([
    "⏱️ 1. Ordre d'Ajout (Qui a été suivi en dernier ?)",
    "🔄 2. COMPARER 2 DATES / SCANS (Nouveaux & Désabonnements)",
    "🔀 3. Liens & Secrets entre ses 2 Comptes",
    "🔍 4. Rechercher un Profil Précis"
])


# ==========================================
# ONGLET 1 : ORDRE CHRONOLOGIQUE
# ==========================================
with tab_chrono:
    st.header("⏱️ Ordre Chronologique Exact (Avec Photos de Profil)")
    st.write("Le **#1 est le TOUT DERNIER compte** qu'elle a suivi ou qui l'a suivie.")
    
    st.markdown("""
    <div class="info-card">
        💡 <b>Pourquoi vous voyez-vous en premier (@mathis_dryy) ?</b><br>
        Sur Instagram, lorsque vous regardez les abonnements ou abonnés de quelqu'un, <b>l'algorithme d'Instagram place TOUJOURS votre propre compte en haut de la liste (#1)</b> car vous êtes le spectateur connecté. La case ci-dessous masque automatiquement votre compte pour voir directement la première vraie personne suivie.
    </div>
    """, unsafe_allow_html=True)
    
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        chosen_acc = st.selectbox("Choisir le compte", ["salome_2m (Compte Public)", "salomee__pv (Compte Privé)"], key="ch_acc")
        target_slug = "salomee__pv" if "salomee__pv" in chosen_acc else "salome_2m"
    with col_c2:
        list_choice = st.radio("Type de liste", ["Ses Derniers Abonnements (Qui ELLE a suivi)", "Ses Nouveaux Abonnés (Qui L'A suivie)"], horizontal=True, key="ch_rad")
        
    hide_self = st.checkbox("👤 Masquer mon propre compte (@mathis_dryy) pour voir le vrai #1 de Salomé", value=True)
    
    snap = get_latest_snapshot(target_slug)
    if snap:
        is_following = "Abonnements" in list_choice
        users = get_snapshot_following(snap["id"], order_by_recent=True) if is_following else get_snapshot_followers(snap["id"], order_by_recent=True)
        
        st.subheader(f"🔥 Classement ordonné pour @{target_slug} ({len(users)} profils) :")
        
        df_chrono = to_rich_dataframe(users, include_rank=True, hide_viewer=hide_self, viewer_username="mathis_dryy")
        st.dataframe(
            df_chrono,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Photo": st.column_config.ImageColumn("Photo de Profil", help="Photo de profil"),
                "Lien Instagram": st.column_config.LinkColumn("Ouvrir sur Instagram")
            }
        )
        
        csv_data = df_chrono.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Télécharger cette liste en CSV", csv_data, f"ordre_{target_slug}.csv", "text/csv")
    else:
        st.info("Aucune donnée enregistrée.")


# ==========================================
# ONGLET 2 : COMPARATEUR ENTRE 2 SCANS
# ==========================================
with tab_comparateur:
    st.header("🔄 Comparer l'Ancien et le Nouveau Nombre d'Abonnés")
    st.write("Sélectionnez deux scans dans l'historique pour voir exactement **qui est arrivé (🟢 Nouveaux abonnés)** et **qui est parti (🔴 Désabonnements)** avec leurs photos de profil.")
    
    comp_target = st.selectbox("Choisir le compte à comparer", ["salome_2m (Compte Public)", "salomee__pv (Compte Privé)"], key="comp_acc")
    slug_comp = "salomee__pv" if "salomee__pv" in comp_target else "salome_2m"
    
    snaps_list = get_snapshots(slug_comp, limit=20)
    
    if len(snaps_list) < 1:
        st.info(f"Aucun scan enregistré pour @{slug_comp}.")
    elif len(snaps_list) == 1:
        st.markdown(f"""
        <div class="success-card">
            <h4 style="margin:0; color:#10b981;">📌 1er Scan de référence enregistré ({snaps_list[0]['timestamp']})</h4>
            <p style="margin:5px 0 0 0;">Ce scan sert de point de départ ({snaps_list[0]['follower_count']} abonnés). Dès votre 2e scan, vous pourrez comparer les deux dates en 1 clic ici et voir tous les ajouts et désabonnements !</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.subheader(f"👥 Liste actuelle des abonnés de @{slug_comp} (avec photos de profil) :")
        curr_f = get_snapshot_followers(snaps_list[0]["id"])
        df_curr = to_rich_dataframe(curr_f, include_rank=True, hide_viewer=False)
        st.dataframe(
            df_curr,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Photo": st.column_config.ImageColumn("Photo", help="Photo de profil"),
                "Lien Instagram": st.column_config.LinkColumn("Profil")
            }
        )
    else:
        snap_options = {f"Scan #{s['id']} - {s['timestamp']} ({s['follower_count']} abonnés)": s["id"] for s in snaps_list}
        snap_keys = list(snap_options.keys())
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            old_label = st.selectbox("📅 Scan Ancien (Point de départ)", snap_keys, index=min(1, len(snap_keys)-1))
            old_id = snap_options[old_label]
        with col_s2:
            new_label = st.selectbox("📅 Scan Récent (Point d'arrivée)", snap_keys, index=0)
            new_id = snap_options[new_label]
            
        if old_id == new_id:
            st.warning("Veuillez sélectionner deux dates différentes pour calculer la comparaison.")
        else:
            diff_res = compare_snapshots(old_id, new_id)
            
            st.markdown("### 📊 Résumé de l'Évolution")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Abonnés Avant", diff_res["old_follower_count"])
            m2.metric("Abonnés Après", diff_res["new_follower_count"])
            m3.metric("🟢 Nouveaux Abonnés", len(diff_res["new_followers"]), delta=f"+{len(diff_res['new_followers'])}" if diff_res['new_followers'] else None)
            m4.metric("🔴 Désabonnements", len(diff_res["unfollowers"]), delta=f"-{len(diff_res['unfollowers'])}" if diff_res['unfollowers'] else None, delta_color="inverse")
            
            tab_n_f, tab_un_f, tab_n_fl, tab_un_fl = st.tabs([
                f"🟢 Nouveaux Abonnés ({len(diff_res['new_followers'])})",
                f"🔴 Désabonnements ({len(diff_res['unfollowers'])})",
                f"➕ Nouveaux comptes suivis par elle ({len(diff_res['new_following'])})",
                f"➖ Comptes qu'elle ne suit plus ({len(diff_res['unfollowed'])})"
            ])
            
            with tab_n_f:
                if diff_res["new_followers"]:
                    st.success(f"{len(diff_res['new_followers'])} nouveau(x) abonné(s) arrivé(s) !")
                    df_nf = to_rich_dataframe(diff_res["new_followers"], include_rank=False)
                    st.dataframe(df_nf, use_container_width=True, hide_index=True, column_config={"Photo": st.column_config.ImageColumn("Photo"), "Lien Instagram": st.column_config.LinkColumn("Profil")})
                else:
                    st.info("Aucun nouvel abonné entre ces deux dates.")
                    
            with tab_un_f:
                if diff_res["unfollowers"]:
                    st.error(f"{len(diff_res['unfollowers'])} personne(s) s'est désabonnée !")
                    df_un = to_rich_dataframe(diff_res["unfollowers"], include_rank=False)
                    st.dataframe(df_un, use_container_width=True, hide_index=True, column_config={"Photo": st.column_config.ImageColumn("Photo"), "Lien Instagram": st.column_config.LinkColumn("Profil")})
                else:
                    st.info("Aucun désabonnement entre ces deux dates.")
                    
            with tab_n_fl:
                if diff_res["new_following"]:
                    st.success(f"Elle a suivi {len(diff_res['new_following'])} nouveau(x) compte(s) !")
                    df_nfl = to_rich_dataframe(diff_res["new_following"], include_rank=False)
                    st.dataframe(df_nfl, use_container_width=True, hide_index=True, column_config={"Photo": st.column_config.ImageColumn("Photo"), "Lien Instagram": st.column_config.LinkColumn("Profil")})
                else:
                    st.info("Aucun nouvel abonnement ajouté entre ces deux dates.")
                    
            with tab_un_fl:
                if diff_res["unfollowed"]:
                    st.warning(f"Elle ne suit plus {len(diff_res['unfollowed'])} compte(s).")
                    df_unfl = to_rich_dataframe(diff_res["unfollowed"], include_rank=False)
                    st.dataframe(df_unfl, use_container_width=True, hide_index=True, column_config={"Photo": st.column_config.ImageColumn("Photo"), "Lien Instagram": st.column_config.LinkColumn("Profil")})
                else:
                    st.info("Aucun désabonnement émis entre ces deux dates.")


# ==========================================
# ONGLET 3 : LIENS & SECRETS ENTRE LES 2 COMPTES
# ==========================================
with tab_liens_secrets:
    st.header("🔀 Liens & Différences entre ses 2 Comptes")
    st.write("Comparaison entre son compte public (`@salome_2m`) et son compte privé (`@salomee__pv`).")
    
    if snap_main and snap_priv:
        f_main = {u["username"]: u for u in get_snapshot_followers(snap_main["id"])}
        f_priv = {u["username"]: u for u in get_snapshot_followers(snap_priv["id"])}
        
        fl_main = {u["username"]: u for u in get_snapshot_following(snap_main["id"])}
        fl_priv = {u["username"]: u for u in get_snapshot_following(snap_priv["id"])}
        
        ex_fl_priv = [u for uname, u in fl_priv.items() if uname not in fl_main]
        ex_f_priv = [u for uname, u in f_priv.items() if uname not in f_main]
        communs = [u for uname, u in f_priv.items() if uname in f_main]
        
        sub1, sub2, sub3 = st.tabs([
            f"🔒 Suivis UNIQUEMENT sur son compte privé ({len(ex_fl_priv)})",
            f"🤫 Abonnés UNIQUEMENT à son compte privé ({len(ex_f_priv)})",
            f"👥 Abonnés aux 2 comptes ({len(communs)})"
        ])
        
        with sub1:
            st.markdown(f"""
            <div class="alert-card">
                <h4 style="margin:0; color:#ef4444;">🚨 Personnes suivies uniquement sur son compte privé</h4>
                <p style="margin:5px 0 0 0;">Il y a <b>{len(ex_fl_priv)} personnes</b> que Salomé suit sur <b>@salomee__pv</b> mais qu'elle NE SUIT PAS sur son compte public.</p>
            </div>
            """, unsafe_allow_html=True)
            
            df_ex = to_rich_dataframe(ex_fl_priv, include_rank=True, hide_viewer=True)
            st.dataframe(df_ex, use_container_width=True, hide_index=True, column_config={"Photo": st.column_config.ImageColumn("Photo"), "Lien Instagram": st.column_config.LinkColumn("Profil")})
            
        with sub2:
            st.markdown(f"""
            <div class="alert-card">
                <h4 style="margin:0; color:#f59e0b;">🤫 Personnes qui la suivent uniquement sur son compte privé</h4>
                <p style="margin:5px 0 0 0;">Il y a <b>{len(ex_f_priv)} personnes</b> abonnées à son compte privé qui ne la suivent pas sur le public.</p>
            </div>
            """, unsafe_allow_html=True)
            
            df_ef = to_rich_dataframe(ex_f_priv, include_rank=True, hide_viewer=True)
            st.dataframe(df_ef, use_container_width=True, hide_index=True, column_config={"Photo": st.column_config.ImageColumn("Photo"), "Lien Instagram": st.column_config.LinkColumn("Profil")})
            
        with sub3:
            st.markdown(f"""
            <div class="success-card">
                <h4 style="margin:0; color:#10b981;">👥 Personnes qui la suivent sur ses DEUX comptes</h4>
                <p style="margin:5px 0 0 0;">Il y a <b>{len(communs)} personnes</b> abonnées à la fois à @salome_2m et @salomee__pv.</p>
            </div>
            """, unsafe_allow_html=True)
            
            df_com = to_rich_dataframe(communs, include_rank=True, hide_viewer=False)
            st.dataframe(df_com, use_container_width=True, hide_index=True, column_config={"Photo": st.column_config.ImageColumn("Photo"), "Lien Instagram": st.column_config.LinkColumn("Profil")})


# ==========================================
# ONGLET 4 : RECHERCHE RAPIDE
# ==========================================
with tab_recherche:
    st.header("🔍 Rechercher un Profil Précis")
    st.write("Vérifiez instantanément si un compte est dans ses abonnés ou abonnements.")
    
    search_q = st.text_input("Entrez un prénom, nom ou pseudo (ex: thomas, julie, alex...)", key="search_instant").strip().lower().lstrip("@")
    
    if search_q and snap_main and snap_priv:
        f_main = get_snapshot_followers(snap_main["id"])
        f_priv = get_snapshot_followers(snap_priv["id"])
        fl_main = get_snapshot_following(snap_main["id"])
        fl_priv = get_snapshot_following(snap_priv["id"])
        
        matches = []
        for u in f_main:
            if search_q in u["username"].lower() or search_q in u.get("full_name", "").lower():
                matches.append({"Photo": u.get("profile_pic_url"), "Compte de Salomé": "@salome_2m (Public)", "Relation": "Elle est suivie par cette personne", "Pseudo": f"@{u['username']}", "Nom": u.get("full_name", ""), "Lien Instagram": f"https://www.instagram.com/{u['username']}/"})
                
        for u in fl_main:
            if search_q in u["username"].lower() or search_q in u.get("full_name", "").lower():
                matches.append({"Photo": u.get("profile_pic_url"), "Compte de Salomé": "@salome_2m (Public)", "Relation": "Salomé SUIT cette personne", "Pseudo": f"@{u['username']}", "Nom": u.get("full_name", ""), "Lien Instagram": f"https://www.instagram.com/{u['username']}/"})
                
        for u in f_priv:
            if search_q in u["username"].lower() or search_q in u.get("full_name", "").lower():
                matches.append({"Photo": u.get("profile_pic_url"), "Compte de Salomé": "@salomee__pv (Privé)", "Relation": "Elle est suivie par cette personne", "Pseudo": f"@{u['username']}", "Nom": u.get("full_name", ""), "Lien Instagram": f"https://www.instagram.com/{u['username']}/"})
                
        for u in fl_priv:
            if search_q in u["username"].lower() or search_q in u.get("full_name", "").lower():
                matches.append({"Photo": u.get("profile_pic_url"), "Compte de Salomé": "@salomee__pv (Privé)", "Relation": "Salomé SUIT cette personne", "Pseudo": f"@{u['username']}", "Nom": u.get("full_name", ""), "Lien Instagram": f"https://www.instagram.com/{u['username']}/"})
                
        if matches:
            st.success(f"{len(matches)} résultat(s) trouvé(s) pour '{search_q}' :")
            st.dataframe(pd.DataFrame(matches), use_container_width=True, hide_index=True, column_config={"Photo": st.column_config.ImageColumn("Photo"), "Lien Instagram": st.column_config.LinkColumn("Profil")})
        else:
            st.warning(f"Aucun résultat trouvé pour '{search_q}'. Ce compte n'est ni dans ses abonnés ni dans ses abonnements.")
