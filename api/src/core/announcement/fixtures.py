"""Mass fixture generator for announcements.

Generates a realistic, controlled set of announcements covering all
display types (banner/modal/blocker), alert levels, and states.
Announcements are rare system messages — the count is capped regardless of scale.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from faker import Faker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..fixture_registry import FixtureContext, FixtureDefinition
from .models import Announcement, AnnouncementDismissal

fake = Faker("fr_FR")

TYPES = ["info", "warning", "success", "danger"]

# Fixed set of realistic announcements covering all combinations
ANNOUNCEMENT_TEMPLATES: list[dict[str, Any]] = [
    # ── Active banners ─────────────────────────────────────────────
    {
        "title": "Maintenance prevue le 15/03/2026",
        "body": "<p>Le service sera temporairement indisponible le <strong>15 mars</strong> entre 2h et 4h du matin.</p>",
        "type": "warning",
        "display": "banner",
        "requires_acknowledgment": False,
        "is_dismissible": True,
        "priority": 5,
        "state": "active",
    },
    {
        "title": "Amelioration des performances deployee",
        "body": "<p>Les temps de chargement ont ete reduits de 40%. <em>Aucune action requise.</em></p>",
        "type": "success",
        "display": "banner",
        "requires_acknowledgment": False,
        "is_dismissible": True,
        "priority": 3,
        "state": "active",
    },
    {
        "title": "Incident reseau en cours",
        "body": "<p>Certains utilisateurs peuvent rencontrer des lenteurs. Nos equipes travaillent a la resolution.</p>",
        "type": "danger",
        "display": "banner",
        "requires_acknowledgment": False,
        "is_dismissible": False,
        "priority": 9,
        "state": "active",
    },
    {
        "title": "Nouvelle fonctionnalite : favoris",
        "body": "<p>Decouvrez la gestion des <strong>favoris</strong> pour epingler vos pages les plus utilisees.</p>",
        "type": "info",
        "display": "banner",
        "requires_acknowledgment": False,
        "is_dismissible": True,
        "priority": 2,
        "state": "active",
    },
    # ── Active modals (dismissible) ────────────────────────────────
    {
        "title": "Bienvenue sur Sitter v2026.03 !",
        "body": (
            "<p>Nous sommes ravis de vous presenter la nouvelle version.</p>"
            "<h3>Nouveautes</h3>"
            "<ul><li>Systeme d'annonces</li><li>Commentaires avec moderation</li>"
            "<li>Favoris et pagination</li></ul>"
        ),
        "type": "success",
        "display": "modal",
        "requires_acknowledgment": False,
        "is_dismissible": True,
        "priority": 4,
        "state": "active",
    },
    # ── Active modal (requires acknowledgment) ─────────────────────
    {
        "title": "Conditions generales mises a jour",
        "body": (
            "<p>Les CGU ont ete mises a jour le <strong>1er mars 2026</strong>.</p>"
            "<ul><li>Politique de conservation des donnees</li>"
            "<li>Droits d'acces aux informations personnelles</li>"
            "<li>Gestion des cookies et traceurs</li></ul>"
            "<p>Veuillez prendre connaissance de ces modifications.</p>"
        ),
        "type": "warning",
        "display": "modal",
        "requires_acknowledgment": True,
        "is_dismissible": True,
        "priority": 10,
        "state": "active",
    },
    # ── Active blocker (mandatory, cannot be dismissed) ────────────
    {
        "title": "Nouvelle politique de securite",
        "body": (
            "<p>De nouvelles regles de securite s'appliquent :</p>"
            "<ul><li>Mot de passe minimum : <strong>12 caracteres</strong></li>"
            "<li>Double authentification obligatoire pour les admins</li>"
            "<li>Sessions expirent apres 30 minutes d'inactivite</li></ul>"
        ),
        "type": "danger",
        "display": "blocker",
        "requires_acknowledgment": True,
        "is_dismissible": False,
        "priority": 10,
        "state": "active",
    },
    # ── Targeted (role-specific) ───────────────────────────────────
    {
        "title": "Rappel administrateurs : audit trimestriel",
        "body": "<p>L'audit trimestriel des permissions est prevu cette semaine. Verifiez les acces de vos equipes.</p>",
        "type": "info",
        "display": "banner",
        "requires_acknowledgment": False,
        "is_dismissible": True,
        "priority": 6,
        "target_roles": ["admin"],
        "state": "active",
    },
    # ── Expired ────────────────────────────────────────────────────
    {
        "title": "Mise a jour de securite deployee (fevrier)",
        "body": "<p>Les correctifs de securite du mois de fevrier ont ete appliques.</p>",
        "type": "info",
        "display": "banner",
        "requires_acknowledgment": False,
        "is_dismissible": True,
        "priority": 3,
        "state": "expired",
    },
    {
        "title": "Interruption planifiee terminee",
        "body": "<p>La maintenance du 20 fevrier est terminee. Tous les services sont retablis.</p>",
        "type": "success",
        "display": "modal",
        "requires_acknowledgment": False,
        "is_dismissible": True,
        "priority": 2,
        "state": "expired",
    },
    # ── Future (scheduled) ─────────────────────────────────────────
    {
        "title": "Migration base de donnees prevue en avril",
        "body": "<p>Une migration majeure est planifiee pour le <strong>5 avril 2026</strong>. Details a venir.</p>",
        "type": "warning",
        "display": "banner",
        "requires_acknowledgment": False,
        "is_dismissible": True,
        "priority": 4,
        "state": "future",
    },
    {
        "title": "Nouvelle interface utilisateur (beta)",
        "body": "<p>La nouvelle interface sera disponible en beta a partir du <strong>10 avril</strong>.</p>",
        "type": "info",
        "display": "modal",
        "requires_acknowledgment": True,
        "is_dismissible": True,
        "priority": 5,
        "state": "future",
    },
    # ── Inactive (disabled by admin) ───────────────────────────────
    {
        "title": "Ancien message de bienvenue",
        "body": "<p>Ce message n'est plus affiche.</p>",
        "type": "info",
        "display": "banner",
        "requires_acknowledgment": False,
        "is_dismissible": True,
        "priority": 0,
        "state": "inactive",
    },
]


async def _generate_announcements(db: AsyncSession, ctx: FixtureContext) -> dict[str, Any]:
    """Generate a controlled set of announcements covering all variations."""
    user_ids = ctx.user_ids
    admin_id = ctx.admin_id

    if not admin_id:
        return {"error": "No admin ID available."}

    now = datetime.now(timezone.utc)
    generated = 0
    counts = {"banner": 0, "modal": 0, "blocker": 0}
    level_counts = {t: 0 for t in TYPES}

    for tpl in ANNOUNCEMENT_TEMPLATES:
        state = tpl["state"]

        if state == "active":
            start = now - timedelta(hours=fake.random_int(min=1, max=72))
            end = now + timedelta(days=fake.random_int(min=7, max=30)) if fake.boolean(chance_of_getting_true=40) else None
            is_active = True
        elif state == "expired":
            start = now - timedelta(days=fake.random_int(min=30, max=60))
            end = now - timedelta(days=fake.random_int(min=1, max=15))
            is_active = True
        elif state == "future":
            start = now + timedelta(days=fake.random_int(min=10, max=40))
            end = now + timedelta(days=fake.random_int(min=41, max=70)) if fake.boolean(chance_of_getting_true=50) else None
            is_active = True
        else:  # inactive
            start = now - timedelta(days=fake.random_int(min=10, max=30))
            end = None
            is_active = False

        ann = Announcement(
            title=tpl["title"],
            body=tpl["body"],
            type=tpl["type"],
            display=tpl["display"],
            requires_acknowledgment=tpl["requires_acknowledgment"],
            target_roles=tpl.get("target_roles"),
            start_date=start,
            end_date=end,
            is_dismissible=tpl["is_dismissible"],
            priority=tpl["priority"],
            is_active=is_active,
            created_by_id=admin_id,
            created_at=start - timedelta(days=1),
            updated_at=now,
        )
        db.add(ann)
        generated += 1
        counts[tpl["display"]] = counts.get(tpl["display"], 0) + 1
        level_counts[tpl["type"]] += 1

    await db.flush()

    # Collect announcement IDs for dismissals
    result = await db.execute(select(Announcement.id))
    announcement_ids = [row[0] for row in result.all()]

    # Generate some dismissals (only for dismissible announcements)
    dismissals = 0
    if user_ids and announcement_ids:
        dismissible_ids_result = await db.execute(
            select(Announcement.id).where(Announcement.is_dismissible == True)  # noqa: E712
        )
        dismissible_ids = [row[0] for row in dismissible_ids_result.all()]

        if dismissible_ids:
            seen_pairs: set[tuple[int, int]] = set()
            target = min(len(user_ids) // 5, len(dismissible_ids) * 10, 200)
            for _ in range(target * 2):  # overshoot to account for duplicates
                if dismissals >= target:
                    break
                uid = fake.random_element(user_ids)
                aid = fake.random_element(dismissible_ids)
                if (uid, aid) in seen_pairs:
                    continue
                seen_pairs.add((uid, aid))
                db.add(AnnouncementDismissal(
                    announcement_id=aid,
                    user_id=uid,
                    dismissed_at=now - timedelta(hours=fake.random_int(min=0, max=72)),
                ))
                dismissals += 1

            await db.flush()

    ctx.set("announcement.ids", announcement_ids)

    return {
        "announcements_created": generated,
        "by_display": counts,
        "by_level": level_counts,
        "dismissals_created": dismissals,
    }


fixtures = [
    FixtureDefinition(
        name="announcement",
        label="Annonces",
        description="Generate realistic system announcements (banners, modals, blockers) with dismissals",
        depends=["_identity"],
        handler=_generate_announcements,
        check_table="announcements",
        check_min_rows=5,
    ),
]
